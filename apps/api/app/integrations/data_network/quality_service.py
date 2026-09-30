"""
Data Quality Engine & Freshness Evaluator (BHOOMI Data Network).
Ensures only valid, audited, and correctly labeled observations reach the AI.
"""
from datetime import datetime, date, timezone
from typing import Optional, Any
from app.integrations.data_network.base import (
    FreshnessState,
    QualityStatus,
    CanonicalWeather,
    CanonicalSoil,
    CanonicalSatellite,
    CanonicalWater,
)


class DataQualityService:
    @staticmethod
    def evaluate_freshness(data_type: str, observed_at: Optional[datetime | date]) -> tuple[FreshnessState, Optional[float]]:
        """
        Determines freshness state and age in hours based on natural update frequencies.
        Never falsely claims 'live' when data is historical or periodic.
        """
        if not observed_at:
            return FreshnessState.UNKNOWN, None

        now = datetime.now(timezone.utc)
        if isinstance(observed_at, date) and not isinstance(observed_at, datetime):
            obs_dt = datetime(observed_at.year, observed_at.month, observed_at.day, 12, 0, 0, tzinfo=timezone.utc)
        elif observed_at.tzinfo is None:
            obs_dt = observed_at.replace(tzinfo=timezone.utc)
        else:
            obs_dt = observed_at

        diff = now - obs_dt
        age_hours = max(0.0, diff.total_seconds() / 3600.0)
        dt = data_type.lower()

        if dt in ("weather", "current_weather", "climate"):
            if age_hours <= 1.0:
                return FreshnessState.LIVE, round(age_hours, 2)
            elif age_hours <= 6.0:
                return FreshnessState.RECENT, round(age_hours, 2)
            elif age_hours <= 24.0:
                return FreshnessState.STALE, round(age_hours, 2)
            else:
                return FreshnessState.OUTDATED, round(age_hours, 2)

        elif dt in ("forecast", "weather_forecast"):
            if age_hours <= 12.0:
                return FreshnessState.RECENT, round(age_hours, 2)
            elif age_hours <= 48.0:
                return FreshnessState.STALE, round(age_hours, 2)
            else:
                return FreshnessState.OUTDATED, round(age_hours, 2)

        elif dt in ("satellite", "ndvi", "vegetation"):
            age_days = age_hours / 24.0
            if age_days <= 5.0:
                return FreshnessState.RECENT, round(age_hours, 2)
            elif age_days <= 16.0:
                return FreshnessState.STALE, round(age_hours, 2)
            else:
                return FreshnessState.OUTDATED, round(age_hours, 2)

        elif dt in ("soil", "soil_profile", "soil_health"):
            age_days = age_hours / 24.0
            if age_days <= 180.0:
                return FreshnessState.RECENT, round(age_hours, 2)
            elif age_days <= 365.0:
                return FreshnessState.STALE, round(age_hours, 2)
            else:
                return FreshnessState.OUTDATED, round(age_hours, 2)

        elif dt in ("crop", "crop_cycle"):
            age_days = age_hours / 24.0
            if age_days <= 14.0:
                return FreshnessState.LIVE, round(age_hours, 2)
            elif age_days <= 45.0:
                return FreshnessState.RECENT, round(age_hours, 2)
            else:
                return FreshnessState.STALE, round(age_hours, 2)

        elif dt in ("water", "soil_moisture"):
            if age_hours <= 3.0:
                return FreshnessState.LIVE, round(age_hours, 2)
            elif age_hours <= 24.0:
                return FreshnessState.RECENT, round(age_hours, 2)
            elif age_hours <= 72.0:
                return FreshnessState.STALE, round(age_hours, 2)
            else:
                return FreshnessState.OUTDATED, round(age_hours, 2)

        return FreshnessState.RECENT if age_hours <= 48.0 else FreshnessState.STALE, round(age_hours, 2)

    @staticmethod
    def validate_weather(reading: CanonicalWeather) -> tuple[QualityStatus, list[str]]:
        issues = []
        status = QualityStatus.GOOD

        if reading.temperature_c is not None:
            if not (-50.0 <= reading.temperature_c <= 60.0):
                issues.append(f"Temperature {reading.temperature_c}°C outside plausible physical range [-50, 60]")
                status = QualityStatus.INVALID
        if reading.humidity_pct is not None:
            if not (0.0 <= reading.humidity_pct <= 100.0):
                issues.append(f"Relative humidity {reading.humidity_pct}% outside valid range [0, 100]")
                status = QualityStatus.INVALID
        if reading.rainfall_mm is not None:
            if reading.rainfall_mm < 0.0 or reading.rainfall_mm > 1500.0:
                issues.append(f"Rainfall {reading.rainfall_mm}mm invalid or extreme")
                status = QualityStatus.INVALID if reading.rainfall_mm < 0 else QualityStatus.WARNING
        if reading.wind_speed_ms is not None:
            if reading.wind_speed_ms < 0.0 or reading.wind_speed_ms > 120.0:
                issues.append(f"Wind speed {reading.wind_speed_ms}m/s invalid")
                status = QualityStatus.INVALID

        if not issues and reading.temperature_c is None and reading.humidity_pct is None and reading.rainfall_mm is None:
            issues.append("Observation contains no atmospheric parameters")
            status = QualityStatus.WARNING

        return status, issues

    @staticmethod
    def validate_soil(sample: CanonicalSoil) -> tuple[QualityStatus, list[str]]:
        issues = []
        status = QualityStatus.GOOD

        if sample.ph is not None:
            if not (2.5 <= sample.ph <= 11.5):
                issues.append(f"Soil pH {sample.ph} outside plausible agricultural range [2.5, 11.5]")
                status = QualityStatus.INVALID
        if sample.nitrogen_kg_ha is not None and sample.nitrogen_kg_ha < 0:
            issues.append("Available Nitrogen cannot be negative")
            status = QualityStatus.INVALID
        if sample.phosphorus_kg_ha is not None and sample.phosphorus_kg_ha < 0:
            issues.append("Available Phosphorus cannot be negative")
            status = QualityStatus.INVALID
        if sample.potassium_kg_ha is not None and sample.potassium_kg_ha < 0:
            issues.append("Available Potassium cannot be negative")
            status = QualityStatus.INVALID
        if sample.organic_carbon_pct is not None:
            if sample.organic_carbon_pct < 0 or sample.organic_carbon_pct > 25.0:
                issues.append(f"Organic carbon {sample.organic_carbon_pct}% outside typical bounds [0, 25]")
                status = QualityStatus.WARNING if sample.organic_carbon_pct > 0 else QualityStatus.INVALID
        if sample.electrical_conductivity_ds_m is not None and sample.electrical_conductivity_ds_m < 0:
            issues.append("Electrical conductivity cannot be negative")
            status = QualityStatus.INVALID

        return status, issues

    @staticmethod
    def validate_satellite(obs: CanonicalSatellite) -> tuple[QualityStatus, list[str]]:
        issues = []
        status = QualityStatus.GOOD

        if obs.ndvi is not None:
            if not (-1.0 <= obs.ndvi <= 1.0):
                issues.append(f"NDVI {obs.ndvi} outside mathematical limits [-1.0, 1.0]")
                status = QualityStatus.INVALID
        if obs.evi is not None:
            if not (-1.0 <= obs.evi <= 2.5):
                issues.append(f"EVI {obs.evi} outside expected limits [-1.0, 2.5]")
                status = QualityStatus.WARNING
        if obs.cloud_cover_pct is not None:
            if not (0.0 <= obs.cloud_cover_pct <= 100.0):
                issues.append(f"Cloud cover {obs.cloud_cover_pct}% outside [0, 100]")
                status = QualityStatus.INVALID
            elif obs.cloud_cover_pct > 80.0:
                issues.append(f"High cloud obstruction ({obs.cloud_cover_pct}%); vegetation index may be degraded")
                status = QualityStatus.WARNING

        return status, issues
