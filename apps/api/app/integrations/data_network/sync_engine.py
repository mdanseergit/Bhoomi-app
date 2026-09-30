"""
Production Data Synchronization Engine (BHOOMI Data Network).
Coordinates automated ingestion, validation, deduplication, failover, and event dispatch.
"""
from datetime import datetime, date, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from app.core.exceptions import ProviderUnavailableError
from app.core.logging import get_logger
from app.integrations.data_network.base import FreshnessState, QualityStatus
from app.integrations.data_network.quality_service import DataQualityService
from app.integrations.data_network.resolver import DataProviderResolver
from app.models.data_network import (
    DataConflict,
    DataProvider,
    DataQualityRecord,
    ProviderSyncRun,
    RawObservation,
    SyncEvent,
    WaterObservation,
)
from app.models.farm import Farm
from app.models.satellite import SatelliteObservation
from app.models.soil import SoilObservation, SoilProfile
from app.models.weather import WeatherObservation

logger = get_logger("bhoomi.datanetwork.sync_engine")


class DataSyncEngine:
    @classmethod
    def sync_farm_weather(cls, db: Session, farm: Farm, force: bool = False) -> Optional[WeatherObservation]:
        """
        Synchronizes weather for a farm following provider priority and graceful fallback.
        Priority: IMD -> NASA POWER -> latest verified observation.
        """
        # 1. Check existing freshness
        latest = (
            db.query(WeatherObservation)
            .filter(WeatherObservation.farm_id == farm.id)
            .order_by(WeatherObservation.observed_at.desc())
            .first()
        )
        if latest and not force:
            freshness, age_hours = DataQualityService.evaluate_freshness("weather", latest.observed_at)
            if freshness in (FreshnessState.LIVE, FreshnessState.RECENT):
                return latest

        # 2. Resolve provider chain
        chain = DataProviderResolver.resolve_chain(
            country="India" if farm.state else "Global",
            state=farm.state,
            data_type="weather",
            db=db,
        )

        for provider in chain:
            run = ProviderSyncRun(
                provider_id=uuid.uuid4(),  # ephemeral ID if not matched to DB provider
                trigger_type="farm_access" if not force else "manual",
                status="running",
                started_at=datetime.now(timezone.utc),
            )
            # Find DB provider record if exists
            db_prov = db.query(DataProvider).filter(DataProvider.provider_name == provider.name, DataProvider.data_type == "weather").first()
            if db_prov:
                run.provider_id = db_prov.id

            try:
                raw_payload = provider.fetch(latitude=farm.latitude, longitude=farm.longitude)
                canonical = provider.normalize(raw_payload)
                is_valid, issues = provider.validate(canonical)

                if is_valid:
                    # Persist raw observation for auditability
                    raw_record = RawObservation(
                        provider_id=run.provider_id if db_prov else None,
                        source_dataset=f"{provider.name}_current",
                        external_record_id=canonical.provenance.external_id if canonical.provenance else None,
                        farm_id=farm.id,
                        data_type="weather",
                        payload=raw_payload,
                        observed_at=canonical.observed_at,
                        ingested_at=datetime.now(timezone.utc),
                    )
                    db.add(raw_record)

                    stored_obs = provider.store(db, canonical, farm_id=farm.id)

                    # Update water layer observation if rainfall is recorded
                    if canonical.rainfall_mm is not None:
                        water_obs = WaterObservation(
                            farm_id=farm.id,
                            provider_id=run.provider_id if db_prov else None,
                            rainfall_mm=canonical.rainfall_mm,
                            moisture_source_type="modelled",
                            source=canonical.source,
                            quality_status=canonical.quality.value,
                            freshness_status=canonical.freshness.value,
                            observed_at=canonical.observed_at or datetime.now(timezone.utc),
                            ingested_at=datetime.now(timezone.utc),
                        )
                        db.add(water_obs)

                    # Log sync run success
                    run.status = "success"
                    run.records_ingested = 1
                    run.completed_at = datetime.now(timezone.utc)
                    run.duration_ms = int((run.completed_at - run.started_at).total_seconds() * 1000)
                    db.add(run)

                    if db_prov:
                        db_prov.last_success = datetime.now(timezone.utc)
                        db_prov.last_sync = datetime.now(timezone.utc)
                        db_prov.status = "healthy"

                    # Dispatch event
                    db.add(SyncEvent(
                        farm_id=farm.id,
                        event_type="DATA_INGESTED",
                        summary=f"Weather telemetry synced from {provider.name}",
                        details={"temperature": canonical.temperature_c, "source": canonical.source, "freshness": canonical.freshness.value},
                    ))
                    db.commit()
                    return stored_obs

            except ProviderUnavailableError as exc:
                logger.info("provider_unavailable_trying_fallback", provider=provider.name, reason=str(exc))
                run.status = "failed"
                run.error_message = str(exc)
                run.completed_at = datetime.now(timezone.utc)
                db.add(run)
                if db_prov:
                    db_prov.last_failure = datetime.now(timezone.utc)
                    if db_prov.auth_status == "authentication_required":
                        db_prov.status = "auth_required"
                    else:
                        db_prov.status = "degraded"
                db.commit()
                continue
            except Exception as exc:
                logger.warning("provider_sync_error", provider=provider.name, error=str(exc))
                run.status = "failed"
                run.error_message = str(exc)
                run.completed_at = datetime.now(timezone.utc)
                db.add(run)
                db.commit()
                continue

        # If all live providers fail, return cached latest
        if latest:
            latest.freshness_status = FreshnessState.STALE.value
            return latest

        return None

    @classmethod
    def sync_farm_satellite(cls, db: Session, farm: Farm, days: int = 30) -> List[SatelliteObservation]:
        """
        Synchronizes satellite observations for farm using ISRO/Bhoonidhi with Copernicus fallback.
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        chain = DataProviderResolver.resolve_chain(
            country="India" if farm.state else "Global",
            state=farm.state,
            data_type="satellite",
            db=db,
        )

        for provider in chain:
            if not provider.connect():
                continue
            try:
                features = provider.fetch(latitude=farm.latitude, longitude=farm.longitude, start_date=start_date, end_date=end_date)
                stored_list = []
                for feat in features:
                    canonical = provider.normalize(feat)
                    is_valid, _ = provider.validate(canonical)
                    if is_valid:
                        obs = provider.store(db, canonical, farm_id=farm.id)
                        stored_list.append(obs)

                if stored_list:
                    db.add(SyncEvent(
                        farm_id=farm.id,
                        event_type="SATELLITE_UPDATED",
                        summary=f"Satellite telemetry updated from {provider.name} ({len(stored_list)} observations)",
                        details={"provider": provider.name, "observations": len(stored_list)},
                    ))
                    db.commit()
                    return stored_list

            except ProviderUnavailableError as exc:
                logger.info("satellite_provider_unavailable", provider=provider.name, reason=str(exc))
                continue
            except Exception as exc:
                logger.warning("satellite_sync_exception", provider=provider.name, error=str(exc))
                continue

        return []

    @classmethod
    def test_provider(cls, db: Session, provider: DataProvider) -> dict:
        """Executes a diagnostic health check and connection test for a provider."""
        adapter_cls = DataProviderResolver._ADAPTERS.get(provider.provider_name)
        if not adapter_cls:
            return {"status": "error", "message": f"No adapter registered for '{provider.provider_name}'"}

        adapter = adapter_cls()
        health = adapter.health_check()
        capabilities = adapter.discover_capabilities()

        # Update DB provider record if persisted
        db_provider = db.get(DataProvider, provider.id) if provider.id else None
        if db_provider:
            db_provider.status = health.get("status", "healthy")
            db_provider.auth_status = health.get("auth_status", "active")
            db_provider.error_message = health.get("message")
            db.commit()

        return {
            "health": health,
            "capabilities": capabilities,
            "connected": adapter.connect(),
        }

    @classmethod
    def run_provider_sync(cls, db: Session, provider: DataProvider) -> dict:
        """Manually or periodically triggers a provider synchronization job."""
        adapter_cls = DataProviderResolver._ADAPTERS.get(provider.provider_name)
        if not adapter_cls:
            return {"status": "error", "message": f"No adapter registered for '{provider.provider_name}'"}

        run = ProviderSyncRun(
            provider_id=provider.id,
            trigger_type="manual",
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.add(run)
        db.commit()

        adapter = adapter_cls()
        if not adapter.connect():
            run.status = "failed"
            run.error_message = f"Provider '{provider.provider_name}' credentials missing or unconfigured"
            run.completed_at = datetime.now(timezone.utc)
            provider.last_failure = datetime.now(timezone.utc)
            provider.status = "auth_required" if provider.authentication_type != "none" else "failed"
            db.commit()
            return {"status": "failed", "message": run.error_message}

        try:
            # Sync across active farms for this country/region
            query = db.query(Farm)
            if provider.country != "Global":
                query = query.filter(Farm.state != None)
            farms = query.limit(10).all()

            ingested = 0
            for f in farms:
                if provider.data_type == "weather":
                    obs = cls.sync_farm_weather(db, f, force=True)
                    if obs:
                        ingested += 1
                elif provider.data_type == "satellite":
                    s_obs = cls.sync_farm_satellite(db, f, days=15)
                    ingested += len(s_obs)

            run.status = "success"
            run.records_ingested = ingested
            run.completed_at = datetime.now(timezone.utc)
            run.duration_ms = int((run.completed_at - run.started_at).total_seconds() * 1000)
            provider.last_success = datetime.now(timezone.utc)
            provider.last_sync = datetime.now(timezone.utc)
            provider.status = "healthy"
            db.commit()
            return {"status": "success", "records_ingested": ingested, "duration_ms": run.duration_ms}

        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
            run.completed_at = datetime.now(timezone.utc)
            provider.last_failure = datetime.now(timezone.utc)
            provider.status = "degraded"
            db.commit()
            return {"status": "failed", "error": str(exc)}
