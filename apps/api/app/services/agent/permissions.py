"""
RBAC -> permission-scope resolution for agent tool calls.

This is deliberately separate from ``app.core.deps.require_roles``. That guard
answers "may this user call this endpoint"; this answers "which real-world
capabilities may the agent exercise on their behalf". A platform admin can
call the agent endpoint without the agent silently inheriting write access to
every farm, so the mapping below stays narrow and explicit.
"""
from app.models.user import Role
from app.services.agent.registry import (
    SCOPE_ACTION_APPROVE,
    SCOPE_ADVISORY_READ,
    SCOPE_ADVISORY_WRITE,
    SCOPE_ALERT_READ,
    SCOPE_COOPERATION_READ,
    SCOPE_DISEASE_READ,
    SCOPE_DISEASE_WRITE,
    SCOPE_FARM_READ,
    SCOPE_FARM_WRITE,
    SCOPE_INTELLIGENCE_READ,
    SCOPE_KNOWLEDGE_READ,
    SCOPE_MEMORY_READ,
    SCOPE_MEMORY_WRITE,
    SCOPE_MONITOR_READ,
    SCOPE_MONITOR_WRITE,
    SCOPE_NOTIFICATION_WRITE,
    SCOPE_REPORT_WRITE,
    SCOPE_SATELLITE_READ,
    SCOPE_SOIL_READ,
    SCOPE_WATER_READ,
    SCOPE_WEATHER_READ,
)

_READ_SCOPES: frozenset[str] = frozenset(
    {
        SCOPE_FARM_READ,
        SCOPE_WEATHER_READ,
        SCOPE_SOIL_READ,
        SCOPE_SATELLITE_READ,
        SCOPE_WATER_READ,
        SCOPE_DISEASE_READ,
        SCOPE_ADVISORY_READ,
        SCOPE_INTELLIGENCE_READ,
        SCOPE_MONITOR_READ,
        SCOPE_MEMORY_READ,
        SCOPE_ALERT_READ,
        SCOPE_KNOWLEDGE_READ,
        SCOPE_COOPERATION_READ,
    }
)


def scopes_for_role(role: Role) -> set[str]:
    """Scopes granted to a user by role.

    Farmers additionally get memory/monitor *writes* because both are scoped
    to their own account, plus the two self-directed writes: a notification to
    themselves and a saved report of their own observations. Nothing here
    grants a write on another user's farm -- that is checked per resource by
    the executor, not by role.
    """
    if role == Role.FARMER:
        return set(_READ_SCOPES) | {
            SCOPE_MEMORY_WRITE,
            SCOPE_MONITOR_WRITE,
            SCOPE_NOTIFICATION_WRITE,
            SCOPE_REPORT_WRITE,
        }

    if role == Role.AGRONOMIST:
        return set(_READ_SCOPES) | {
            SCOPE_ADVISORY_WRITE,
            SCOPE_DISEASE_WRITE,
            SCOPE_MEMORY_WRITE,
            SCOPE_MONITOR_WRITE,
            SCOPE_NOTIFICATION_WRITE,
            SCOPE_REPORT_WRITE,
            SCOPE_ACTION_APPROVE,
        }

    if role == Role.STATE_ADMIN:
        return set(_READ_SCOPES) | {
            SCOPE_ADVISORY_WRITE,
            SCOPE_DISEASE_WRITE,
            SCOPE_MEMORY_WRITE,
            SCOPE_MONITOR_WRITE,
            SCOPE_NOTIFICATION_WRITE,
            SCOPE_REPORT_WRITE,
            SCOPE_ALERT_READ,
            SCOPE_ACTION_APPROVE,
        }

    if role == Role.PLATFORM_ADMIN:
        return set(_READ_SCOPES) | {
            SCOPE_FARM_WRITE,
            SCOPE_ADVISORY_WRITE,
            SCOPE_DISEASE_WRITE,
            SCOPE_MONITOR_WRITE,
            SCOPE_MEMORY_WRITE,
            SCOPE_NOTIFICATION_WRITE,
            SCOPE_REPORT_WRITE,
            SCOPE_ACTION_APPROVE,
        }

    return set()


def missing_scopes(required: tuple[str, ...] | list[str], granted: set[str]) -> list[str]:
    return [scope for scope in required if scope not in granted]