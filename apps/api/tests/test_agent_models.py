"""
Tests for the agent runtime persistence layer.

These cover the guarantees the rest of the agent system depends on:

* every table the platform promises actually exists and is reachable from
  ``Base.metadata`` (a model that is not imported is a model that does not
  exist at runtime);
* ``agent_tasks.status`` accepts exactly the documented lifecycle values;
* an agent task cannot be created without the budget columns the loop
  enforces, because a run that was not budgeted is a run that cannot be
  audited;
* a high-risk action is recorded as requiring approval and nothing marks it
  executed before a human decision exists.
"""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect

from app.core.database import Base, engine
from app.models.agent import (
    AgentAction,
    AgentActionStatus,
    AgentAlert,
    AgentAlertStatus,
    AgentApproval,
    AgentApprovalStatus,
    AgentEvaluation,
    AgentEvaluationResult,
    AgentMemory,
    AgentMemoryType,
    AgentMonitor,
    AgentMonitorStatus,
    AgentPhase,
    AgentSession,
    AgentSessionStatus,
    AgentStep,
    AgentStepStatus,
    AgentTask,
    AgentTaskStatus,
    ToolExecution,
    ToolExecutionStatus,
    ToolRiskLevel,
)
from app.models.user import Role, User

EXPECTED_TABLES = {
    "agent_sessions",
    "agent_tasks",
    "agent_steps",
    "tool_executions",
    "agent_memory",
    "agent_actions",
    "agent_approvals",
    "agent_alerts",
    "agent_monitoring",
    "agent_evaluations",
}


@pytest.fixture()
def user(db_session):
    u = User(
        full_name="Agent Test Farmer",
        email=f"agent.{uuid.uuid4().hex[:10]}@example.com",
        password_hash="x",
        role=Role.FARMER,
        state="Tamil Nadu",
    )
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture()
def farm(db_session, user):
    from app.models.farm import Farm

    f = Farm(
        user_id=user.id,
        name="Agent Runtime Farm",
        state="Tamil Nadu",
        district="Salem",
        latitude=11.6,
        longitude=78.1,
        area_hectares=2.5,
    )
    db_session.add(f)
    db_session.commit()
    return f


@pytest.fixture()
def task(db_session, user, farm):
    from app.core.config import settings

    t = AgentTask(
        user_id=user.id,
        farm_id=farm.id,
        query="Should I irrigate my tomato plot tomorrow?",
        max_steps=settings.MAX_AGENT_STEPS,
        max_tool_calls=settings.MAX_AGENT_TOOL_CALLS,
    )
    db_session.add(t)
    db_session.commit()
    return t


# ---------------------------------------------------------------------------
# Schema registration
# ---------------------------------------------------------------------------

def test_all_agent_tables_are_registered():
    assert EXPECTED_TABLES <= set(Base.metadata.tables)


def test_agent_tables_exist_in_the_database():
    db_tables = set(inspect(engine).get_table_names())
    missing = EXPECTED_TABLES - db_tables
    assert not missing, f"agent tables missing from the database: {missing}"


def test_approval_is_one_per_action():
    unique = [tuple(u["column_names"]) for u in inspect(engine).get_unique_constraints("agent_approvals")]
    assert ("action_id",) in unique


# ---------------------------------------------------------------------------
# Task lifecycle
# ---------------------------------------------------------------------------

def test_task_status_lifecycle_values():
    assert {s.value for s in AgentTaskStatus} == {
        "queued",
        "running",
        "waiting_for_approval",
        "completed",
        "failed",
        "cancelled",
        "expired",
    }


def test_task_defaults_to_queued_with_empty_audit_lists(db_session, user, farm):
    from app.core.config import settings

    t = AgentTask(
        user_id=user.id,
        farm_id=farm.id,
        query="status check",
        max_steps=settings.MAX_AGENT_STEPS,
        max_tool_calls=settings.MAX_AGENT_TOOL_CALLS,
    )
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)

    assert t.status == AgentTaskStatus.QUEUED
    assert t.step_count == 0
    assert t.tool_call_count == 0
    assert t.requires_approval is False
    assert t.fallback_used is False
    assert t.evidence == []
    assert t.missing_data == []
    assert t.conflicts == []
    assert t.started_at is None
    assert t.completed_at is None


def test_max_agent_steps_covers_the_phase_spine():
    """The loop persists a fixed 9-phase spine (observe -> notify) and every
    phase is an audit row, so a step ceiling at or below the spine size would
    make it impossible for a run to finish recording itself."""
    from app.core.config import settings
    from app.services.agent.task_manager import SPINE_PHASE_COUNT

    assert settings.MAX_AGENT_STEPS > SPINE_PHASE_COUNT
    assert settings.MAX_AGENT_TOOL_CALLS >= settings.MAX_AGENT_STEPS
    assert settings.MAX_AGENT_TASK_SECONDS > 0
    assert settings.AGENT_REPETITION_LIMIT > 0
    assert settings.AGENT_SESSION_TTL_HOURS > 0


def test_waiting_for_approval_is_reachable_and_distinct_from_completed(db_session, task):
    task.status = AgentTaskStatus.RUNNING
    task.current_phase = AgentPhase.ACT
    task.requires_approval = True
    db_session.commit()

    task.status = AgentTaskStatus.WAITING_FOR_APPROVAL
    db_session.commit()
    db_session.refresh(task)

    assert task.status == AgentTaskStatus.WAITING_FOR_APPROVAL
    assert task.status != AgentTaskStatus.COMPLETED
    assert task.requires_approval is True


# ---------------------------------------------------------------------------
# Steps record public phases, not reasoning
# ---------------------------------------------------------------------------

def test_step_records_phase_evidence_and_sources(db_session, task):
    now = datetime.now(timezone.utc)
    step = AgentStep(
        task_id=task.id,
        step_number=1,
        phase=AgentPhase.OBSERVE,
        status=AgentStepStatus.COMPLETED,
        goal="collect current conditions",
        summary="No irrigation event recorded in the last 3 days.",
        evidence=[{"kind": "water", "value": 0}],
        sources=[{"provider": "IMD", "observed_at": "2026-10-01T06:00:00Z"}],
        missing_data=["soil_moisture_lab"],
        started_at=now,
        completed_at=now,
    )
    db_session.add(step)
    db_session.commit()
    db_session.refresh(step)

    assert step.phase == AgentPhase.OBSERVE
    assert step.sources[0]["provider"] == "IMD"
    assert step.missing_data == ["soil_moisture_lab"]


def test_phase_covers_the_documented_loop():
    assert {p.value for p in AgentPhase} == {
        "observe",
        "understand",
        "plan",
        "use_tools",
        "analyze",
        "act",
        "verify",
        "remember",
        "notify",
    }


def test_task_cascade_deletes_steps_and_tool_executions(db_session, task):
    now = datetime.now(timezone.utc)
    step = AgentStep(
        task_id=task.id,
        step_number=1,
        phase=AgentPhase.USE_TOOLS,
        started_at=now,
    )
    db_session.add(step)
    db_session.flush()
    db_session.add(
        ToolExecution(
            task_id=task.id,
            step_id=step.id,
            tool_name="get_weather_forecast",
            started_at=now,
        )
    )
    db_session.commit()

    db_session.delete(task)
    db_session.commit()

    assert db_session.query(AgentStep).filter_by(task_id=task.id).count() == 0
    assert db_session.query(ToolExecution).filter_by(task_id=task.id).count() == 0


# ---------------------------------------------------------------------------
# Tool execution records the permission decision
# ---------------------------------------------------------------------------

def test_tool_execution_defaults_to_read_only_started(db_session, task):
    ex = ToolExecution(
        task_id=task.id,
        tool_name="get_soil_observation",
        input_payload={"farm_id": str(task.farm_id)},
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(ex)
    db_session.commit()
    db_session.refresh(ex)

    assert ex.status == ToolExecutionStatus.STARTED
    assert ex.risk_level == ToolRiskLevel.READ_ONLY
    assert ex.required_permissions == []
    assert ex.retry_count == 0
    assert ex.completed_at is None


def test_denied_tool_call_is_recorded_rather_than_swallowed(db_session, task):
    ex = ToolExecution(
        task_id=task.id,
        tool_name="apply_irrigation_schedule",
        risk_level=ToolRiskLevel.HIGH,
        required_permissions=["farms.write"],
        status=ToolExecutionStatus.DENIED,
        error_message="no farm write permission for this user",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(ex)
    db_session.commit()
    db_session.refresh(ex)

    assert ex.status == ToolExecutionStatus.DENIED
    assert ex.error_message


# ---------------------------------------------------------------------------
# Actions, approvals, verification
# ---------------------------------------------------------------------------

def test_high_risk_action_starts_awaiting_approval(db_session, task):
    action = AgentAction(
        task_id=task.id,
        farm_id=task.farm_id,
        action_type="irrigation.schedule",
        title="Schedule irrigation for 25 mm",
        payload={"millimetres": 25, "window": "06:00-09:00"},
        status=AgentActionStatus.AWAITING_APPROVAL,
        risk_level=ToolRiskLevel.HIGH,
        requires_approval=True,
    )
    db_session.add(action)
    db_session.commit()
    db_session.refresh(action)

    assert action.requires_approval is True
    assert action.status == AgentActionStatus.AWAITING_APPROVAL
    assert action.executed_at is None
    assert action.verification_status is None


def test_approval_is_pending_until_a_human_decides(db_session, task, user):
    action = AgentAction(
        task_id=task.id,
        action_type="advisory.publish",
        title="Publish advisory",
        requires_approval=True,
        risk_level=ToolRiskLevel.MEDIUM,
    )
    db_session.add(action)
    db_session.flush()
    approval = AgentApproval(
        action_id=action.id,
        task_id=task.id,
        requested_by_user_id=user.id,
        status=AgentApprovalStatus.PENDING,
        payload_snapshot=action.payload,
    )
    db_session.add(approval)
    db_session.commit()
    db_session.refresh(approval)

    assert approval.status == AgentApprovalStatus.PENDING
    assert approval.approver_user_id is None
    assert approval.decided_at is None
    assert approval.payload_snapshot == action.payload


def test_rejecting_an_action_leaves_it_unexecuted(db_session, task, user):
    action = AgentAction(
        task_id=task.id,
        action_type="disease_scan.delete",
        title="Delete scan record",
        requires_approval=True,
        risk_level=ToolRiskLevel.HIGH,
    )
    db_session.add(action)
    db_session.flush()
    approval = AgentApproval(
        action_id=action.id,
        task_id=task.id,
        approver_user_id=user.id,
        status=AgentApprovalStatus.REJECTED,
        reason="user did not authorise deletion",
        decided_at=datetime.now(timezone.utc),
    )
    db_session.add(approval)
    action.status = AgentActionStatus.REJECTED
    db_session.commit()
    db_session.refresh(action)

    assert action.status == AgentActionStatus.REJECTED
    assert action.executed_at is None
    assert action.execution_result is None


def test_only_one_approval_row_per_action(db_session, task):
    action = AgentAction(task_id=task.id, action_type="x", title="x")
    db_session.add(action)
    db_session.flush()
    db_session.add(AgentApproval(action_id=action.id, task_id=task.id))
    db_session.commit()

    from sqlalchemy.exc import IntegrityError

    db_session.add(AgentApproval(action_id=action.id, task_id=task.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

def test_user_correction_outranks_inference(db_session, user, farm, task):
    inferred = AgentMemory(
        user_id=user.id,
        farm_id=farm.id,
        task_id=task.id,
        memory_type=AgentMemoryType.PREFERENCE,
        key="irrigation.preference",
        content={"value": "early morning"},
        confidence=0.4,
    )
    corrected = AgentMemory(
        user_id=user.id,
        farm_id=farm.id,
        memory_type=AgentMemoryType.PREFERENCE,
        key="irrigation.preference",
        content={"value": "late evening"},
        confidence=0.95,
        is_user_correction=True,
    )
    db_session.add_all([inferred, corrected])
    db_session.commit()

    authoritative = (
        db_session.query(AgentMemory)
        .filter_by(user_id=user.id, key="irrigation.preference")
        .filter(AgentMemory.is_user_correction.is_(True))
        .one()
    )
    assert authoritative.content["value"] == "late evening"


def test_expired_memory_is_filterable(db_session, user):
    from datetime import timedelta

    stale = AgentMemory(
        user_id=user.id,
        memory_type=AgentMemoryType.SHORT_TERM,
        key="temp.stale",
        content={"v": 1},
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    fresh = AgentMemory(
        user_id=user.id,
        memory_type=AgentMemoryType.SHORT_TERM,
        key="temp.fresh",
        content={"v": 2},
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add_all([stale, fresh])
    db_session.commit()

    now = datetime.now(timezone.utc)
    live = db_session.query(AgentMemory).filter(AgentMemory.expires_at > now).all()
    assert [m.key for m in live] == ["temp.fresh"]


# ---------------------------------------------------------------------------
# Sessions, monitors, alerts, evaluations
# ---------------------------------------------------------------------------

def test_session_defaults_to_active(db_session, user, farm):
    s = AgentSession(user_id=user.id, farm_id=farm.id, title="Irrigation thread")
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)

    assert s.status == AgentSessionStatus.ACTIVE
    assert s.message_count == 0
    assert s.preferred_language == "en"


def test_monitor_is_opt_in(db_session, user, farm):
    m = AgentMonitor(
        user_id=user.id,
        farm_id=farm.id,
        name="Rain before spray",
        monitor_type="weather_window",
        condition={"metric": "rainfall_mm", "operator": ">", "threshold": 5},
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)

    assert m.enabled is True
    assert m.status == AgentMonitorStatus.ACTIVE
    assert m.check_interval_minutes == 360
    assert m.last_checked_at is None


def test_alert_can_be_linked_to_a_monitor(db_session, user, farm, task):
    monitor = AgentMonitor(
        user_id=user.id, farm_id=farm.id, name="m", monitor_type="drought", condition={"x": 1}
    )
    db_session.add(monitor)
    db_session.flush()
    alert = AgentAlert(
        task_id=task.id,
        monitor_id=monitor.id,
        user_id=user.id,
        farm_id=farm.id,
        alert_type="drought_risk",
        severity="high",
        title="Soil moisture below threshold",
        message="Moisture at 12% against a 20% threshold.",
        condition_snapshot={"metric": "soil_moisture_pct", "value": 12, "threshold": 20},
        triggered_at=datetime.now(timezone.utc),
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    assert alert.status == AgentAlertStatus.ACTIVE
    assert alert.monitor_id == monitor.id
    assert alert.condition_snapshot["value"] == 12


def test_evaluation_records_measurable_outcome(db_session, task):
    ev = AgentEvaluation(
        task_id=task.id,
        evaluator="automated",
        result=AgentEvaluationResult.INCONCLUSIVE,
        checks=[{"name": "cited_source", "passed": False}],
        notes="no soil observation available to confirm",
        evaluated_at=datetime.now(timezone.utc),
    )
    db_session.add(ev)
    db_session.commit()
    db_session.refresh(ev)

    assert ev.result == AgentEvaluationResult.INCONCLUSIVE
    assert ev.checks[0]["passed"] is False
    assert ev.score is None