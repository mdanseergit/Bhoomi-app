"""
Tool execution: permission check, budget accounting, timeout, audit row.

Nothing reaches a handler without passing through here. The executor is the
single place that knows a caller's scopes, and the single place that writes
the ``tool_executions`` row, so the audit trail cannot be bypassed by
calling a handler directly.

Failures are recorded, never swallowed: a denied call, a bad argument, a
timeout and an unavailable provider are all distinct outcomes the loop and
the UI can explain.
"""
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.agent import (
    AgentStep,
    AgentTask,
    ToolExecution,
    ToolExecutionStatus,
    ToolRiskLevel,
)
from app.services.agent.registry import (
    ToolContext,
    ToolInputError,
    ToolOutputError,
    ToolResult,
    registry,
)

logger = get_logger("bhoomi.agent.executor")

# Sentinel returned instead of a ToolResult when execution fails, so the
# caller always gets a uniform shape plus a recorded reason.
_FAILURE_PREFIX = "tool execution did not complete"


class ToolBudgetExhausted(RuntimeError):
    """The task has spent its tool-call allowance."""


class ToolApprovalRequired(RuntimeError):
    """A write that needs a human decision before it may run.

    Raised by the executor rather than handled inside a handler, so a gated
    tool can never be executed as a side effect of planning. The caller turns
    this into an ``AgentAction`` + ``AgentApproval`` pair and halts the task.
    """

    def __init__(self, spec, reason: str) -> None:
        self.spec = spec
        self.reason = reason
        super().__init__(reason)


@dataclass
class ExecutionOutcome:
    """What the loop sees after one tool call."""

    tool_name: str
    ok: bool
    result: ToolResult | None
    reason: str | None
    duration_ms: int
    status: ToolExecutionStatus
    execution_id: str | None

    @property
    def summary(self) -> str:
        if self.ok and self.result is not None:
            return self.result.summary
        return f"{self.tool_name}: {self.reason}"


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


class ToolExecutor:
    def __init__(self, *, db: Session, task: AgentTask, user_id: str, role: str, granted_scopes: set[str]):
        self.db = db
        self.task = task
        self.user_id = user_id
        self.role = role
        self.granted_scopes = granted_scopes

    def available_names(self) -> list[str]:
        return [spec.name for spec in registry.list_tools(enabled_only=True) if self._allowed(spec)]

    def _allowed(self, spec) -> bool:
        return set(spec.required_permissions).issubset(self.granted_scopes)

    def run(
        self,
        name: str,
        raw_args: dict[str, Any],
        *,
        step: AgentStep | None = None,
        farm: Any = None,
        language: str = "en",
        approved_action_types: frozenset[str] | None = None,
    ) -> ExecutionOutcome:
        started = datetime.now(timezone.utc)
        t0 = time.perf_counter()

        if self.task.tool_call_count >= self.task.max_tool_calls:
            # Recorded as a budget stop rather than silently returning, so the
            # audit shows why the loop ended where it did.
            raise ToolBudgetExhausted(
                f"Tool-call budget of {self.task.max_tool_calls} is exhausted for this task."
            )

        spec = registry.get(name)
        if spec is None:
            return self._finish(
                None, name, ToolExecutionStatus.FAILED, started, t0,
                reason="No tool with that name is registered.",
            )
        if not spec.enabled:
            return self._finish(
                None, name, ToolExecutionStatus.DENIED, started, t0,
                reason=f"Tool '{name}' is disabled.",
            )
        if not self._allowed(spec):
            missing = [s for s in spec.required_permissions if s not in self.granted_scopes]
            return self._finish(
                spec, name, ToolExecutionStatus.DENIED, started, t0,
                reason=f"Your role is not permitted to use '{name}' (missing: {', '.join(missing)}).",
            )

        try:
            args = spec.validate_input(raw_args or {})
        except ToolInputError as exc:
            return self._finish(
                spec, name, ToolExecutionStatus.FAILED, started, t0, reason=str(exc),
            )

        # The gate sits after permission and input validation but before any row
        # is written or any handler runs, so a denied action leaves no trace
        # beyond the audit record of the refusal itself.
        if (
            spec.requires_approval
            and settings.AGENT_HIGH_RISK_APPROVAL_REQUIRED
            and name not in (approved_action_types or frozenset())
        ):
            raise ToolApprovalRequired(
                spec,
                f"'{name}' needs human approval before it can run.",
            )

        row = ToolExecution(
            task_id=self.task.id,
            step_id=step.id if step else None,
            tool_name=spec.name,
            tool_version=spec.version,
            status=ToolExecutionStatus.STARTED,
            risk_level=spec.risk_level,
            required_permissions=list(spec.required_permissions),
            input_payload=_safe_payload(raw_args),
            source=spec.source,
            started_at=started,
        )
        self.db.add(row)
        self.db.commit()

        self.task.tool_call_count += 1
        self.db.commit()

        ctx = ToolContext(
            db=self.db,
            farm=farm,
            user_id=self.user_id,
            role=self.role,
            task_id=str(self.task.id),
            language=language,
        )

        result, status, reason, retries = self._invoke_with_retries(spec, ctx, args)
        row.retry_count = retries
        return self._finish(
            spec, name, status, started, t0, row=row, result=result, reason=reason,
        )

    def _invoke_with_retries(self, spec, ctx: ToolContext, args):
        """Runs a handler, retrying transient faults up to ``spec.max_retries``.

        Retries are reserved for faults that are plausibly transient (timeout,
        an output-contract violation on a first call). A permission denial or a
        budget stop is never retried, because retrying cannot change the
        answer. Every attempt is reflected in ``retry_count`` on the audit row.
        """
        attempts = max(0, spec.max_retries)
        last_reason: str | None = None
        status = ToolExecutionStatus.FAILED

        for attempt in range(attempts + 1):
            # Only faults that could plausibly resolve themselves are retried. A
            # handler raising is a bug in that handler, so re-running it just
            # burns wall-clock and inflates retry_count on the audit row.
            retryable = True
            try:
                result = self._invoke_with_timeout(spec, ctx, args)
            except TimeoutError:
                status = ToolExecutionStatus.TIMEOUT
                last_reason = f"Tool '{spec.name}' exceeded {spec.timeout_seconds}s."
            except ToolOutputError as exc:
                status = ToolExecutionStatus.FAILED
                last_reason = str(exc)
            except Exception as exc:  # noqa: BLE001 - surfaced as a recorded failure, never a crash
                logger.warning("agent_tool_failed", tool=spec.name, attempt=attempt, error=repr(exc))
                status = ToolExecutionStatus.FAILED
                last_reason = f"{_FAILURE_PREFIX}: {type(exc).__name__}."
                retryable = False
            else:
                if result is not None and spec.output_model is not None:
                    try:
                        normalised = spec.validate_output(result.data)
                    except ToolOutputError as exc:
                        status = ToolExecutionStatus.FAILED
                        last_reason = str(exc)
                    else:
                        return (
                            ToolResult(
                                data=normalised,
                                summary=result.summary,
                                sources=result.sources,
                                evidence=result.evidence,
                                missing_data=result.missing_data,
                                conflicts=result.conflicts,
                                confidence=result.confidence,
                                available=result.available,
                                action_id=result.action_id,
                                verification=result.verification,
                            ),
                            ToolExecutionStatus.SUCCEEDED,
                            None,
                            attempt,
                        )
                else:
                    return result, ToolExecutionStatus.SUCCEEDED, None, attempt

            if not retryable:
                break

        # ``attempt`` is the index of the final try, so it doubles as the count
        # of retries actually performed.
        return None, status, last_reason, attempt

    def _invoke_with_timeout(self, spec, ctx: ToolContext, args) -> ToolResult:
        """Runs a handler under a wall-clock ceiling.

        Providers already carry their own HTTP timeout, so this is a backstop
        for a handler that hangs. Python cannot kill a thread safely, so the
        timeout is recorded honestly and the (already-doomed) thread is left
        to finish on its own rather than pretending it was cancelled.
        """
        import concurrent.futures as cf

        with cf.ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"tool-{spec.name}") as pool:
            future = pool.submit(spec.handler, ctx, args)
            try:
                return future.result(timeout=spec.timeout_seconds)
            except cf.TimeoutError as exc:
                raise TimeoutError(str(exc)) from exc

    def _finish(
        self,
        spec,
        name: str,
        status: ToolExecutionStatus,
        started: datetime,
        t0: float,
        *,
        result: ToolResult | None = None,
        reason: str | None = None,
        row: ToolExecution | None = None,
    ) -> ExecutionOutcome:
        duration_ms = int((time.perf_counter() - t0) * 1000)

        if row is None:
            row = ToolExecution(
                task_id=self.task.id,
                tool_name=name,
                tool_version=getattr(spec, "version", None),
                status=status,
                risk_level=getattr(spec, "risk_level", ToolRiskLevel.READ_ONLY),
                required_permissions=list(getattr(spec, "required_permissions", ()) or ()),
                input_payload={},
                source=getattr(spec, "source", None),
                started_at=started,
            )
            self.db.add(row)

        row.status = status
        row.duration_ms = duration_ms
        row.completed_at = datetime.now(timezone.utc)
        row.error_message = reason
        if result is not None:
            row.output_payload = {
                "summary": result.summary,
                "available": result.available,
                "sources": result.sources,
                "missing_data": result.missing_data,
                "confidence": result.confidence,
                "action_id": result.action_id,
                "verification": result.verification,
                "data": _bounded(result.data),
            }
        self.db.commit()
        self.db.refresh(row)

        return ExecutionOutcome(
            tool_name=name,
            ok=status is ToolExecutionStatus.SUCCEEDED,
            result=result,
            reason=reason,
            duration_ms=duration_ms,
            status=status,
            execution_id=str(row.id),
        )


def _safe_payload(payload: Any) -> dict:
    """Strips anything that is not plain JSON before it is persisted."""
    if not isinstance(payload, dict):
        return {"value": str(payload)[:200]}
    return {str(k): v for k, v in list(payload.items())[:20]}


def _bounded(data: dict) -> dict:
    """Keeps stored tool output small; the full payload never needs to sit in
    the audit row, only enough to explain what the agent saw."""
    limited: dict = {}
    for index, (key, value) in enumerate(data.items()):
        if index >= 30:
            limited["_truncated"] = True
            break
        if isinstance(value, (list, dict)):
            limited[key] = f"<{len(value)} items>"
        else:
            limited[key] = value
    return limited


__all__ = [
    "ExecutionOutcome",
    "ToolExecutor",
    "ToolBudgetExhausted",
    "ToolApprovalRequired",
    "_iso",
]