"""add_agent_runtime_tables

Persistence for the BHOOMI agent runtime: sessions, tasks, steps, tool
executions, memory, proposed actions, human approvals, alerts, monitors and
per-task evaluations.

Two details this migration handles explicitly, because autogenerate does not:

* ``spatial_ref_sys`` is owned by the PostGIS extension. Alembic cannot see it
  in the model metadata, so autogenerate offers to drop it. Dropping it would
  destroy the spatial reference data that ``farms.location`` depends on, so it
  is left strictly alone.
* ``agent_phase`` and ``tool_risk_level`` are each used by more than one table.
  A naive ``sa.Enum(...)`` column definition emits ``CREATE TYPE`` once per
  table, and the second one fails with "type already exists". The types are
  therefore created once up front and every column references them with
  ``create_type=False``.

Revision ID: b2f7c41a9d33
Revises: c7f1b9d20e44
Create Date: 2026-10-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b2f7c41a9d33"
down_revision: Union[str, None] = "c7f1b9d20e44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum(name: str, *labels: str) -> postgresql.ENUM:
    return postgresql.ENUM(*labels, name=name, create_type=False)


AGENT_SESSION_STATUS = _enum("agent_session_status", "ACTIVE", "CLOSED", "EXPIRED")
AGENT_TASK_STATUS = _enum(
    "agent_task_status",
    "QUEUED",
    "RUNNING",
    "WAITING_FOR_APPROVAL",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "EXPIRED",
)
AGENT_PHASE = _enum(
    "agent_phase",
    "OBSERVE",
    "UNDERSTAND",
    "PLAN",
    "USE_TOOLS",
    "ANALYZE",
    "ACT",
    "VERIFY",
    "REMEMBER",
    "NOTIFY",
)
AGENT_STEP_STATUS = _enum("agent_step_status", "STARTED", "COMPLETED", "FAILED", "SKIPPED")
TOOL_EXECUTION_STATUS = _enum(
    "tool_execution_status", "STARTED", "SUCCEEDED", "FAILED", "DENIED", "TIMEOUT"
)
TOOL_RISK_LEVEL = _enum("tool_risk_level", "READ_ONLY", "LOW", "MEDIUM", "HIGH")
AGENT_ACTION_STATUS = _enum(
    "agent_action_status",
    "PROPOSED",
    "AWAITING_APPROVAL",
    "APPROVED",
    "REJECTED",
    "EXECUTED",
    "VERIFIED",
    "FAILED",
)
AGENT_APPROVAL_STATUS = _enum(
    "agent_approval_status", "PENDING", "APPROVED", "REJECTED", "EXPIRED", "CANCELLED"
)
AGENT_ALERT_STATUS = _enum("agent_alert_status", "ACTIVE", "ACKNOWLEDGED", "RESOLVED", "DISMISSED")
AGENT_MONITOR_STATUS = _enum("agent_monitor_status", "ACTIVE", "PAUSED", "ERROR")
AGENT_MEMORY_TYPE = _enum(
    "agent_memory_type", "SHORT_TERM", "LONG_TERM", "FACT", "PREFERENCE", "OUTCOME"
)
AGENT_EVALUATION_RESULT = _enum("agent_evaluation_result", "PASSED", "FAILED", "INCONCLUSIVE")

ALL_ENUMS = (
    AGENT_SESSION_STATUS,
    AGENT_TASK_STATUS,
    AGENT_PHASE,
    AGENT_STEP_STATUS,
    TOOL_EXECUTION_STATUS,
    TOOL_RISK_LEVEL,
    AGENT_ACTION_STATUS,
    AGENT_APPROVAL_STATUS,
    AGENT_ALERT_STATUS,
    AGENT_MONITOR_STATUS,
    AGENT_MEMORY_TYPE,
    AGENT_EVALUATION_RESULT,
)


def _id_timestamps() -> list:
    return [
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in ALL_ENUMS:
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "agent_sessions",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=True),
        sa.Column("status", AGENT_SESSION_STATUS, nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("preferred_language", sa.String(length=8), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        *_id_timestamps(),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_sessions_user_id"), "agent_sessions", ["user_id"], unique=False)
    op.create_index(op.f("ix_agent_sessions_farm_id"), "agent_sessions", ["farm_id"], unique=False)

    op.create_table(
        "agent_tasks",
        sa.Column("session_id", sa.UUID(), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("status", AGENT_TASK_STATUS, nullable=False),
        sa.Column("current_phase", AGENT_PHASE, nullable=True),
        sa.Column("requires_approval", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("step_count", sa.Integer(), nullable=False),
        sa.Column("max_steps", sa.Integer(), nullable=False),
        sa.Column("tool_call_count", sa.Integer(), nullable=False),
        sa.Column("max_tool_calls", sa.Integer(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("model_used", sa.String(length=120), nullable=True),
        sa.Column("provider_used", sa.String(length=40), nullable=True),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("missing_data", sa.JSON(), nullable=False),
        sa.Column("conflicts", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        *_id_timestamps(),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_tasks_user_id"), "agent_tasks", ["user_id"], unique=False)
    op.create_index(op.f("ix_agent_tasks_farm_id"), "agent_tasks", ["farm_id"], unique=False)
    op.create_index(op.f("ix_agent_tasks_session_id"), "agent_tasks", ["session_id"], unique=False)
    op.create_index(op.f("ix_agent_tasks_status"), "agent_tasks", ["status"], unique=False)

    op.create_table(
        "agent_steps",
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("phase", AGENT_PHASE, nullable=False),
        sa.Column("status", AGENT_STEP_STATUS, nullable=False),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("missing_data", sa.JSON(), nullable=False),
        sa.Column("conflicts", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("tool_call_count", sa.Integer(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("model_used", sa.String(length=120), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_id_timestamps(),
        sa.ForeignKeyConstraint(["task_id"], ["agent_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_steps_task_id"), "agent_steps", ["task_id"], unique=False)

    op.create_table(
        "tool_executions",
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("step_id", sa.UUID(), nullable=True),
        sa.Column("tool_name", sa.String(length=120), nullable=False),
        sa.Column("tool_version", sa.String(length=40), nullable=True),
        sa.Column("status", TOOL_EXECUTION_STATUS, nullable=False),
        sa.Column("risk_level", TOOL_RISK_LEVEL, nullable=False),
        sa.Column("required_permissions", sa.JSON(), nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=False),
        sa.Column("output_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_id_timestamps(),
        sa.ForeignKeyConstraint(["step_id"], ["agent_steps.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["agent_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tool_executions_task_id"), "tool_executions", ["task_id"], unique=False)
    op.create_index(op.f("ix_tool_executions_step_id"), "tool_executions", ["step_id"], unique=False)
    op.create_index(
        op.f("ix_tool_executions_tool_name"), "tool_executions", ["tool_name"], unique=False
    )

    op.create_table(
        "agent_memory",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=True),
        sa.Column("task_id", sa.UUID(), nullable=True),
        sa.Column("memory_type", AGENT_MEMORY_TYPE, nullable=False),
        sa.Column("key", sa.String(length=160), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.Column("is_user_correction", sa.Boolean(), nullable=False),
        sa.Column("access_count", sa.Integer(), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        *_id_timestamps(),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["agent_tasks.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_memory_user_id"), "agent_memory", ["user_id"], unique=False)
    op.create_index(op.f("ix_agent_memory_farm_id"), "agent_memory", ["farm_id"], unique=False)
    op.create_index(op.f("ix_agent_memory_task_id"), "agent_memory", ["task_id"], unique=False)
    op.create_index(op.f("ix_agent_memory_key"), "agent_memory", ["key"], unique=False)

    op.create_table(
        "agent_actions",
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=True),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", AGENT_ACTION_STATUS, nullable=False),
        sa.Column("risk_level", TOOL_RISK_LEVEL, nullable=False),
        sa.Column("requires_approval", sa.Boolean(), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_result", sa.JSON(), nullable=True),
        sa.Column("verification_status", sa.String(length=30), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        *_id_timestamps(),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["agent_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_actions_task_id"), "agent_actions", ["task_id"], unique=False)
    op.create_index(op.f("ix_agent_actions_farm_id"), "agent_actions", ["farm_id"], unique=False)
    op.create_index(
        op.f("ix_agent_actions_action_type"), "agent_actions", ["action_type"], unique=False
    )

    op.create_table(
        "agent_approvals",
        sa.Column("action_id", sa.UUID(), nullable=False),
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("requested_by_user_id", sa.UUID(), nullable=True),
        sa.Column("approver_user_id", sa.UUID(), nullable=True),
        sa.Column("status", AGENT_APPROVAL_STATUS, nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("payload_snapshot", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        *_id_timestamps(),
        # One approval per action: a second decision is an update of the same
        # gate, never a parallel one.
        sa.ForeignKeyConstraint(["action_id"], ["agent_actions.id"]),
        sa.ForeignKeyConstraint(["approver_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["agent_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("action_id"),
    )
    op.create_index(op.f("ix_agent_approvals_task_id"), "agent_approvals", ["task_id"], unique=False)
    op.create_index(op.f("ix_agent_approvals_status"), "agent_approvals", ["status"], unique=False)
    op.create_index(
        op.f("ix_agent_approvals_approver_user_id"),
        "agent_approvals",
        ["approver_user_id"],
        unique=False,
    )

    # agent_monitoring is created before agent_alerts because the alert table
    # carries a foreign key to it, and Postgres cannot reference a table that
    # does not exist yet.
    op.create_table(
        "agent_monitoring",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("monitor_type", sa.String(length=80), nullable=False),
        sa.Column("condition", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", AGENT_MONITOR_STATUS, nullable=False),
        sa.Column("check_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("alert_severity", sa.String(length=20), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        *_id_timestamps(),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_monitoring_user_id"), "agent_monitoring", ["user_id"], unique=False)
    op.create_index(op.f("ix_agent_monitoring_farm_id"), "agent_monitoring", ["farm_id"], unique=False)
    op.create_index(
        op.f("ix_agent_monitoring_monitor_type"), "agent_monitoring", ["monitor_type"], unique=False
    )

    op.create_table(
        "agent_alerts",
        sa.Column("task_id", sa.UUID(), nullable=True),
        sa.Column("monitor_id", sa.UUID(), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("farm_id", sa.UUID(), nullable=True),
        sa.Column("alert_type", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", AGENT_ALERT_STATUS, nullable=False),
        sa.Column("condition_snapshot", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        *_id_timestamps(),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"]),
        sa.ForeignKeyConstraint(["monitor_id"], ["agent_monitoring.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["agent_tasks.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_alerts_task_id"), "agent_alerts", ["task_id"], unique=False)
    op.create_index(op.f("ix_agent_alerts_monitor_id"), "agent_alerts", ["monitor_id"], unique=False)
    op.create_index(op.f("ix_agent_alerts_user_id"), "agent_alerts", ["user_id"], unique=False)
    op.create_index(op.f("ix_agent_alerts_farm_id"), "agent_alerts", ["farm_id"], unique=False)

    op.create_table(
        "agent_evaluations",
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("evaluator", sa.String(length=60), nullable=False),
        sa.Column("result", AGENT_EVALUATION_RESULT, nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("checks", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("user_feedback", sa.String(length=20), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        *_id_timestamps(),
        sa.ForeignKeyConstraint(["task_id"], ["agent_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agent_evaluations_task_id"), "agent_evaluations", ["task_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_alerts_farm_id"), table_name="agent_alerts")
    op.drop_index(op.f("ix_agent_alerts_user_id"), table_name="agent_alerts")
    op.drop_index(op.f("ix_agent_alerts_monitor_id"), table_name="agent_alerts")
    op.drop_index(op.f("ix_agent_alerts_task_id"), table_name="agent_alerts")
    op.drop_table("agent_alerts")

    op.drop_index(op.f("ix_agent_monitoring_monitor_type"), table_name="agent_monitoring")
    op.drop_index(op.f("ix_agent_monitoring_farm_id"), table_name="agent_monitoring")
    op.drop_index(op.f("ix_agent_monitoring_user_id"), table_name="agent_monitoring")
    op.drop_table("agent_monitoring")

    op.drop_index(op.f("ix_agent_evaluations_task_id"), table_name="agent_evaluations")
    op.drop_table("agent_evaluations")

    op.drop_index(op.f("ix_agent_approvals_approver_user_id"), table_name="agent_approvals")
    op.drop_index(op.f("ix_agent_approvals_status"), table_name="agent_approvals")
    op.drop_index(op.f("ix_agent_approvals_task_id"), table_name="agent_approvals")
    op.drop_table("agent_approvals")

    op.drop_index(op.f("ix_agent_actions_action_type"), table_name="agent_actions")
    op.drop_index(op.f("ix_agent_actions_farm_id"), table_name="agent_actions")
    op.drop_index(op.f("ix_agent_actions_task_id"), table_name="agent_actions")
    op.drop_table("agent_actions")

    op.drop_index(op.f("ix_agent_memory_key"), table_name="agent_memory")
    op.drop_index(op.f("ix_agent_memory_task_id"), table_name="agent_memory")
    op.drop_index(op.f("ix_agent_memory_farm_id"), table_name="agent_memory")
    op.drop_index(op.f("ix_agent_memory_user_id"), table_name="agent_memory")
    op.drop_table("agent_memory")

    op.drop_index(op.f("ix_tool_executions_tool_name"), table_name="tool_executions")
    op.drop_index(op.f("ix_tool_executions_step_id"), table_name="tool_executions")
    op.drop_index(op.f("ix_tool_executions_task_id"), table_name="tool_executions")
    op.drop_table("tool_executions")

    op.drop_index(op.f("ix_agent_steps_task_id"), table_name="agent_steps")
    op.drop_table("agent_steps")

    op.drop_index(op.f("ix_agent_tasks_status"), table_name="agent_tasks")
    op.drop_index(op.f("ix_agent_tasks_session_id"), table_name="agent_tasks")
    op.drop_index(op.f("ix_agent_tasks_farm_id"), table_name="agent_tasks")
    op.drop_index(op.f("ix_agent_tasks_user_id"), table_name="agent_tasks")
    op.drop_table("agent_tasks")

    op.drop_index(op.f("ix_agent_sessions_farm_id"), table_name="agent_sessions")
    op.drop_index(op.f("ix_agent_sessions_user_id"), table_name="agent_sessions")
    op.drop_table("agent_sessions")

    for enum_type in reversed(ALL_ENUMS):
        enum_type.drop(op.get_bind(), checkfirst=True)