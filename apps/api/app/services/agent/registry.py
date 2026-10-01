"""
The agent tool registry.

A tool is the *only* way the agent reaches outside itself. Nothing here
executes SQL, spawns a process, reads a file, or fetches an arbitrary URL:
each entry names a real BHOOMI service, declares the permission scopes it
needs, the risk of running it, and a pydantic schema for its input and
output. A tool that is not registered cannot be called, which is what makes
the agent's reach auditable rather than open-ended.

Risk drives two things: audit depth (every call is recorded either way) and
whether a call needs explicit human approval. Anything above
``ToolRiskLevel.MEDIUM`` is a write and is gated by
``settings.AGENT_HIGH_RISK_APPROVAL_REQUIRED``.
"""
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from app.core.logging import get_logger
from app.models.agent import ToolRiskLevel

logger = get_logger("bhoomi.agent.registry")


# --- Permission scopes ---------------------------------------------------
# Coarse-grained capabilities checked against the caller's role before a tool
# is allowed to run. Fine-grained farm ownership is enforced separately by
# the executor, which re-checks the resource against the requesting user.
SCOPE_FARM_READ = "farm:read"
SCOPE_FARM_WRITE = "farm:write"
SCOPE_ADVISORY_READ = "advisory:read"
SCOPE_ADVISORY_WRITE = "advisory:write"
SCOPE_WEATHER_READ = "weather:read"
SCOPE_SOIL_READ = "soil:read"
SCOPE_SATELLITE_READ = "satellite:read"
SCOPE_DISEASE_READ = "disease:read"
SCOPE_DISEASE_WRITE = "disease:write"
SCOPE_WATER_READ = "water:read"
SCOPE_INTELLIGENCE_READ = "intelligence:read"
SCOPE_MONITOR_READ = "monitor:read"
SCOPE_MONITOR_WRITE = "monitor:write"
SCOPE_MEMORY_READ = "memory:read"
SCOPE_MEMORY_WRITE = "memory:write"
SCOPE_ALERT_READ = "alert:read"
SCOPE_ACTION_APPROVE = "action:approve"
SCOPE_NOTIFICATION_WRITE = "notification:write"
SCOPE_REPORT_WRITE = "report:write"
SCOPE_KNOWLEDGE_READ = "knowledge:read"
SCOPE_COOPERATION_READ = "cooperation:read"

ALL_SCOPES: tuple[str, ...] = (
    SCOPE_FARM_READ,
    SCOPE_FARM_WRITE,
    SCOPE_ADVISORY_READ,
    SCOPE_ADVISORY_WRITE,
    SCOPE_WEATHER_READ,
    SCOPE_SOIL_READ,
    SCOPE_SATELLITE_READ,
    SCOPE_DISEASE_READ,
    SCOPE_DISEASE_WRITE,
    SCOPE_WATER_READ,
    SCOPE_INTELLIGENCE_READ,
    SCOPE_MONITOR_READ,
    SCOPE_MONITOR_WRITE,
    SCOPE_MEMORY_READ,
    SCOPE_MEMORY_WRITE,
    SCOPE_ALERT_READ,
    SCOPE_ACTION_APPROVE,
    SCOPE_NOTIFICATION_WRITE,
    SCOPE_REPORT_WRITE,
    SCOPE_KNOWLEDGE_READ,
    SCOPE_COOPERATION_READ,
)


class ToolInputError(ValueError):
    """Raised when a tool call's arguments do not satisfy its schema."""


class ToolOutputError(ValueError):
    """Raised when a tool's return payload violates its declared schema."""


@dataclass(frozen=True)
class ToolResult:
    """What a tool hands back to the loop.

    ``data`` is the machine-readable payload, ``summary`` is the one-line
    human-readable statement used for the activity feed, and ``sources`` is
    the provenance list that ends up in the task's evidence. A tool that has
    no real observation must return ``available=False`` rather than a
    plausible-looking placeholder.

    Write tools additionally report ``action_id`` / ``verification`` so the
    caller can confirm the change actually landed rather than assuming the
    handler returned implies the write succeeded.
    """

    data: dict[str, Any]
    summary: str
    sources: list[dict] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    confidence: float | None = None
    available: bool = True
    # Set by write tools so the task's action row and the API response can
    # point at the concrete record that was created.
    action_id: str | None = None
    verification: str | None = None

    @classmethod
    def unavailable(cls, summary: str, missing: list[str], source: str = "unavailable") -> "ToolResult":
        return cls(
            data={"available": False},
            summary=summary,
            sources=[{"domain": "capability", "provider": source, "status": "NOT_CONFIGURED"}],
            missing_data=missing,
            available=False,
        )


@dataclass(frozen=True)
class ToolContext:
    """Everything a tool is allowed to see.

    The tool never receives the raw SQLAlchemy session, the request object,
    or any credential. It receives a scoped session, the resolved farm (if
    the caller named one), and the user's id, and it is expected to return
    only data that user is entitled to.
    """

    db: Any
    farm: Any
    user_id: str
    role: str
    task_id: str
    language: str = "en"


ToolHandler = Callable[[ToolContext, BaseModel], ToolResult]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    version: str
    summary: str
    input_model: type[BaseModel]
    handler: ToolHandler
    # The declared shape of the ``data`` a handler returns. Validated by the
    # executor so a handler cannot silently drift from the contract the model
    # and the UI were told about.
    output_model: type[BaseModel] | None = None
    risk_level: ToolRiskLevel = ToolRiskLevel.READ_ONLY
    required_permissions: tuple[str, ...] = (SCOPE_FARM_READ,)
    timeout_seconds: int = 15
    max_retries: int = 1
    source: str = "bhoomi-services"
    enabled: bool = True
    tags: tuple[str, ...] = ()
    # Alternative names this tool answers to. BHOOMI exposes a canonical
    # verb-first surface (``get_farm``) while older clients, prompts and saved
    # sessions still use the original short names (``farm_snapshot``). An alias
    # resolves to the same registered spec, so there is exactly one handler and
    # one audit record regardless of which name was used.
    aliases: tuple[str, ...] = ()
    # Explicit approval gate. Kept as a field rather than derived purely from
    # risk_level so a MEDIUM write that is reversible (a notification) can stay
    # autonomous while a consequential one (expert review) cannot.
    requires_approval: bool = False

    @property
    def is_write(self) -> bool:
        return self.risk_level != ToolRiskLevel.READ_ONLY

    @property
    def names(self) -> tuple[str, ...]:
        """Every name this tool answers to, canonical name first."""
        return (self.name, *self.aliases)

    def validate_input(self, raw: dict[str, Any]) -> BaseModel:
        try:
            return self.input_model(**(raw or {}))
        except ValidationError as exc:
            raise ToolInputError(f"Invalid arguments for tool '{self.name}': {exc.errors()}") from exc

    def validate_output(self, data: dict[str, Any]) -> dict[str, Any]:
        """Checks a handler's payload against the declared output schema.

        Returns the normalised payload. A handler that returns extra keys keeps
        them (the models here are permissive), but a handler that returns the
        *wrong type* for a declared field is a contract violation and is
        rejected rather than passed on to the model.
        """
        if self.output_model is None:
            return data
        try:
            return self.output_model.model_validate(data).model_dump(mode="json")
        except ValidationError as exc:
            raise ToolOutputError(
                f"Tool '{self.name}' returned a payload that does not match its declared "
                f"output schema: {exc.errors()}"
            ) from exc

    def describe(self) -> dict[str, Any]:
        """The catalogue entry exposed to the model and to the UI."""
        schema = self.input_model.model_json_schema()
        return {
            "name": self.name,
            "aliases": list(self.aliases),
            "version": self.version,
            "summary": self.summary,
            "risk_level": self.risk_level.value,
            "requires_approval": self.requires_approval,
            "required_permissions": list(self.required_permissions),
            "timeout_seconds": self.timeout_seconds,
            "source": self.source,
            "enabled": self.enabled,
            "tags": list(self.tags),
            "input_schema": schema,
            "output_schema": self.output_model.model_json_schema() if self.output_model else None,
        }


class ToolRegistry:
    """An explicit allow-list. Registration is the only way in."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._aliases: dict[str, str] = {}

    def register(self, spec: ToolSpec, *, replace: bool = False) -> ToolSpec:
        existing = self._tools.get(spec.name)
        if existing is not None and not replace:
            raise ValueError(f"Tool '{spec.name}' is already registered.")
        conflicts = [
            alias
            for alias in spec.aliases
            if (self._aliases.get(alias) or self._tools.get(alias)) not in (None, spec.name)
        ]
        if conflicts:
            raise ValueError(f"Tool '{spec.name}' declares aliases already in use: {sorted(conflicts)}")
        unknown = set(spec.required_permissions) - set(ALL_SCOPES)
        if unknown:
            raise ValueError(f"Tool '{spec.name}' declares unknown scopes: {sorted(unknown)}")
        if existing is not None:
            for alias in existing.aliases:
                self._aliases.pop(alias, None)
        self._tools[spec.name] = spec
        for alias in spec.aliases:
            self._aliases[alias] = spec.name
        return spec

    def get(self, name: str) -> ToolSpec | None:
        """Resolves a canonical name or an alias to its spec."""
        spec = self._tools.get(name)
        if spec is not None:
            return spec
        canonical = self._aliases.get(name)
        return self._tools.get(canonical) if canonical else None

    def list_tools(self, *, enabled_only: bool = False) -> list[ToolSpec]:
        return [t for t in self._tools.values() if t.enabled or not enabled_only]

    def describe_all(self) -> list[dict[str, Any]]:
        return [t.describe() for t in sorted(self._tools.values(), key=lambda t: t.name)]

    def catalogue_for_model(self, allowed_scopes: set[str], *, enabled_only: bool = True) -> list[dict[str, Any]]:
        """Only the tools this caller could actually run are offered to the
        model. Hiding an unavailable tool is stronger than relying on a later
        permission denial, and keeps the planner from wasting a step on a call
        that was never going to be allowed.

        Both the input and the declared output schema are included: a planner
        that cannot see what a call returns cannot reason about whether the
        call is worth making. Aliases are advertised so the model can use the
        canonical name even when a prompt or an intent map uses an older one.
        """
        return [
            {
                "name": t.name,
                "aliases": list(t.aliases),
                "summary": t.summary,
                "risk_level": t.risk_level.value,
                "requires_approval": t.requires_approval,
                "tags": list(t.tags),
                "input_schema": t.input_model.model_json_schema(),
                "output_schema": t.output_model.model_json_schema() if t.output_model else None,
            }
            for t in sorted(self._tools.values(), key=lambda t: t.name)
            if t.enabled
            and set(t.required_permissions).issubset(allowed_scopes)
        ]


registry = ToolRegistry()