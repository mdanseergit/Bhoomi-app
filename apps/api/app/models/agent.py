"""
Persistence for the BHOOMI agent runtime.

The agent loop is deliberately auditable: every task, every reasoning phase,
every tool call and every proposed agricultural action is a row before it is
anything else. That is what lets the platform answer "why did it tell me to
irrigate?" months later, and what lets a human approve or reject a write
before it happens.

What is intentionally *not* stored: hidden chain-of-thought. Steps record the
public phase, its outcome summary, the evidence used and the confidence, never
the model's private reasoning trace.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class AgentSessionStatus(str, enum.Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    EXPIRED = "expired"


class AgentTaskStatus(str, enum.Enum):
    """Lifecycle of one agent request.

    ``waiting_for_approval`` is a first-class terminal-for-now state: the loop
    halted at a write boundary and will only resume after a human decision is
    recorded against the matching ``agent_actions``/``agent_approvals`` row.
    """

    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class AgentPhase(str, enum.Enum):
    """Public phases of the loop.

    The phase names are the audit trail shown to the user; they are not a
    transcript of internal reasoning.
    """

    OBSERVE = "observe"
    UNDERSTAND = "understand"
    PLAN = "plan"
    USE_TOOLS = "use_tools"
    ANALYZE = "analyze"
    ACT = "act"
    VERIFY = "verify"
    REMEMBER = "remember"
    NOTIFY = "notify"


class AgentStepStatus(str, enum.Enum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ToolExecutionStatus(str, enum.Enum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"
    TIMEOUT = "timeout"


class ToolRiskLevel(str, enum.Enum):
    """Risk drives both audit depth and whether a write needs human approval."""

    READ_ONLY = "read_only"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AgentActionStatus(str, enum.Enum):
    PROPOSED = "proposed"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    VERIFIED = "verified"
    FAILED = "failed"


class AgentApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class AgentAlertStatus(str, enum.Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class AgentMonitorStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"


class AgentMemoryType(str, enum.Enum):
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    FACT = "fact"
    PREFERENCE = "preference"
    OUTCOME = "outcome"


class AgentEvaluationResult(str, enum.Enum):
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"


class AgentSession(UUIDPKMixin, TimestampMixin, Base):
    """A conversation thread. Tasks hang off it; memory may outlive it."""

    __tablename__ = "agent_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    farm_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id"), nullable=True, index=True
    )
    title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[AgentSessionStatus] = mapped_column(
        Enum(AgentSessionStatus, name="agent_session_status"),
        default=AgentSessionStatus.ACTIVE,
        nullable=False,
    )
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tasks = relationship("AgentTask", back_populates="session", cascade="all, delete-orphan")


class AgentTask(UUIDPKMixin, TimestampMixin, Base):
    """One agent request: the unit of work, budget and audit."""

    __tablename__ = "agent_tasks"

    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_sessions.id"), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    farm_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id"), nullable=True, index=True
    )

    query: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="en", nullable=False)

    status: Mapped[AgentTaskStatus] = mapped_column(
        Enum(AgentTaskStatus, name="agent_task_status"),
        default=AgentTaskStatus.QUEUED,
        nullable=False,
        index=True,
    )
    current_phase: Mapped[AgentPhase | None] = mapped_column(
        Enum(AgentPhase, name="agent_phase"), nullable=True
    )
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Budget. Every limit is stored per task so a run can be audited after the
    # fact against the caps it was actually given.
    step_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_steps: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_call_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_tool_calls: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    model_used: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_used: Mapped[str | None] = mapped_column(String(40), nullable=True)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    missing_data: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    conflicts: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session = relationship("AgentSession", back_populates="tasks")
    steps = relationship("AgentStep", back_populates="task", cascade="all, delete-orphan")
    tool_executions = relationship(
        "ToolExecution", back_populates="task", cascade="all, delete-orphan"
    )
    actions = relationship("AgentAction", back_populates="task", cascade="all, delete-orphan")


class AgentStep(UUIDPKMixin, TimestampMixin, Base):
    """One phase of one task. Public outcome only, never hidden reasoning."""

    __tablename__ = "agent_steps"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_tasks.id"), nullable=False, index=True
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[AgentPhase] = mapped_column(
        Enum(AgentPhase, name="agent_phase"), nullable=False
    )
    status: Mapped[AgentStepStatus] = mapped_column(
        Enum(AgentStepStatus, name="agent_step_status"),
        default=AgentStepStatus.STARTED,
        nullable=False,
    )
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    sources: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    missing_data: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    conflicts: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    tool_call_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(120), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    task = relationship("AgentTask", back_populates="steps")
    tool_executions = relationship(
        "ToolExecution", back_populates="step", cascade="all, delete-orphan"
    )


class ToolExecution(UUIDPKMixin, TimestampMixin, Base):
    """One tool invocation, with the permission decision that allowed it."""

    __tablename__ = "tool_executions"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_tasks.id"), nullable=False, index=True
    )
    step_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_steps.id"), nullable=True, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    tool_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[ToolExecutionStatus] = mapped_column(
        Enum(ToolExecutionStatus, name="tool_execution_status"),
        default=ToolExecutionStatus.STARTED,
        nullable=False,
    )
    risk_level: Mapped[ToolRiskLevel] = mapped_column(
        Enum(ToolRiskLevel, name="tool_risk_level"),
        default=ToolRiskLevel.READ_ONLY,
        nullable=False,
    )
    required_permissions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    input_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    output_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    task = relationship("AgentTask", back_populates="tool_executions")
    step = relationship("AgentStep", back_populates="tool_executions")


class AgentMemory(UUIDPKMixin, TimestampMixin, Base):
    """Durable, user-scoped memory.

    A memory is only ever created from something the agent actually observed or
    the user actually stated. ``is_user_correction`` marks a correction the
    farmer made, which outranks anything inferred.
    """

    __tablename__ = "agent_memory"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    farm_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id"), nullable=True, index=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_tasks.id"), nullable=True, index=True
    )
    memory_type: Mapped[AgentMemoryType] = mapped_column(
        Enum(AgentMemoryType, name="agent_memory_type"),
        default=AgentMemoryType.FACT,
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    content: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.6, nullable=False)
    importance: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    is_user_correction: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    access_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentAction(UUIDPKMixin, TimestampMixin, Base):
    """A write the agent wants to make. Nothing here executes without a
    matching approval row when ``requires_approval`` is set."""

    __tablename__ = "agent_actions"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_tasks.id"), nullable=False, index=True
    )
    farm_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id"), nullable=True, index=True
    )
    action_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[AgentActionStatus] = mapped_column(
        Enum(AgentActionStatus, name="agent_action_status"),
        default=AgentActionStatus.PROPOSED,
        nullable=False,
    )
    risk_level: Mapped[ToolRiskLevel] = mapped_column(
        Enum(ToolRiskLevel, name="tool_risk_level"),
        default=ToolRiskLevel.MEDIUM,
        nullable=False,
    )
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    verification_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    task = relationship("AgentTask", back_populates="actions")
    approval = relationship(
        "AgentApproval", back_populates="action", uselist=False, cascade="all, delete-orphan"
    )


class AgentApproval(UUIDPKMixin, TimestampMixin, Base):
    """Human decision gate. The payload snapshot is immutable so the approver
    judged exactly what the agent proposed."""

    __tablename__ = "agent_approvals"

    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_actions.id"), nullable=False, unique=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_tasks.id"), nullable=False, index=True
    )
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approver_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    status: Mapped[AgentApprovalStatus] = mapped_column(
        Enum(AgentApprovalStatus, name="agent_approval_status"),
        default=AgentApprovalStatus.PENDING,
        nullable=False,
        index=True,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    action = relationship("AgentAction", back_populates="approval")


class AgentAlert(UUIDPKMixin, TimestampMixin, Base):
    """A condition worth interrupting the user about, raised by a monitor or
    by a running task."""

    __tablename__ = "agent_alerts"

    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_tasks.id"), nullable=True, index=True
    )
    monitor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_monitoring.id"), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    farm_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id"), nullable=True, index=True
    )
    alert_type: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="info", nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AgentAlertStatus] = mapped_column(
        Enum(AgentAlertStatus, name="agent_alert_status"),
        default=AgentAlertStatus.ACTIVE,
        nullable=False,
    )
    condition_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    evidence: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentMonitor(UUIDPKMixin, TimestampMixin, Base):
    """A standing condition the platform watches for a farm.

    Monitoring is user-toggleable: nothing runs on a schedule unless a row here
    exists and ``enabled`` is true.
    """

    __tablename__ = "agent_monitoring"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    monitor_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    condition: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[AgentMonitorStatus] = mapped_column(
        Enum(AgentMonitorStatus, name="agent_monitor_status"),
        default=AgentMonitorStatus.ACTIVE,
        nullable=False,
    )
    check_interval_minutes: Mapped[int] = mapped_column(Integer, default=360, nullable=False)
    alert_severity: Mapped[str] = mapped_column(String(20), default="moderate", nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class AgentEvaluation(UUIDPKMixin, TimestampMixin, Base):
    """Did the agent actually get it right? Recorded per task so quality can
    be measured instead of assumed."""

    __tablename__ = "agent_evaluations"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_tasks.id"), nullable=False, index=True
    )
    evaluator: Mapped[str] = mapped_column(String(60), nullable=False)  # automated | user | audit
    result: Mapped[AgentEvaluationResult] = mapped_column(
        Enum(AgentEvaluationResult, name="agent_evaluation_result"), nullable=False
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    checks: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_feedback: Mapped[str | None] = mapped_column(String(20), nullable=True)  # helpful|not_helpful
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)