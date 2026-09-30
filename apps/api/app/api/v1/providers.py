"""
Data Providers & Country/Region Registry API Endpoints (BHOOMI Data Network).
Provides status monitoring, registration, and administrative controls for agricultural providers.
"""
from datetime import datetime, timezone
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.core.exceptions import NotFoundError
from app.integrations.data_network.registry import CountryDataRegistry, RegionDataRegistry, seed_database_provider_registry
from app.integrations.data_network.sync_engine import DataSyncEngine
from app.models.data_network import DataProvider, ProviderSyncRun
from app.models.user import Role, User

router = APIRouter(tags=["providers"])


def _ensure_registry_seeded(db: Session) -> None:
    if db.query(DataProvider).count() == 0:
        seed_database_provider_registry(db)


@router.get("/providers")
def list_providers(
    country: Optional[str] = None,
    data_type: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Lists all registered data providers across countries and domains."""
    _ensure_registry_seeded(db)
    query = db.query(DataProvider)
    if country:
        query = query.filter(DataProvider.country.ilike(f"%{country}%"))
    if data_type:
        query = query.filter(DataProvider.data_type == data_type.lower())

    providers = query.order_by(DataProvider.priority.asc(), DataProvider.provider_name.asc()).all()
    return [
        {
            "id": str(p.id),
            "provider_name": p.provider_name,
            "country": p.country,
            "region": p.region,
            "data_type": p.data_type,
            "base_url": p.base_url,
            "authentication_type": p.authentication_type,
            "api_version": p.api_version,
            "enabled": p.enabled,
            "priority": p.priority,
            "refresh_interval_minutes": p.refresh_interval_minutes,
            "status": p.status,
            "auth_status": p.auth_status,
            "error_message": p.error_message,
            "last_success": p.last_success.isoformat() if p.last_success else None,
            "last_failure": p.last_failure.isoformat() if p.last_failure else None,
            "last_sync": p.last_sync.isoformat() if p.last_sync else None,
            "next_sync": p.next_sync.isoformat() if p.next_sync else None,
            "license": p.license,
            "terms_url": p.terms_url,
            "documentation_url": p.documentation_url,
            "capabilities": p.capabilities,
            "rate_limit_per_minute": p.rate_limit_per_minute,
        }
        for p in providers
    ]


@router.get("/providers/status")
def get_providers_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Platform-wide data network operational health summary."""
    _ensure_registry_seeded(db)
    providers = db.query(DataProvider).all()

    total = len(providers)
    healthy = sum(1 for p in providers if p.status == "healthy")
    degraded = sum(1 for p in providers if p.status == "degraded")
    failed = sum(1 for p in providers if p.status in ("failed", "auth_required"))
    # Declared in the registry but not proven reachable by this deployment.
    # Reporting these separately stops "total_providers" from being read as
    # "sources we are connected to".
    unverified = sum(1 for p in providers if p.status in ("unverified", "configured", "unknown"))
    connected = healthy + degraded

    # Recent sync runs
    recent_runs = (
        db.query(ProviderSyncRun)
        .order_by(ProviderSyncRun.started_at.desc())
        .limit(10)
        .all()
    )

    last_sync = max([p.last_sync for p in providers if p.last_sync], default=None)

    return {
        "summary": {
            "total_providers": total,
            "healthy": healthy,
            "degraded": degraded,
            "failed": failed,
            "connected": connected,
            "unverified": unverified,
            "last_sync": last_sync.isoformat() if last_sync else None,
        },
        "providers": [
            {
                "id": str(p.id),
                "name": p.provider_name,
                "country": p.country,
                "data_type": p.data_type,
                "status": p.status,
                "auth_status": p.auth_status,
                "priority": p.priority,
                "enabled": p.enabled,
                "last_sync": p.last_sync.isoformat() if p.last_sync else None,
                "error_message": p.error_message,
            }
            for p in providers
        ],
        "recent_sync_runs": [
            {
                "id": str(r.id),
                "provider_id": str(r.provider_id),
                "trigger_type": r.trigger_type,
                "status": r.status,
                "records_ingested": r.records_ingested,
                "duration_ms": r.duration_ms,
                "started_at": r.started_at.isoformat() if r.started_at else None,
            }
            for r in recent_runs
        ],
    }


@router.get("/countries")
def list_countries(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Lists registered countries and their connected regional state adapters."""
    _ensure_registry_seeded(db)
    countries = CountryDataRegistry.get_supported_countries()
    result = []
    for c in countries:
        regions = RegionDataRegistry.get_supported_regions(c)
        p_count = db.query(DataProvider).filter(DataProvider.country == c).count()
        result.append({
            "country": c,
            "regions": regions,
            "providers_count": p_count,
            "national_systems": ["IMD", "Soil Health Card", "ISRO Bhoonidhi"] if c == "India" else ["Global Fallbacks"],
        })
    return result


@router.get("/countries/{country}/providers")
def get_country_providers(
    country: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retrieves providers dedicated to or covering a specific country."""
    _ensure_registry_seeded(db)
    providers = (
        db.query(DataProvider)
        .filter((DataProvider.country.ilike(country)) | (DataProvider.country == "Global"))
        .order_by(DataProvider.priority.asc())
        .all()
    )
    return [
        {
            "id": str(p.id),
            "provider_name": p.provider_name,
            "country": p.country,
            "region": p.region,
            "data_type": p.data_type,
            "status": p.status,
            "auth_status": p.auth_status,
            "priority": p.priority,
            "enabled": p.enabled,
            "last_sync": p.last_sync.isoformat() if p.last_sync else None,
        }
        for p in providers
    ]


@router.get("/regions/{region_id}/providers")
def get_region_providers(
    region_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retrieves providers applicable to a specific region/state node."""
    _ensure_registry_seeded(db)
    providers = (
        db.query(DataProvider)
        .filter(
            (DataProvider.region == region_id) | (DataProvider.region == None)
        )
        .order_by(DataProvider.priority.asc())
        .all()
    )
    return [
        {
            "id": str(p.id),
            "provider_name": p.provider_name,
            "country": p.country,
            "region": p.region,
            "data_type": p.data_type,
            "status": p.status,
            "priority": p.priority,
            "enabled": p.enabled,
        }
        for p in providers
    ]


def _find_provider(db: Session, identifier: str) -> DataProvider | None:
    _ensure_registry_seeded(db)
    try:
        uid = uuid.UUID(identifier)
        return db.query(DataProvider).filter(DataProvider.id == uid).first()
    except ValueError:
        slug = identifier.replace("-", " ").strip().lower()
        return db.query(DataProvider).filter(
            func.lower(DataProvider.provider_name) == slug
        ).first()


@router.post("/admin/providers/{provider_id}/sync")
def trigger_provider_sync(
    provider_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.PLATFORM_ADMIN, Role.STATE_ADMIN)),
):
    """Triggers an on-demand manual synchronization for a provider."""
    provider = _find_provider(db, provider_id)
    if not provider:
        raise NotFoundError("Provider not found.")

    result = DataSyncEngine.run_provider_sync(db, provider)
    return {
        "provider_id": str(provider.id),
        "provider_name": provider.provider_name,
        "sync_result": result,
    }


@router.post("/admin/providers/{provider_id}/test")
def test_provider_connection(
    provider_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.PLATFORM_ADMIN, Role.STATE_ADMIN)),
):
    """Runs connection diagnostics and health tests for a data provider."""
    provider = _find_provider(db, provider_id)
    if not provider:
        raise NotFoundError("Provider not found.")

    diagnostic = DataSyncEngine.test_provider(db, provider)
    diagnostic_status = diagnostic.get("status") if isinstance(diagnostic, dict) else None
    return {
        "provider_id": str(provider.id),
        "provider_name": provider.provider_name,
        # Surface the outcome at the top level so clients do not have to know
        # the internal shape of the diagnostic payload.
        "status": diagnostic_status or "unknown",
        "test_results": diagnostic,
    }


@router.post("/admin/providers/{provider_id}/enable")
def enable_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.PLATFORM_ADMIN)),
):
    """Enables a provider in the data registry."""
    provider = _find_provider(db, provider_id)
    if not provider:
        raise NotFoundError("Provider not found.")
    provider.enabled = True
    db.commit()
    return {"id": str(provider.id), "provider_name": provider.provider_name, "enabled": True}


@router.post("/admin/providers/{provider_id}/disable")
def disable_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.PLATFORM_ADMIN)),
):
    """Disables a provider in the data registry."""
    provider = _find_provider(db, provider_id)
    if not provider:
        raise NotFoundError("Provider not found.")
    provider.enabled = False
    db.commit()
    return {"id": str(provider.id), "provider_name": provider.provider_name, "enabled": False}
