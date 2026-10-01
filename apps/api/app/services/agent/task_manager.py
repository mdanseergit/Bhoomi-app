"""
Task and session lifecycle, plus the budget every run is accountable to.

The manager owns the transitions (``queued -> running -> completed`` and the
approval-halted branch) and the persisted counters. The loop asks it for
permission to take a step; it is the component that says no when a cap is
reached. Keeping that here means no individual phase can quietly exceed the
budget a task was given.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.agent import (
    AgentMemory,
    AgentMemoryType,
    AgentPhase,
    AgentSession,
    AgentSessionStatus,
    AgentStep,
    AgentStepStatus,
    AgentTask,
    AgentTaskStatus,
)
from app.models.user import User

logger = get_logger("bhoomi.agent.tasks")

# observe, understand, plan, use_tools, analyze, act, verify, remember, notify
SPINE_PHASE_COUNT = 9
MIN_STEPS_FOR_SPINE = SPINE_PHASE_COUNT

TERMINAL_TASK_STATUSES = frozenset(
    {
        AgentTaskStatus.COMPLETED,
        AgentTaskStatus.FAILED,
        AgentTaskStatus.CANCELLED,
        AgentTaskStatus.EXPIRED,
    }
)


class BudgetExceeded(RuntimeError):
    """The task cannot take another step within its limits."""


@dataclass
class BudgetReport:
    steps_used: int
    max_steps: int
    tool_calls_used: int
    max_tool_calls: int
    tokens_in: int
    tokens_out: int
    elapsed_seconds: int
    max_seconds: int
    repetition_count: int
    max_repetition: int

    @property
    def step_exhausted(self) -> bool:
        return self.steps_used >= self.max_steps

    @property
    def tools_exhausted(self) -> bool:
        return self.tool_calls_used >= self.max_tool_calls

    @property
    def timed_out(self) -> bool:
        return self.elapsed_seconds >= self.max_seconds

    @property
    def limit_reason(self) -> str | None:
        if self.timed_out:
            return f"time limit of {self.max_seconds}s reached"
        if self.step_exhausted:
            return f"step limit of {self.max_steps} reached"
        if self.tools_exhausted:
            return f"tool-call limit of {self.max_tool_calls} reached"
        if self.repetition_count >= self.max_repetition:
            return f"the loop repeated the same call {self.max_repetition} times"
        return None

    def to_dict(self) -> dict:
        return {
            "steps_used": self.steps_used,
            "max_steps": self.max_steps,
            "tool_calls_used": self.tool_calls_used,
            "max_tool_calls": self.max_tool_calls,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "elapsed_seconds": self.elapsed_seconds,
            "max_seconds": self.max_seconds,
            "repetition_count": self.repetition_count,
            "max_repetition": self.max_repetition,
            "limit_reason": self.limit_reason,
        }


@dataclass
class RepetitionGuard:
    """Catches a loop that keeps re-asking for the same thing.

    A model that keeps calling ``weather_now`` with identical arguments is not
    converging. Counting recent signatures stops it early instead of burning
    the whole step budget to arrive at the same place.
    """

    limit: int = 3
    _signatures: list[str] = field(default_factory=list)

    def observe(self, signature: str) -> int:
        if signature:
            self._signatures.append(signature)
        return self._consecutive(signature)

    def _consecutive(self, signature: str) -> int:
        count = 0
        for item in reversed(self._signatures):
            if item == signature:
                count += 1
            else:
                break
        return count

    @property
    def count(self) -> int:
        if not self._signatures:
            return 0
        return self._consecutive(self._signatures[-1])


class TaskManager:
    def __init__(self, db: Session):
        self.db = db

    # --- Sessions -------------------------------------------------------

    def get_or_create_session(
        self,
        user: User,
        *,
        session_id: str | None,
        farm_id: str | None,
        language: str,
    ) -> AgentSession:
        now = datetime.now(timezone.utc)

        if session_id:
            try:
                candidate_uuid = uuid.UUID(session_id)
            except (ValueError, AttributeError, TypeError):
                candidate_uuid = None
            if candidate_uuid is not None:
                session = self.db.get(AgentSession, candidate_uuid)
                # A session belonging to somebody else is treated as absent
                # rather than as a 403, so the endpoint cannot be used to probe
                # whether a given session id exists.
                if session is not None and str(session.user_id) == str(user.id):
                    if session.expires_at is None or session.expires_at > now:
                        # The caller may switch farms mid-conversation. The
                        # session follows the newest farm so the thread is never
                        # labelled with one farm while the tools read another.
                        if farm_id and str(session.farm_id or "") != farm_id:
                            session.farm_id = uuid.UUID(farm_id)
                        session.last_activity_at = now
                        self.db.commit()
                        return session

        session = AgentSession(
            user_id=user.id,
            farm_id=farm_id,
            status=AgentSessionStatus.ACTIVE,
            message_count=0,
            preferred_language=language,
            last_activity_at=now,
            expires_at=now + timedelta(hours=settings.AGENT_SESSION_TTL_HOURS),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def close_session(self, session: AgentSession) -> AgentSession:
        session.status = AgentSessionStatus.CLOSED
        self.db.commit()
        self.db.refresh(session)
        return session

    # --- Tasks ----------------------------------------------------------

    def create_task(
        self,
        *,
        session: AgentSession,
        user: User,
        query: str,
        language: str,
        max_steps: int | None = None,
        max_tool_calls: int | None = None,
    ) -> AgentTask:
        now = datetime.now(timezone.utc)
        # A caller may tighten a budget but never raise it above the configured
        # ceiling: the cap exists to bound cost for everyone. The floor is the
        # fixed spine, so a run always records its own complete phase trail.
        effective_steps = min(
            max(MIN_STEPS_FOR_SPINE, max_steps or settings.MAX_AGENT_STEPS),
            max(settings.MAX_AGENT_STEPS, MIN_STEPS_FOR_SPINE),
        )
        task = AgentTask(
            session_id=session.id,
            user_id=user.id,
            farm_id=session.farm_id,
            query=query,
            language=language,
            status=AgentTaskStatus.QUEUED,
            step_count=0,
            max_steps=effective_steps,
            max_tool_calls=min(
                max_tool_calls or settings.MAX_AGENT_TOOL_CALLS, settings.MAX_AGENT_TOOL_CALLS
            ),
            evidence=[],
            missing_data=[],
            conflicts=[],
            started_at=now,
            expires_at=now + timedelta(seconds=settings.MAX_AGENT_TASK_SECONDS),
        )
        self.db.add(task)
        session.message_count += 1
        session.last_activity_at = now
        self.db.commit()
        self.db.refresh(task)
        return task

    def start_task(self, task: AgentTask) -> AgentTask:
        task.status = AgentTaskStatus.RUNNING
        task.started_at = task.started_at or datetime.now(timezone.utc)
        self.db.commit()
        return task

    def complete_task(
        self,
        task: AgentTask,
        *,
        response: str,
        confidence: float | None = None,
        evidence: list | None = None,
        missing_data: list | None = None,
        conflicts: list | None = None,
        model_used: str | None = None,
        provider_used: str | None = None,
        fallback_used: bool = False,
    ) -> AgentTask:
        task.response = response
        task.status = AgentTaskStatus.COMPLETED
        task.current_phase = AgentPhase.NOTIFY
        task.completed_at = datetime.now(timezone.utc)
        task.confidence = confidence if confidence is not None else task.confidence
        task.evidence = evidence if evidence is not None else task.evidence
        task.missing_data = missing_data if missing_data is not None else task.missing_data
        task.conflicts = conflicts if conflicts is not None else task.conflicts
        task.model_used = model_used or task.model_used
        task.provider_used = provider_used or task.provider_used
        task.fallback_used = fallback_used or task.fallback_used
        self.db.commit()
        self.db.refresh(task)
        return task

    def fail_task(self, task: AgentTask, reason: str) -> AgentTask:
        task.status = AgentTaskStatus.FAILED
        task.error_message = reason[:1000]
        task.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(task)
        return task

    def halt_for_approval(self, task: AgentTask) -> AgentTask:
        task.status = AgentTaskStatus.WAITING_FOR_APPROVAL
        task.requires_approval = True
        self.db.commit()
        self.db.refresh(task)
        return task

    # --- Steps ----------------------------------------------------------

    def open_step(self, task: AgentTask, phase: AgentPhase, goal: str | None = None) -> AgentStep:
        now = datetime.now(timezone.utc)
        step = AgentStep(
            task_id=task.id,
            step_number=task.step_count + 1,
            phase=phase,
            status=AgentStepStatus.STARTED,
            goal=goal,
            evidence=[],
            sources=[],
            missing_data=[],
            conflicts=[],
            started_at=now,
        )
        self.db.add(step)
        task.step_count += 1
        task.current_phase = phase
        self.db.commit()
        self.db.refresh(step)
        return step

    def close_step(
        self,
        step: AgentStep,
        *,
        status: AgentStepStatus = AgentStepStatus.COMPLETED,
        summary: str | None = None,
        evidence: list | None = None,
        sources: list | None = None,
        missing_data: list | None = None,
        conflicts: list | None = None,
        confidence: float | None = None,
        tool_call_count: int = 0,
        tokens_in: int = 0,
        tokens_out: int = 0,
        model_used: str | None = None,
        duration_ms: int | None = None,
        error_message: str | None = None,
    ) -> AgentStep:
        started = step.started_at
        completed = datetime.now(timezone.utc)
        step.status = status
        step.summary = summary
        step.evidence = evidence if evidence is not None else step.evidence
        step.sources = sources if sources is not None else step.sources
        step.missing_data = missing_data if missing_data is not None else step.missing_data
        step.conflicts = conflicts if conflicts is not None else step.conflicts
        step.confidence = confidence if confidence is not None else step.confidence
        step.tool_call_count = tool_call_count
        step.tokens_in = tokens_in
        step.tokens_out = tokens_out
        step.model_used = model_used or step.model_used
        step.error_message = error_message
        step.completed_at = completed
        if started is not None:
            elapsed = completed - started
            step.duration_ms = duration_ms if duration_ms is not None else int(elapsed.total_seconds() * 1000)
        self.db.commit()
        self.db.refresh(step)
        return step

    # --- Budget ---------------------------------------------------------

    def budget(self, task: AgentTask, guard: RepetitionGuard | None = None) -> BudgetReport:
        started = task.started_at or datetime.now(timezone.utc)
        elapsed = int((datetime.now(timezone.utc) - started).total_seconds())
        return BudgetReport(
            steps_used=task.step_count,
            max_steps=task.max_steps,
            tool_calls_used=task.tool_call_count,
            max_tool_calls=task.max_tool_calls,
            tokens_in=task.tokens_in,
            tokens_out=task.tokens_out,
            elapsed_seconds=elapsed,
            max_seconds=settings.MAX_AGENT_TASK_SECONDS,
            repetition_count=guard.count if guard else 0,
            max_repetition=settings.AGENT_REPETITION_LIMIT,
        )

    def ensure_can_step(self, task: AgentTask, guard: RepetitionGuard | None = None) -> BudgetReport:
        """Full gate, including the step ceiling.

        Used where a phase might repeat, i.e. where the loop is at risk of
        spending steps indefinitely.
        """
        report = self.budget(task, guard)
        reason = report.limit_reason
        if reason:
            raise BudgetExceeded(reason)
        return report

    def ensure_not_timed_out(self, task: AgentTask) -> None:
        """Time gate only, for the mandatory phases of the spine.

        ``observe .. notify`` must each be recorded or the audit trail is
        incomplete, so these phases are never skipped for the step ceiling --
        a run that has exhausted its step budget still reports its own limits
        and what it observed. Only the wall-clock cap can interrupt them,
        because an unbounded run is the failure mode worth guarding.
        """
        report = self.budget(task)
        if report.timed_out:
            raise BudgetExceeded(f"time limit of {report.max_seconds}s reached")

    def record_usage(self, task: AgentTask, *, tokens_in: int, tokens_out: int) -> None:
        task.tokens_in += max(0, tokens_in)
        task.tokens_out += max(0, tokens_out)
        self.db.commit()

    # --- Memory ---------------------------------------------------------

    def remember(
        self,
        *,
        user_id,
        farm_id,
        task_id,
        key: str,
        content: dict,
        source: str,
        confidence: float,
        memory_type: AgentMemoryType = AgentMemoryType.FACT,
        is_user_correction: bool = False,
    ) -> AgentMemory:
        """Upserts one memory per (user, key).

        Memory is written only from something observed or stated, never from
        the model's speculation, so a later session cannot be misled by an
        inference that was never verified.
        """
        existing = (
            self.db.query(AgentMemory)
            .filter(AgentMemory.user_id == user_id, AgentMemory.key == key)
            .first()
        )
        if existing is not None:
            existing.content = content
            existing.source = source
            existing.confidence = confidence
            existing.memory_type = memory_type
            existing.is_user_correction = is_user_correction
            existing.last_accessed_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        memory = AgentMemory(
            user_id=user_id,
            farm_id=farm_id,
            task_id=task_id,
            memory_type=memory_type,
            key=key,
            content=content,
            source=source,
            confidence=confidence,
            is_user_correction=is_user_correction,
        )
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        return memory

    def recall(self, *, user_id, limit: int = 10) -> list[AgentMemory]:
        return (
            self.db.query(AgentMemory)
            .filter(AgentMemory.user_id == user_id)
            .order_by(
                AgentMemory.is_user_correction.desc(),
                AgentMemory.importance.desc(),
                AgentMemory.confidence.desc(),
            )
            .limit(limit)
            .all()
        )


__all__ = [
    "BudgetExceeded",
    "BudgetReport",
    "RepetitionGuard",
    "TaskManager",
    "TERMINAL_TASK_STATUSES",
]