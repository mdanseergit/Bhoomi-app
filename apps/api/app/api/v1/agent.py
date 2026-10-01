"""
Agent API surface.

Every route is authenticated. Farm-scoped routes resolve the farm first and
apply the same ownership rule the rest of the platform uses, so the agent
cannot become a way around it. The chat endpoint sits in the ``ai`` rate-limit
bucket because a single message can trigger several provider calls.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.rate_limit import rate_limit
from app.models.agent import (
    AgentAction,
    AgentActionStatus,
    AgentAlert,
    AgentApproval,
    AgentApprovalStatus,
    AgentMemory,
    AgentMonitor,
    AgentMonitorStatus,
    AgentStep,
    AgentTask,
    AgentTaskStatus,
    ToolExecution,
)
from app.models.farm import Farm
from app.models.user import Role, User
from app.repositories.farm_repository import FarmRepository
from app.schemas.agent import (
    AgentAlertOut,
    AgentApprovalDecision,
    AgentApprovalOut,
    AgentChatRequest,
    AgentChatResponse,
    AgentMemoryOut,
    AgentMonitorIn,
    AgentMonitorOut,
    AgentStepOut,
    AgentTaskOut,
    AgentToolExecutionOut,
)
from app.services.agent import AgentService, registry
from app.services.agent.permissions import scopes_for_role
from app.services.agent.task_manager import TERMINAL_TASK_STATUSES, TaskManager

router = APIRouter(prefix="/agent", tags=["agent"])

farm_repo = FarmRepository()


def _agent(db: Session) -> AgentService:
    return AgentService(db)


def _resolve_farm(db: Session, user: User, farm_id: str | None) -> Farm | None:
    """Returns the farm, or None when the caller did not name one.

    A farm the caller may not see is reported as not found rather than
    forbidden: telling an unauthorised caller that a farm id is real would leak
    the existence of another farmer's land.
    """
    if not farm_id:
        return None
    farm = farm_repo.get(db, farm_id)
    if farm is None:
        raise NotFoundError("Farm not found.")
    if user.role in (Role.PLATFORM_ADMIN, Role.AGRONOMIST, Role.STATE_ADMIN):
        return farm
    if str(farm.user_id) != str(user.id):
        raise NotFoundError("Farm not found.")
    return farm


def _owned_task(db: Session, user: User, task_id: str) -> AgentTask:
    task = db.get(AgentTask, task_id)
    if task is None:
        raise NotFoundError("Agent task not found.")
    if str(task.user_id) != str(user.id):
        raise NotFoundError("Agent task not found.")
    return task


@router.post(
    "/chat",
    response_model=AgentChatResponse,
    dependencies=[Depends(rate_limit("ai"))],
)
def chat(
    payload: AgentChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = _agent(db)
    farm = _resolve_farm(db, user, payload.farm_id)

    disabled = {t.strip() for t in payload.disabled_tools if t and t.strip()}
    known = {spec.name for spec in registry.list_tools()}
    unknown = disabled - known
    if unknown:
        raise NotFoundError(f"Unknown tool(s): {', '.join(sorted(unknown))}.")

    granted = scopes_for_role(user.role)
    permitted = {
        spec.name
        for spec in registry.list_tools(enabled_only=True)
        if set(spec.required_permissions).issubset(granted)
    }
    # `None` means "every permitted tool". An explicit empty list means the
    # caller opted out of all of them, which is a different request and must not
    # silently re-enable the whole catalogue.
    enabled = sorted(permitted - disabled) if disabled else sorted(permitted)

    result = service.chat(
        user=user,
        query=payload.message,
        farm=farm,
        session_id=payload.session_id,
        language=payload.language,
        enabled_tools=enabled,
    )

    from app.schemas.agent import BudgetOut

    return AgentChatResponse(
        task_id=result.task_id or "",
        session_id=result.session_id or "",
        status=result.status or "completed",
        answer=result.answer,
        confidence=result.confidence,
        model_used=result.model_used,
        provider_used=result.provider_used,
        fallback_used=result.fallback_used,
        requires_approval=result.requires_approval,
        evidence=result.evidence,
        sources=result.sources,
        missing_data=result.missing_data,
        conflicts=result.conflicts,
        tool_calls=result.tool_calls,
        phases=result.phases,
        budget=BudgetOut(**result.budget),
        warning=result.warning,
    )


@router.get("/tools")
def list_tools(user: User = Depends(get_current_user)):
    """The tools this caller could actually run. Not the full catalogue."""
    granted = scopes_for_role(user.role)
    return [
        spec.describe()
        for spec in sorted(registry.list_tools(enabled_only=True), key=lambda s: s.name)
        if set(spec.required_permissions).issubset(granted)
    ]


@router.get("/tasks", response_model=list[AgentTaskOut])
def list_tasks(
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(AgentTask)
        .filter(AgentTask.user_id == user.id)
        .order_by(AgentTask.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_task_out(t) for t in rows]


@router.get("/tasks/{task_id}", response_model=AgentTaskOut)
def get_task(task_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _task_out(_owned_task(db, user, task_id))


@router.get("/tasks/{task_id}/activity")
def get_task_activity(task_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Phases and tool calls for one task.

    This is the audit view the chat bar renders: what ran, in which phase, for
    how long, and what it could not access. It contains no hidden reasoning --
    only the same public summaries the task stores.
    """
    task = _owned_task(db, user, task_id)
    steps = (
        db.query(AgentStep)
        .filter(AgentStep.task_id == task.id)
        .order_by(AgentStep.step_number.asc())
        .all()
    )
    executions = (
        db.query(ToolExecution)
        .filter(ToolExecution.task_id == task.id)
        .order_by(ToolExecution.started_at.asc())
        .all()
    )
    approvals = (
        db.query(AgentApproval).filter(AgentApproval.task_id == task.id).all()
    )
    return {
        "task_id": str(task.id),
        "status": task.status.value,
        "query": task.query,
        "response": task.response,
        "confidence": task.confidence,
        "steps": [AgentStepOut(**_step_payload(s)) for s in steps],
        "tool_executions": [AgentToolExecutionOut(**_execution_payload(e)) for e in executions],
        "approvals": [AgentApprovalOut(**_approval_payload(a)) for a in approvals],
        "budget": TaskManager(db).budget(task).to_dict(),
    }


@router.get("/approvals", response_model=list[AgentApprovalOut])
def list_approvals(
    status: str | None = Query(default="pending", pattern="^(pending|approved|rejected|expired|cancelled)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(AgentApproval).join(AgentAction, AgentApproval.action_id == AgentAction.id)
    query = query.filter(AgentApproval.status == AgentApprovalStatus(status))
    if user.role not in (Role.AGRONOMIST, Role.STATE_ADMIN, Role.PLATFORM_ADMIN):
        # A farmer only ever sees approvals raised against their own actions.
        owned = (
            db.query(AgentTask.id)
            .filter(AgentTask.user_id == user.id)
            .subquery()
        )
        query = query.filter(AgentApproval.task_id.in_(owned))
    return [_approval_payload(a) for a in query.order_by(AgentApproval.created_at.desc()).limit(100).all()]


@router.post("/approvals/{approval_id}/decide", response_model=AgentApprovalOut)
def decide_approval(
    approval_id: str,
    payload: AgentApprovalDecision,
    user: User = Depends(require_roles(Role.AGRONOMIST, Role.STATE_ADMIN, Role.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
):
    approval = db.get(AgentApproval, approval_id)
    if approval is None:
        raise NotFoundError("Approval not found.")
    if approval.status != AgentApprovalStatus.PENDING:
        raise ForbiddenError(f"This approval was already {approval.status.value}.")

    action = db.get(AgentAction, approval.action_id)
    approval.status = AgentApprovalStatus.APPROVED if payload.approve else AgentApprovalStatus.REJECTED
    approval.approver_user_id = user.id
    approval.decided_at = datetime.now(timezone.utc)
    if payload.note:
        approval.reason = payload.note
    if action is not None:
        action.status = AgentActionStatus.APPROVED if payload.approve else AgentActionStatus.REJECTED

    # Approving an action does not execute it. Execution is a separate step
    # that must independently verify the write, so a decision can never be
    # mistaken for a completed change.
    task = db.get(AgentTask, approval.task_id)
    if task is not None and task.status.value == "waiting_for_approval":
        task.status = AgentTaskStatus.COMPLETED
        task.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(approval)
    return _approval_payload(approval)


@router.get("/memory", response_model=list[AgentMemoryOut])
def list_memory(
    limit: int = Query(default=25, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = TaskManager(db).recall(user_id=user.id, limit=limit)
    return [
        AgentMemoryOut(
            id=str(m.id),
            memory_type=m.memory_type.value,
            key=m.key,
            content=m.content,
            source=m.source,
            confidence=m.confidence,
            importance=m.importance,
            is_user_correction=m.is_user_correction,
            created_at=m.created_at.isoformat(),
        )
        for m in rows
    ]


@router.delete("/memory/{memory_id}", status_code=204)
def forget_memory(
    memory_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    memory = db.get(AgentMemory, memory_id)
    if memory is None or str(memory.user_id) != str(user.id):
        raise NotFoundError("Memory not found.")
    db.delete(memory)
    db.commit()
    return None


@router.get("/monitors", response_model=list[AgentMonitorOut])
def list_monitors(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(AgentMonitor)
        .filter(AgentMonitor.user_id == user.id)
        .order_by(AgentMonitor.created_at.desc())
        .all()
    )
    return [_monitor_out(m) for m in rows]


@router.post("/monitors", response_model=AgentMonitorOut, status_code=201)
def create_monitor(
    payload: AgentMonitorIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    farm = _resolve_farm(db, user, payload.farm_id)
    monitor = AgentMonitor(
        user_id=user.id,
        farm_id=farm.id if farm else None,
        name=payload.name,
        monitor_type=payload.monitor_type,
        condition=payload.condition,
        check_interval_minutes=payload.check_interval_minutes,
        alert_severity=payload.alert_severity,
        enabled=True,
        status=AgentMonitorStatus.ACTIVE,
    )
    db.add(monitor)
    db.commit()
    db.refresh(monitor)
    return _monitor_out(monitor)


@router.patch("/monitors/{monitor_id}", response_model=AgentMonitorOut)
def toggle_monitor(
    monitor_id: str,
    enabled: bool = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    monitor = db.get(AgentMonitor, monitor_id)
    if monitor is None or str(monitor.user_id) != str(user.id):
        raise NotFoundError("Monitor not found.")
    monitor.enabled = enabled
    monitor.status = AgentMonitorStatus.ACTIVE if enabled else AgentMonitorStatus.PAUSED
    db.commit()
    db.refresh(monitor)
    return _monitor_out(monitor)


@router.get("/alerts", response_model=list[AgentAlertOut])
def list_alerts(
    limit: int = Query(default=25, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(AgentAlert)
        .filter(AgentAlert.user_id == user.id)
        .order_by(AgentAlert.triggered_at.desc())
        .limit(limit)
        .all()
    )
    return [
        AgentAlertOut(
            id=str(a.id),
            alert_type=a.alert_type,
            severity=a.severity,
            title=a.title,
            message=a.message,
            status=a.status.value,
            farm_id=str(a.farm_id) if a.farm_id else None,
            triggered_at=a.triggered_at.isoformat(),
            acknowledged_at=a.acknowledged_at.isoformat() if a.acknowledged_at else None,
        )
        for a in rows
    ]


# --- serialisers ----------------------------------------------------------


def _task_out(t: AgentTask) -> AgentTaskOut:
    return AgentTaskOut(
        id=str(t.id),
        session_id=str(t.session_id) if t.session_id else None,
        farm_id=str(t.farm_id) if t.farm_id else None,
        query=t.query,
        response=t.response,
        status=t.status.value,
        current_phase=t.current_phase.value if t.current_phase else None,
        confidence=t.confidence,
        step_count=t.step_count,
        max_steps=t.max_steps,
        tool_call_count=t.tool_call_count,
        max_tool_calls=t.max_tool_calls,
        requires_approval=t.requires_approval,
        model_used=t.model_used,
        missing_data=t.missing_data or [],
        created_at=t.created_at.isoformat(),
        completed_at=t.completed_at.isoformat() if t.completed_at else None,
    )


def _step_payload(s: AgentStep) -> dict:
    return {
        "id": str(s.id),
        "step_number": s.step_number,
        "phase": s.phase.value,
        "status": s.status.value,
        "goal": s.goal,
        "summary": s.summary,
        "evidence": s.evidence or [],
        "sources": s.sources or [],
        "missing_data": s.missing_data or [],
        "confidence": s.confidence,
        "tool_call_count": s.tool_call_count,
        "model_used": s.model_used,
        "duration_ms": s.duration_ms,
        "created_at": s.created_at.isoformat(),
    }


def _execution_payload(e: ToolExecution) -> dict:
    output = e.output_payload or {}
    return {
        "id": str(e.id),
        "tool_name": e.tool_name,
        "tool_version": e.tool_version,
        "status": e.status.value,
        "risk_level": e.risk_level.value,
        "required_permissions": e.required_permissions or [],
        "summary": output.get("summary"),
        "error_message": e.error_message,
        "duration_ms": e.duration_ms,
        "source": e.source,
        "started_at": e.started_at.isoformat(),
    }


def _approval_payload(a: AgentApproval) -> dict:
    action: AgentAction | None = a.action
    return {
        "id": str(a.id),
        "action_id": str(a.action_id),
        "task_id": str(a.task_id),
        "status": a.status.value,
        "reason": a.reason,
        "action_title": action.title if action else None,
        "action_description": action.description if action else None,
        "action_type": action.action_type if action else None,
        "risk_level": action.risk_level.value if action else None,
        "payload_snapshot": a.payload_snapshot or {},
        "requested_at": a.created_at.isoformat(),
        "decided_at": a.decided_at.isoformat() if a.decided_at else None,
    }


def _monitor_out(m: AgentMonitor) -> AgentMonitorOut:
    return AgentMonitorOut(
        id=str(m.id),
        farm_id=str(m.farm_id),
        name=m.name,
        monitor_type=m.monitor_type,
        condition=m.condition or {},
        enabled=m.enabled,
        status=m.status.value,
        check_interval_minutes=m.check_interval_minutes,
        alert_severity=m.alert_severity,
        last_checked_at=m.last_checked_at.isoformat() if m.last_checked_at else None,
        created_at=m.created_at.isoformat(),
    )


__all__ = ["router", "TERMINAL_TASK_STATUSES"]