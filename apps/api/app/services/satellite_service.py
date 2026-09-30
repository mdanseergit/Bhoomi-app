"""
SatelliteService -- wraps the SatelliteProvider abstraction, persists
observations, and computes short-term NDVI trend used by the intelligence
engine.
"""
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.integrations.satellite.factory import get_satellite_provider
from app.models.farm import Farm
from app.models.satellite import SatelliteObservation
from app.services.agriculture.schema import VegetationSnapshot

logger = get_logger("bhoomi.satellite.service")


class SatelliteService:
    def __init__(self) -> None:
        self.provider = get_satellite_provider()

    def sync_farm(self, db: Session, farm: Farm, days: int = 30) -> list[SatelliteObservation]:
        from app.integrations.data_network.sync_engine import DataSyncEngine
        return DataSyncEngine.sync_farm_satellite(db, farm, days=days)

    def get_latest_snapshot(self, db: Session, farm: Farm) -> VegetationSnapshot:
        rows = (
            db.query(SatelliteObservation)
            .filter(SatelliteObservation.farm_id == farm.id)
            .order_by(SatelliteObservation.observation_date.desc())
            .limit(3)
            .all()
        )
        if not rows:
            self.sync_farm(db, farm)
            rows = (
                db.query(SatelliteObservation)
                .filter(SatelliteObservation.farm_id == farm.id)
                .order_by(SatelliteObservation.observation_date.desc())
                .limit(3)
                .all()
            )
        if not rows:
            # No observation available. Report explicitly empty rather than
            # defaulting NDVI/EVI to invented values.
            return VegetationSnapshot(
                ndvi=None,
                evi=None,
                trend_7d_pct=None,
                vegetation_health=None,
                source="unavailable",
                observation_date=None,
                is_dev_dataset=False,
            )

        latest = rows[0]
        trend = None
        if len(rows) > 1 and rows[-1].ndvi and latest.ndvi:
            trend = round(((latest.ndvi - rows[-1].ndvi) / rows[-1].ndvi) * 100, 1)

        return VegetationSnapshot(
            ndvi=latest.ndvi,
            evi=latest.evi,
            trend_7d_pct=trend,
            vegetation_health=latest.vegetation_health,
            source=latest.source,
            observation_date=latest.observation_date,
            is_dev_dataset=latest.is_dev_dataset,
        )
