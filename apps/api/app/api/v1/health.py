"""
Observability endpoints (PRODUCT SPEC section 60): /health, /ready, /live.
"""
from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.redis_client import get_redis

router = APIRouter(tags=["health"])


def _check_db() -> str:
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return "healthy"
    except Exception:
        return "unhealthy"


def _check_redis() -> str:
    try:
        get_redis().ping()
        return "healthy"
    except Exception:
        return "unhealthy"


def _check_ai() -> str:
    if not settings.NVIDIA_API_KEY:
        return "deterministic_fallback_only"
    if settings.ai_model_chain:
        return "configured"
    return "missing_model_config"


def _check_weather() -> str:
    return "configured" if settings.IMD_API_BASE_URL and settings.IMD_API_KEY else "not_configured"


def _check_satellite() -> str:
    provider = (settings.SATELLITE_PROVIDER or "none").strip().lower()
    if provider in ("", "none", "unavailable"):
        return "not_configured"
    return provider


def _check_disease_model() -> str:
    """Report the disease backend this deployment can actually serve.

    Mirrors DiseaseService._resolve_provider, so a name that resolves to the
    development heuristic is reported as not configured rather than echoed
    back as if it were a real model.
    """
    from app.services.disease_service import DiseaseService

    if (settings.DISEASE_MODEL_PROVIDER or "").strip().lower() in ("", "none"):
        return "not_configured"
    resolved = DiseaseService._resolve_provider()
    if resolved is None or not resolved.is_validated:
        return "not_configured"
    return resolved.name


@router.get("/health")
def health():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
        "database": _check_db(),
        "redis": _check_redis(),
        "ai_provider": _check_ai(),
        "weather_provider": _check_weather(),
        "satellite_provider": _check_satellite(),
        "disease_model": _check_disease_model(),
    }


@router.get("/ready")
def ready():
    db_ok = _check_db() == "healthy"
    redis_ok = _check_redis() == "healthy"
    return {"ready": db_ok and redis_ok, "database": db_ok, "redis": redis_ok}


@router.get("/live")
def live():
    return {"alive": True}
