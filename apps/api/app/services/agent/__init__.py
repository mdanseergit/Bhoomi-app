"""
BHOOMI agent runtime.

Import order matters here: `tools` registers every callable tool into the
registry singleton, and `loop_runner` depends on that registry being
populated. `AgentService` is the single entry point the API layer uses.
"""
from app.services.agent.executor import ExecutionOutcome, ToolExecutor
from app.services.agent.loop_runner import AgentRunner, LoopResult
from app.services.agent.permissions import scopes_for_role
from app.services.agent.registry import ToolContext, ToolRegistry, ToolResult, ToolSpec, registry
from app.services.agent.task_manager import RepetitionGuard, TaskManager
from app.services.agent.tools import build_default_registry

build_default_registry()


class AgentService:
    """Facade the router talks to.

    Wraps the phase sequence so the API layer never assembles the loop itself,
    and guarantees the task is persisted with its final state even when a
    phase raises.
    """

    def __init__(self, db):
        self.db = db
        self.tasks = TaskManager(db)
        self.runner = AgentRunner(db)

    def catalogue(self, user) -> list[dict]:
        return registry.catalogue_for_model(scopes_for_role(user.role))

    def chat(
        self,
        *,
        user,
        query: str,
        farm,
        session_id: str | None,
        language: str = "en",
        enabled_tools: list[str] | None = None,
    ) -> LoopResult:
        session = self.tasks.get_or_create_session(
            user, session_id=session_id, farm_id=str(farm.id) if farm else None, language=language
        )
        task = self.tasks.create_task(
            session=session, user=user, query=query, language=language
        )
        task = self.tasks.start_task(task)
        try:
            result = self.runner.run(
                task=task,
                user=user,
                farm=farm,
                query=query,
                language=language,
                enabled_tools=enabled_tools,
            )
        except Exception as exc:  # noqa: BLE001 - the task must not stay 'running'
            self.tasks.fail_task(task, f"The agent run could not be completed: {type(exc).__name__}.")
            raise

        self.tasks.complete_task(
            task,
            response=result.answer,
            confidence=result.confidence,
            evidence=result.evidence,
            missing_data=result.missing_data,
            conflicts=result.conflicts,
            model_used=result.model_used,
            provider_used=result.provider_used,
            fallback_used=result.fallback_used,
        )
        if result.requires_approval:
            self.tasks.halt_for_approval(task)
        self.db.refresh(task)
        result.task_id = str(task.id)
        result.session_id = str(session.id)
        result.status = task.status.value
        return result


__all__ = [
    "AgentService",
    "AgentRunner",
    "ExecutionOutcome",
    "LoopResult",
    "RepetitionGuard",
    "TaskManager",
    "ToolContext",
    "ToolExecutor",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
    "registry",
    "scopes_for_role",
]