from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _AgentSchema(BaseModel):
    # `model_used` names the language model that answered, which is a field
    # name here, not a Pydantic namespace collision.
    model_config = ConfigDict(protected_namespaces=())


class AgentChatRequest(_AgentSchema):
    message: str = Field(min_length=1, max_length=2000)
    farm_id: str | None = None
    session_id: str | None = None
    language: str = Field(default="en", max_length=8)
    # Optional opt-out from tools the caller is otherwise permitted to use, so
    # a user can force an answer from existing context only.
    disabled_tools: list[str] = Field(default_factory=list)


class ToolCallOut(BaseModel):
    tool: str
    status: str
    summary: str
    duration_ms: int
    execution_id: str | None = None
    reason: str | None = None


class PhaseOut(BaseModel):
    step_number: int
    phase: str
    status: str
    summary: str | None = None
    duration_ms: int | None = None


class SourceOut(BaseModel):
    domain: str | None = None
    provider: str | None = None
    status: str | None = None


class BudgetOut(BaseModel):
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
    limit_reason: str | None = None


class AgentChatResponse(_AgentSchema):
    task_id: str
    session_id: str
    status: str
    answer: str
    confidence: float
    model_used: str | None = None
    provider_used: str | None = None
    fallback_used: bool = False
    requires_approval: bool = False
    evidence: list[dict] = Field(default_factory=list)
    sources: list[SourceOut] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    conflicts: list[dict] = Field(default_factory=list)
    tool_calls: list[ToolCallOut] = Field(default_factory=list)
    phases: list[PhaseOut] = Field(default_factory=list)
    budget: BudgetOut
    warning: str | None = None


class AgentTaskOut(_AgentSchema):
    id: str
    session_id: str | None
    farm_id: str | None
    query: str
    response: str | None
    status: str
    current_phase: str | None
    confidence: float | None
    step_count: int
    max_steps: int
    tool_call_count: int
    max_tool_calls: int
    requires_approval: bool
    model_used: str | None
    missing_data: list[str]
    created_at: str
    completed_at: str | None


class AgentStepOut(_AgentSchema):
    id: str
    step_number: int
    phase: str
    status: str
    goal: str | None
    summary: str | None
    evidence: list[dict]
    sources: list[dict]
    missing_data: list[str]
    confidence: float | None
    tool_call_count: int
    model_used: str | None
    duration_ms: int | None
    created_at: str


class AgentToolExecutionOut(BaseModel):
    id: str
    tool_name: str
    tool_version: str | None
    status: str
    risk_level: str
    required_permissions: list[str]
    summary: str | None
    error_message: str | None
    duration_ms: int | None
    source: str | None
    started_at: str


class AgentApprovalOut(BaseModel):
    id: str
    action_id: str
    task_id: str
    status: str
    reason: str | None
    action_title: str | None
    action_description: str | None
    action_type: str | None
    risk_level: str | None
    payload_snapshot: dict[str, Any]
    requested_at: str
    decided_at: str | None


class AgentApprovalDecision(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=1000)


class AgentMemoryOut(BaseModel):
    id: str
    memory_type: str
    key: str
    content: dict
    source: str | None
    confidence: float
    importance: float
    is_user_correction: bool
    created_at: str


class AgentMonitorIn(BaseModel):
    farm_id: str
    name: str = Field(min_length=1, max_length=160)
    monitor_type: str = Field(pattern="^(weather|soil|vegetation|disease|advisory)$")
    condition: dict[str, Any] = Field(default_factory=dict)
    check_interval_minutes: int = Field(default=360, ge=5, le=10080)
    alert_severity: str = Field(default="moderate", pattern="^(info|low|moderate|high|critical)$")


class AgentMonitorOut(BaseModel):
    id: str
    farm_id: str
    name: str
    monitor_type: str
    condition: dict
    enabled: bool
    status: str
    check_interval_minutes: int
    alert_severity: str
    last_checked_at: str | None
    created_at: str


class AgentAlertOut(BaseModel):
    id: str
    alert_type: str
    severity: str
    title: str
    message: str
    status: str
    farm_id: str | None
    triggered_at: str
    acknowledged_at: str | None