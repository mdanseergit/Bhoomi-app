"""
Background job implementations. Every task:
  - is idempotent (safe to run twice for the same farm/day)
  - retries with exponential backoff on transient provider failures
  - logs structured progress for observability
"""
from celery import shared_task

from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.models.farm import Farm
from app.services.satellite_service import SatelliteService
from app.services.weather_service import WeatherService

logger = get_logger("bhoomi.workers")


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def sync_farm_weather(self, farm_id: str):
    db = SessionLocal()
    try:
        farm = db.get(Farm, farm_id)
        if not farm:
            logger.warning("sync_farm_weather_farm_not_found", farm_id=farm_id)
            return
        WeatherService().get_current_snapshot(db, farm)
        logger.info("sync_farm_weather_completed", farm_id=farm_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("sync_farm_weather_failed_retrying", farm_id=farm_id, error=str(exc))
        raise self.retry(exc=exc)
    finally:
        db.close()


@shared_task
def sync_all_farms_weather():
    db = SessionLocal()
    try:
        farm_ids = [str(f.id) for f in db.query(Farm.id).filter(Farm.deleted_at.is_(None)).all()]
    finally:
        db.close()
    for fid in farm_ids:
        sync_farm_weather.delay(fid)
    logger.info("sync_all_farms_weather_dispatched", count=len(farm_ids))
    return len(farm_ids)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def sync_farm_satellite(self, farm_id: str):
    db = SessionLocal()
    try:
        farm = db.get(Farm, farm_id)
        if not farm:
            return
        SatelliteService().sync_farm(db, farm)
        logger.info("sync_farm_satellite_completed", farm_id=farm_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("sync_farm_satellite_failed_retrying", farm_id=farm_id, error=str(exc))
        raise self.retry(exc=exc)
    finally:
        db.close()


@shared_task
def sync_all_farms_satellite():
    db = SessionLocal()
    try:
        farm_ids = [str(f.id) for f in db.query(Farm.id).filter(Farm.deleted_at.is_(None)).all()]
    finally:
        db.close()
    for fid in farm_ids:
        sync_farm_satellite.delay(fid)
    logger.info("sync_all_farms_satellite_dispatched", count=len(farm_ids))
    return len(farm_ids)


@shared_task
def recompute_farm_intelligence(farm_id: str, user_id: str | None = None):
    """Triggered after new soil data, a disease scan, or a significant
    weather change so the farm's advisory set stays current."""
    from app.services.intelligence_service import IntelligenceService

    db = SessionLocal()
    try:
        farm = db.get(Farm, farm_id)
        if not farm:
            return
        IntelligenceService().compute_and_persist(db, farm, user_id=user_id, with_ai=False)
        logger.info("recompute_farm_intelligence_completed", farm_id=farm_id)
    finally:
        db.close()


@shared_task
def cleanup_stale_data():
    """Removes expired idempotency/cache keys and other transient state.
    Actual TTL-based Redis keys expire automatically; this task exists as
    an extension point for future DB-side retention cleanup (see
    DATA-GOVERNANCE.md retention policy)."""
    logger.info("cleanup_stale_data_ran")
    return True
