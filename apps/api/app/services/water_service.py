"""
WaterService (BHOOMI Data Network).
Coordinates water intelligence: rainfall, soil moisture, irrigation, and drought indicators.
Explicitly isolates and labels lab soil moisture vs field sensors vs satellite estimates.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.integrations.data_network.base import FreshnessState, QualityStatus
from app.integrations.data_network.quality_service import DataQualityService
from app.models.data_network import WaterObservation
from app.models.farm import Farm
from app.models.soil import SoilProfile
from app.models.weather import WeatherObservation


@dataclass
class WaterSnapshot:
    rainfall_mm: Optional[float]
    soil_moisture_pct: Optional[float]
    moisture_source_type: str  # lab | field_sensor | satellite_estimate | modelled
    irrigation_applied_mm: Optional[float]
    drought_index: Optional[float]
    source: str
    freshness: str
    observed_at: Optional[datetime]
    has_data: bool


class WaterService:
    def get_snapshot(self, db: Session, farm: Farm) -> WaterSnapshot:
        # 1. Check direct water observation log
        obs = (
            db.query(WaterObservation)
            .filter(WaterObservation.farm_id == farm.id)
            .order_by(WaterObservation.observed_at.desc())
            .first()
        )
        if obs:
            freshness, _ = DataQualityService.evaluate_freshness("water", obs.observed_at)
            return WaterSnapshot(
                rainfall_mm=obs.rainfall_mm,
                soil_moisture_pct=obs.soil_moisture_pct,
                moisture_source_type=obs.moisture_source_type,
                irrigation_applied_mm=obs.irrigation_applied_mm,
                drought_index=obs.drought_index,
                source=obs.source,
                freshness=freshness.value,
                observed_at=obs.observed_at,
                has_data=True,
            )

        # 2. Derive from latest weather and soil profile if available
        weather = (
            db.query(WeatherObservation)
            .filter(WeatherObservation.farm_id == farm.id)
            .order_by(WeatherObservation.observed_at.desc())
            .first()
        )
        soil = db.query(SoilProfile).filter(SoilProfile.farm_id == farm.id).first()

        rainfall = weather.rainfall if weather else None
        soil_moist = soil.moisture if soil else None
        moist_source = "lab" if (soil and soil.source in ("soil_health_card", "csv_import", "manual")) else "modelled"

        has_data = (rainfall is not None) or (soil_moist is not None)
        obs_time = weather.observed_at if weather else (datetime.combine(soil.sample_date, datetime.min.time()) if soil and soil.sample_date else None)
        freshness, _ = DataQualityService.evaluate_freshness("water", obs_time)

        return WaterSnapshot(
            rainfall_mm=rainfall,
            soil_moisture_pct=soil_moist,
            moisture_source_type=moist_source if soil_moist is not None else "unavailable",
            irrigation_applied_mm=None,
            drought_index=None,
            source=weather.source if weather else (soil.source if soil else "unavailable"),
            freshness=freshness.value if has_data else FreshnessState.UNKNOWN.value,
            observed_at=obs_time,
            has_data=has_data,
        )
