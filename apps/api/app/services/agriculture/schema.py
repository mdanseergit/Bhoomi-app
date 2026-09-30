"""
Shared structures passed through the BHOOMI data-fusion pipeline:

  weather + soil + satellite + crop + farm metadata + history
        -> normalization -> feature extraction -> risk engine
        -> advisory engine -> LLM explanation

Every stage consumes/produces plain, serializable structures so results can
be logged, cached, tested and replayed deterministically.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

Severity = Literal["low", "moderate", "high", "critical"]


@dataclass
class WeatherSnapshot:
    temperature_c: float | None
    humidity_pct: float | None
    rainfall_mm: float | None
    rain_probability_pct: float | None
    wind_speed_kmh: float | None
    condition: str | None
    warning_level: str | None
    source: str
    observed_at: datetime | None
    is_stale: bool = False

    @property
    def has_observations(self) -> bool:
        """True when at least one measured weather value came from a real feed."""
        return any(
            v is not None
            for v in (
                self.temperature_c,
                self.humidity_pct,
                self.rainfall_mm,
                self.rain_probability_pct,
                self.wind_speed_kmh,
            )
        )


@dataclass
class SoilSnapshot:
    ph: float | None
    nitrogen: float | None
    phosphorus: float | None
    potassium: float | None
    organic_carbon: float | None
    moisture: float | None
    source: str
    sample_date: date | None

    @property
    def has_observations(self) -> bool:
        return any(
            v is not None
            for v in (
                self.ph,
                self.nitrogen,
                self.phosphorus,
                self.potassium,
                self.organic_carbon,
                self.moisture,
            )
        )


@dataclass
class VegetationSnapshot:
    ndvi: float | None
    evi: float | None
    trend_7d_pct: float | None
    vegetation_health: str | None
    source: str
    observation_date: date | None
    is_dev_dataset: bool = False


@dataclass
class FarmContext:
    farm_id: str
    crop: str | None
    crop_stage: str | None
    previous_crop: str | None
    irrigation_type: str | None
    water_source: str | None
    area_hectares: float
    state: str
    district: str


@dataclass
class Factor:
    name: str
    impact: float  # relative contribution, 0..1
    detail: str = ""


@dataclass
class ServiceResult:
    score: float
    severity: Severity
    factors: list[Factor] = field(default_factory=list)
    # False when the component had no real observations to score, in which
    # case `score` is a neutral placeholder and MUST NOT be presented to a
    # user as a measurement.
    has_data: bool = True

    def to_json(self) -> dict:
        return {
            "score": round(self.score, 1),
            "severity": self.severity,
            "has_data": self.has_data,
            "factors": [
                {"name": f.name, "impact": round(f.impact, 2), "detail": f.detail} for f in self.factors
            ],
        }
