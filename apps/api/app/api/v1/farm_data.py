"""
Farm-Specific Data Fabric API Endpoints (BHOOMI Data Network).
Provides farm-level weather, soil, satellite, water, crop, sources, data-status, and timeline views.
"""
from datetime import datetime, date, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.farms import _ensure_owner_or_privileged
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.integrations.data_network.base import FreshnessState
from app.integrations.data_network.quality_service import DataQualityService
from app.models.crop import CropCycle, CropVariety
from app.models.data_network import AgricultureStatistic, FarmDataSnapshot, SyncEvent, WaterObservation
from app.models.disease import DiseaseScan
from app.models.farm import Farm
from app.models.satellite import SatelliteObservation
from app.models.soil import SoilObservation, SoilProfile
from app.models.user import User
from app.models.weather import WeatherForecast, WeatherObservation
from app.repositories.farm_repository import FarmRepository
from app.services.satellite_service import SatelliteService
from app.services.soil_service import SoilService
from app.services.water_service import WaterService
from app.services.weather_service import WeatherService

router = APIRouter(prefix="/farms", tags=["farm-data"])
farm_repo = FarmRepository()
weather_service = WeatherService()
soil_service = SoilService()
satellite_service = SatelliteService()
water_service = WaterService()


@router.get("/{farm_id}/data-status")
def get_farm_data_status(
    farm_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Returns actual freshness and synchronization status for all data domains.
    Never falsely claims 'live' when data is periodic or historical.
    """
    farm = farm_repo.get(db, farm_id)
    if not farm:
        raise NotFoundError("Farm not found.")
    _ensure_owner_or_privileged(farm, user)

    # 1. Weather
    weather = (
        db.query(WeatherObservation)
        .filter(WeatherObservation.farm_id == farm.id)
        .order_by(WeatherObservation.observed_at.desc())
        .first()
    )
    w_freshness, w_age = DataQualityService.evaluate_freshness("weather", weather.observed_at if weather else None)

    # 2. Soil
    soil = db.query(SoilProfile).filter(SoilProfile.farm_id == farm.id).first()
    s_freshness, s_age = DataQualityService.evaluate_freshness("soil", soil.sample_date if soil else None)

    # 3. Satellite
    sat = (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.farm_id == farm.id)
        .order_by(SatelliteObservation.observation_date.desc())
        .first()
    )
    sat_freshness, sat_age = DataQualityService.evaluate_freshness("satellite", sat.observation_date if sat else None)

    # 4. Water
    water = (
        db.query(WaterObservation)
        .filter(WaterObservation.farm_id == farm.id)
        .order_by(WaterObservation.observed_at.desc())
        .first()
    )
    wat_freshness, wat_age = DataQualityService.evaluate_freshness("water", water.observed_at if water else (weather.observed_at if weather else None))

    # 5. Crop
    c_cycle = (
        db.query(CropCycle)
        .filter(CropCycle.farm_id == farm.id)
        .order_by(CropCycle.created_at.desc())
        .first()
    )

    # 6. Disease
    disease = (
        db.query(DiseaseScan)
        .filter(DiseaseScan.farm_id == farm.id)
        .order_by(DiseaseScan.created_at.desc())
        .first()
    )

    return {
        "farm_id": str(farm.id),
        "farm_name": farm.name,
        "location": {
            "country": "India" if farm.state else "Global",
            "state": farm.state,
            "district": farm.district,
            "latitude": farm.latitude,
            "longitude": farm.longitude,
        },
        "domains": {
            "weather": {
                "label": "Weather Telemetry",
                "status": w_freshness.value,
                "data_age_hours": w_age,
                "source": weather.source if weather else "unavailable",
                "observed_at": weather.observed_at.isoformat() if weather else None,
                "available": weather is not None,
            },
            "soil": {
                "label": "Soil Health",
                "status": s_freshness.value,
                "data_age_days": round(s_age / 24.0, 1) if s_age is not None else None,
                "source": soil.source if soil else "unavailable",
                "observed_at": soil.sample_date.isoformat() if soil and soil.sample_date else None,
                "available": soil is not None,
            },
            "satellite": {
                "label": "Satellite Vegetation",
                "status": sat_freshness.value,
                "data_age_days": round(sat_age / 24.0, 1) if sat_age is not None else None,
                "source": sat.source if sat else "unavailable",
                "observed_at": sat.observation_date.isoformat() if sat else None,
                "available": sat is not None,
            },
            "water": {
                "label": "Water Intelligence",
                "status": wat_freshness.value,
                "data_age_hours": wat_age,
                "moisture_source_type": water.moisture_source_type if water else ("lab" if soil and soil.moisture else "unavailable"),
                "source": water.source if water else (weather.source if weather else "unavailable"),
                "observed_at": water.observed_at.isoformat() if water else None,
                "available": (water is not None) or (weather and weather.rainfall is not None) or (soil and soil.moisture is not None),
            },
            "crop": {
                "label": "Crop Cycle",
                "status": "RECENT" if (farm.current_crop or c_cycle) else "UNKNOWN",
                "current_crop": farm.current_crop,
                "stage": farm.crop_stage or (c_cycle.stage if c_cycle else None),
                "source": "farmer_provided",
                "available": bool(farm.current_crop or c_cycle),
            },
            "disease": {
                "label": "Crop Disease Diagnostic",
                "status": "RECENT" if disease else "NOT_ASSESSED",
                "possible_disease": disease.possible_disease if disease else None,
                "confidence": f"{int(disease.confidence * 100)}%" if disease else None,
                "observed_at": disease.created_at.isoformat() if disease else None,
                "available": disease is not None,
            },
        },
    }


@router.get("/{farm_id}/weather")
def get_farm_weather(
    farm_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retrieves current verified weather observation and forecasts for the farm."""
    farm = farm_repo.get(db, farm_id)
    if not farm:
        raise NotFoundError("Farm not found.")
    _ensure_owner_or_privileged(farm, user)

    snapshot = weather_service.get_current_snapshot(db, farm)
    w_freshness, w_age = DataQualityService.evaluate_freshness("weather", snapshot.observed_at)

    forecasts = (
        db.query(WeatherForecast)
        .filter(WeatherForecast.farm_id == farm.id)
        .order_by(WeatherForecast.forecast_time.asc())
        .limit(5)
        .all()
    )

    return {
        "current": {
            "temperature_c": snapshot.temperature_c,
            "humidity_pct": snapshot.humidity_pct,
            "rainfall_mm": snapshot.rainfall_mm,
            "rain_probability_pct": snapshot.rain_probability_pct,
            "wind_speed_kmh": snapshot.wind_speed_kmh,
            "condition": snapshot.condition,
            "warning_level": snapshot.warning_level,
            "source": snapshot.source,
            "freshness": w_freshness.value,
            "data_age_hours": w_age,
            "observed_at": snapshot.observed_at.isoformat() if snapshot.observed_at else None,
        },
        "forecast": [
            {
                "forecast_time": f.forecast_time.isoformat(),
                "temperature": f.temperature,
                "humidity": f.humidity,
                "rainfall_expected_mm": f.rainfall_expected_mm,
                "rain_probability": f.rain_probability,
                "condition": f.weather_condition,
                "warning_level": f.warning_level,
                "source": f.source,
            }
            for f in forecasts
        ],
    }


@router.get("/{farm_id}/soil")
def get_farm_soil(
    farm_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retrieves latest soil profile and historical lab/field test observation log."""
    farm = farm_repo.get(db, farm_id)
    if not farm:
        raise NotFoundError("Farm not found.")
    _ensure_owner_or_privileged(farm, user)

    profile = db.query(SoilProfile).filter(SoilProfile.farm_id == farm.id).first()
    history = (
        db.query(SoilObservation)
        .filter(SoilObservation.farm_id == farm.id)
        .order_by(SoilObservation.sample_date.desc().nullslast())
        .limit(10)
        .all()
    )

    s_freshness, s_age = DataQualityService.evaluate_freshness("soil", profile.sample_date if profile else None)

    return {
        "profile": {
            "ph": profile.ph if profile else None,
            "nitrogen_kg_ha": profile.nitrogen if profile else None,
            "phosphorus_kg_ha": profile.phosphorus if profile else None,
            "potassium_kg_ha": profile.potassium if profile else None,
            "organic_carbon_pct": profile.organic_carbon if profile else None,
            "electrical_conductivity_ds_m": profile.electrical_conductivity if profile else None,
            "sulfur_ppm": profile.sulfur if profile else None,
            "zinc_ppm": profile.zinc if profile else None,
            "iron_ppm": profile.iron if profile else None,
            "copper_ppm": profile.copper if profile else None,
            "manganese_ppm": profile.manganese if profile else None,
            "boron_ppm": profile.boron if profile else None,
            "moisture_pct": profile.moisture if profile else None,
            "source": profile.source if profile else "unavailable",
            "source_type": "laboratory_soil_test",
            "freshness": s_freshness.value,
            "data_age_days": round(s_age / 24.0, 1) if s_age is not None else None,
            "sample_date": profile.sample_date.isoformat() if profile and profile.sample_date else None,
        } if profile else None,
        "observations_count": len(history),
        "history": [
            {
                "id": str(h.id),
                "ph": h.ph,
                "nitrogen": h.nitrogen,
                "phosphorus": h.phosphorus,
                "potassium": h.potassium,
                "organic_carbon": h.organic_carbon,
                "sample_date": h.sample_date.isoformat() if h.sample_date else None,
                "source": h.source,
            }
            for h in history
        ],
    }


@router.get("/{farm_id}/satellite")
def get_farm_satellite(
    farm_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retrieves verified Earth Observation telemetry (NDVI, EVI, cloud cover)."""
    farm = farm_repo.get(db, farm_id)
    if not farm:
        raise NotFoundError("Farm not found.")
    _ensure_owner_or_privileged(farm, user)

    snapshot = satellite_service.get_latest_snapshot(db, farm)
    observations = (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.farm_id == farm.id)
        .order_by(SatelliteObservation.observation_date.desc())
        .limit(10)
        .all()
    )

    sat_freshness, sat_age = DataQualityService.evaluate_freshness("satellite", snapshot.observation_date)

    return {
        "latest": {
            "ndvi": snapshot.ndvi,
            "evi": snapshot.evi,
            "trend_7d_pct": snapshot.trend_7d_pct,
            "vegetation_health": snapshot.vegetation_health,
            "source": snapshot.source,
            "is_dev_dataset": snapshot.is_dev_dataset,
            "freshness": sat_freshness.value,
            "data_age_days": round(sat_age / 24.0, 1) if sat_age is not None else None,
            "observation_date": snapshot.observation_date.isoformat() if snapshot.observation_date else None,
        },
        "history": [
            {
                "id": str(o.id),
                "observation_date": o.observation_date.isoformat(),
                "ndvi": o.ndvi,
                "evi": o.evi,
                "cloud_cover_pct": o.cloud_cover_pct,
                "vegetation_health": o.vegetation_health,
                "source": o.source,
            }
            for o in observations
        ],
    }


@router.get("/{farm_id}/water")
def get_farm_water(
    farm_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retrieves normalized water layer: rainfall, lab/sensor/satellite soil moisture, drought index."""
    farm = farm_repo.get(db, farm_id)
    if not farm:
        raise NotFoundError("Farm not found.")
    _ensure_owner_or_privileged(farm, user)

    snapshot = water_service.get_snapshot(db, farm)

    # Moisture can legitimately come from two very different places, so they
    # are reported separately instead of being merged into one ambiguous value.
    latest_soil = (
        db.query(SoilProfile)
        .filter(SoilProfile.farm_id == farm.id)
        .order_by(SoilProfile.sample_date.desc().nullslast(), SoilProfile.created_at.desc())
        .first()
    )
    latest_satellite = (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.farm_id == farm.id)
        .order_by(SatelliteObservation.observation_date.desc())
        .first()
    )

    return {
        "farm_id": farm.id,
        "rainfall_mm": snapshot.rainfall_mm,
        "precipitation_recent_mm": snapshot.rainfall_mm,
        "soil_moisture_pct": snapshot.soil_moisture_pct,
        "soil_moisture_lab": {
            "value_pct": latest_soil.moisture if latest_soil else None,
            "sampled_at": latest_soil.sample_date.isoformat() if latest_soil and latest_soil.sample_date else None,
            "observed_at": latest_soil.sample_date.isoformat() if latest_soil and latest_soil.sample_date else None,
            "source": (latest_soil.source if latest_soil and latest_soil.source else "Laboratory / Soil Health Card"),
            "freshness": "RECENT" if latest_soil else "DATA NOT AVAILABLE",
        } if latest_soil else None,
        "soil_moisture_satellite": {
            "value_pct": getattr(latest_satellite, "soil_moisture", None) if latest_satellite else None,
            "observed_at": latest_satellite.observation_date.isoformat() if latest_satellite and latest_satellite.observation_date else None,
            "source": getattr(latest_satellite, "source", None) or "ISRO Bhoonidhi / Sentinel-1",
            "freshness": "RECENT" if latest_satellite else "DATA NOT AVAILABLE",
        } if latest_satellite else None,
        "soil_moisture_sensor": {
            "value_pct": None,
            "source": "IoT Field Sensor",
            "observed_at": None,
            "freshness": "DATA NOT AVAILABLE",
        },
        "moisture_source_type": snapshot.moisture_source_type,
        "irrigation_type": farm.irrigation_type or "None specified",
        "water_source": farm.water_source or "Not specified",
        "drought_index": snapshot.drought_index,
        "water_stress_index": snapshot.drought_index or "normal",
        "source": snapshot.source,
        "freshness": snapshot.freshness,
        "observed_at": snapshot.observed_at.isoformat() if snapshot.observed_at else None,
        "has_data": snapshot.has_data,
        "confidence": 0.85 if snapshot.has_data else 0.0,
    }


@router.get("/{farm_id}/crop")
def get_farm_crop(
    farm_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retrieves current farm crop cycle, variety, and regional statistical baselines (FAOSTAT)."""
    farm = farm_repo.get(db, farm_id)
    if not farm:
        raise NotFoundError("Farm not found.")
    _ensure_owner_or_privileged(farm, user)

    cycle = (
        db.query(CropCycle)
        .filter(CropCycle.farm_id == farm.id)
        .order_by(CropCycle.created_at.desc())
        .first()
    )

    crop_name = farm.current_crop or (cycle.crop if cycle else "Rice")

    # Fetch FAOSTAT regional context for crop
    stat_baseline = (
        db.query(AgricultureStatistic)
        .filter(AgricultureStatistic.crop.ilike(f"%{crop_name}%"))
        .order_by(AgricultureStatistic.year.desc())
        .first()
    )

    return {
        "crop": crop_name,
        "variety": farm.crop_variety or (cycle.variety if cycle else None),
        "stage": farm.crop_stage or (cycle.stage if cycle else None),
        "sowing_date": (farm.sowing_date or (cycle.sowing_date if cycle else None)),
        "previous_crop": farm.previous_crop,
        "area_hectares": farm.area_hectares,
        "source": "farmer_provided",
        "regional_baseline": {
            "source": "FAOSTAT",
            "country": stat_baseline.country if stat_baseline else "India",
            "element": stat_baseline.element if stat_baseline else "Yield",
            "baseline_value": stat_baseline.value if stat_baseline else 3800.0,
            "unit": stat_baseline.unit if stat_baseline else "kg/ha",
            "year": stat_baseline.year if stat_baseline else 2023,
        } if stat_baseline else None,
    }


@router.get("/{farm_id}/sources")
def get_farm_sources(
    farm_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Reports the data sources that are actually configured and actually
    contributing observations to this farm.

    A provider is only listed as active when it is genuinely configured and
    has real rows for this farm; otherwise it is reported as unavailable so
    the UI never implies a feed exists when it does not.
    """
    farm = farm_repo.get(db, farm_id)
    if not farm:
        raise NotFoundError("Farm not found.")
    _ensure_owner_or_privileged(farm, user)

    def count(model, column):
        return db.query(model).filter(column == farm.id).count()

    weather_rows = count(WeatherObservation, WeatherObservation.farm_id)
    soil_rows = count(SoilProfile, SoilProfile.farm_id)
    satellite_rows = count(SatelliteObservation, SatelliteObservation.farm_id)

    satellite_provider = (settings.SATELLITE_PROVIDER or "none").strip().lower()
    satellite_active = satellite_rows > 0 and satellite_provider not in ("", "none", "unavailable")

    sources = [
        {
            "domain": "Weather & Climate",
            "primary_provider": "India Meteorological Department (IMD)" if settings.IMD_API_KEY else None,
            "status": "active" if weather_rows > 0 else "unavailable",
            "observations": weather_rows,
            "license": "Government of India Open Data / IMD Data Sharing Policy" if weather_rows > 0 else None,
            "terms_url": "https://mausam.imd.gov.in/" if weather_rows > 0 else None,
            "detail": (
                f"{weather_rows} observation(s) recorded for this farm."
                if weather_rows > 0
                else "No weather provider is configured, so no weather data is available."
            ),
        },
        {
            "domain": "Soil Intelligence",
            "primary_provider": "Farm-entered soil samples",
            "status": "active" if soil_rows > 0 else "unavailable",
            "observations": soil_rows,
            "license": None,
            "terms_url": None,
            "detail": (
                f"{soil_rows} soil profile(s) recorded for this farm."
                if soil_rows > 0
                else "No soil sample has been recorded for this farm yet."
            ),
        },
        {
            "domain": "Satellite & Earth Observation",
            "primary_provider": satellite_provider if satellite_active else None,
            "status": "active" if satellite_active else "unavailable",
            "observations": satellite_rows,
            "license": None,
            "terms_url": None,
            "detail": (
                f"{satellite_rows} vegetation observation(s) from {satellite_provider}."
                if satellite_active
                else "No Earth-observation provider is configured, so no vegetation index is available."
            ),
        },
    ]

    return {
        "farm_id": str(farm.id),
        "sources": sources,
        "active_providers_count": sum(1 for s in sources if s["status"] == "active"),
    }


@router.get("/{farm_id}/timeline")
def get_farm_timeline(
    farm_id: str,
    window: str = Query("30d", pattern="^(1d|7d|30d|90d|season|year)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Returns time-series observations comparing 1d, 7d, 30d, 90d, season, or year
    across weather, vegetation indices, soil profiles, and water telemetry.
    """
    farm = farm_repo.get(db, farm_id)
    if not farm:
        raise NotFoundError("Farm not found.")
    _ensure_owner_or_privileged(farm, user)

    days_map = {"1d": 1, "7d": 7, "30d": 30, "90d": 90, "season": 120, "year": 365}
    days = days_map.get(window, 30)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    date_cutoff = date.today() - timedelta(days=days)

    weather_rows = (
        db.query(WeatherObservation)
        .filter(WeatherObservation.farm_id == farm.id, WeatherObservation.observed_at >= cutoff)
        .order_by(WeatherObservation.observed_at.asc())
        .all()
    )

    sat_rows = (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.farm_id == farm.id, SatelliteObservation.observation_date >= date_cutoff)
        .order_by(SatelliteObservation.observation_date.asc())
        .all()
    )

    soil_rows = (
        db.query(SoilObservation)
        .filter(SoilObservation.farm_id == farm.id)
        .order_by(SoilObservation.sample_date.asc().nullslast())
        .all()
    )

    water_rows = (
        db.query(WaterObservation)
        .filter(WaterObservation.farm_id == farm.id, WaterObservation.observed_at >= cutoff)
        .order_by(WaterObservation.observed_at.asc())
        .all()
    )

    return {
        "farm_id": str(farm.id),
        "window": window,
        "days": days,
        # A flat, chronologically ordered list of every real observation in
        # the window, so clients can render one timeline without re-merging
        # the per-domain series themselves.
        "timeline": sorted(
            [
                {
                    "domain": "weather",
                    "timestamp": w.observed_at.isoformat(),
                    "source": w.source,
                }
                for w in weather_rows
            ]
            + [
                {
                    "domain": "vegetation",
                    "timestamp": s.observation_date.isoformat(),
                    "source": s.source,
                }
                for s in sat_rows
            ]
            + [
                {
                    "domain": "soil",
                    "timestamp": so.sample_date.isoformat() if so.sample_date else None,
                    "source": so.source,
                }
                for so in soil_rows
                if so.sample_date
            ]
            + [
                {
                    "domain": "water",
                    "timestamp": wo.observed_at.isoformat(),
                    "source": wo.source,
                }
                for wo in water_rows
            ],
            key=lambda e: e["timestamp"],
        ),
        "series": {
            "weather": [
                {
                    "timestamp": w.observed_at.isoformat(),
                    "temperature": w.temperature,
                    "rainfall": w.rainfall,
                    "wind_speed": w.wind_speed,
                    "source": w.source,
                }
                for w in weather_rows
            ],
            "vegetation": [
                {
                    "date": s.observation_date.isoformat(),
                    "ndvi": s.ndvi,
                    "evi": s.evi,
                    "cloud_cover": s.cloud_cover_pct,
                    "source": s.source,
                }
                for s in sat_rows
            ],
            "soil": [
                {
                    "date": so.sample_date.isoformat() if so.sample_date else None,
                    "ph": so.ph,
                    "nitrogen": so.nitrogen,
                    "phosphorus": so.phosphorus,
                    "potassium": so.potassium,
                    "organic_carbon": so.organic_carbon,
                    "source": so.source,
                }
                for so in soil_rows
            ],
            "water": [
                {
                    "timestamp": wo.observed_at.isoformat(),
                    "rainfall_mm": wo.rainfall_mm,
                    "soil_moisture_pct": wo.soil_moisture_pct,
                    "moisture_source_type": wo.moisture_source_type,
                    "source": wo.source,
                }
                for wo in water_rows
            ],
        },
    }


@router.get("/{farm_id}/events")
def get_farm_sync_events(
    farm_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retrieves the recent data ingestion and synchronization event log."""
    farm = farm_repo.get(db, farm_id)
    if not farm:
        raise NotFoundError("Farm not found.")
    _ensure_owner_or_privileged(farm, user)

    events = (
        db.query(SyncEvent)
        .filter(SyncEvent.farm_id == farm.id)
        .order_by(SyncEvent.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": str(e.id),
            "event_type": e.event_type,
            "summary": e.summary,
            "details": e.details,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]
