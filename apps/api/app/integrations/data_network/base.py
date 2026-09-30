"""
Universal Data Provider Abstraction & Canonical Schemas (BHOOMI Data Network).
Every external agricultural data source implements DataProvider.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from enum import Enum
from typing import Any, Optional
import uuid


class FreshnessState(str, Enum):
    LIVE = "LIVE"
    RECENT = "RECENT"
    STALE = "STALE"
    OUTDATED = "OUTDATED"
    UNKNOWN = "UNKNOWN"


class QualityStatus(str, Enum):
    GOOD = "GOOD"
    WARNING = "WARNING"
    STALE = "STALE"
    INVALID = "INVALID"


@dataclass
class UnitConversionRecord:
    original_value: Any
    original_unit: str
    normalized_value: Any
    normalized_unit: str
    conversion_method: str


@dataclass
class ProvenanceMetadata:
    provider_name: str
    source_dataset: str
    external_id: Optional[str] = None
    observed_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_verified_at: Optional[datetime] = None
    license: Optional[str] = None
    terms_url: Optional[str] = None
    attribution: Optional[str] = None
    quality_score: float = 1.0
    freshness: FreshnessState = FreshnessState.UNKNOWN
    data_age_hours: Optional[float] = None
    confidence: float = 1.0
    processing_version: str = "v1.0"


@dataclass
class CanonicalWeather:
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    rainfall_mm: Optional[float] = None
    rain_probability_pct: Optional[float] = None
    wind_speed_ms: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    condition: Optional[str] = None
    warning_level: Optional[str] = "none"
    solar_radiation_mj_m2: Optional[float] = None
    observed_at: Optional[datetime] = None
    source: str = "unknown"
    freshness: FreshnessState = FreshnessState.UNKNOWN
    quality: QualityStatus = QualityStatus.GOOD
    provenance: Optional[ProvenanceMetadata] = None
    conversions: list[UnitConversionRecord] = field(default_factory=list)


@dataclass
class CanonicalSoil:
    ph: Optional[float] = None
    nitrogen_kg_ha: Optional[float] = None
    phosphorus_kg_ha: Optional[float] = None
    potassium_kg_ha: Optional[float] = None
    organic_carbon_pct: Optional[float] = None
    electrical_conductivity_ds_m: Optional[float] = None
    sulfur_ppm: Optional[float] = None
    zinc_ppm: Optional[float] = None
    boron_ppm: Optional[float] = None
    iron_ppm: Optional[float] = None
    manganese_ppm: Optional[float] = None
    copper_ppm: Optional[float] = None
    moisture_pct: Optional[float] = None
    moisture_source_type: str = "lab"  # lab | field_sensor | satellite_estimate | modelled
    sample_date: Optional[date] = None
    source: str = "unknown"
    freshness: FreshnessState = FreshnessState.UNKNOWN
    quality: QualityStatus = QualityStatus.GOOD
    provenance: Optional[ProvenanceMetadata] = None
    conversions: list[UnitConversionRecord] = field(default_factory=list)


@dataclass
class CanonicalSatellite:
    ndvi: Optional[float] = None
    evi: Optional[float] = None
    vegetation_health: Optional[str] = None  # poor | fair | good | excellent
    cloud_cover_pct: Optional[float] = None
    observation_date: Optional[date] = None
    satellite_name: str = "Sentinel-2"
    source: str = "unknown"
    is_dev_dataset: bool = False
    freshness: FreshnessState = FreshnessState.UNKNOWN
    quality: QualityStatus = QualityStatus.GOOD
    provenance: Optional[ProvenanceMetadata] = None


@dataclass
class CanonicalWater:
    rainfall_mm: Optional[float] = None
    soil_moisture_pct: Optional[float] = None
    moisture_source_type: str = "modelled"  # lab | field_sensor | satellite_estimate | modelled
    irrigation_applied_mm: Optional[float] = None
    drought_index: Optional[float] = None
    observed_at: Optional[datetime] = None
    source: str = "unknown"
    freshness: FreshnessState = FreshnessState.UNKNOWN
    quality: QualityStatus = QualityStatus.GOOD
    provenance: Optional[ProvenanceMetadata] = None


@dataclass
class CanonicalCrop:
    crop_name: str
    variety: Optional[str] = None
    crop_stage: Optional[str] = None
    sowing_date: Optional[date] = None
    source: str = "farmer_provided"
    freshness: FreshnessState = FreshnessState.RECENT
    quality: QualityStatus = QualityStatus.GOOD


@dataclass
class CanonicalStatistic:
    country: str
    region: Optional[str] = None
    crop: str = "all"
    year: int = 2024
    element: str = "production"  # area_harvested | production | yield
    value: float = 0.0
    unit: str = "tonnes"
    source: str = "FAOSTAT"
    observed_at: Optional[datetime] = None


class DataProvider(ABC):
    """Universal interface that all external agricultural data sources must implement."""

    name: str = "base_provider"
    data_type: str = "unknown"  # weather, soil, satellite, statistics, water, climate, crop, disease
    country_scope: str = "Global"
    region_scope: Optional[str] = None
    is_fallback: bool = False

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection or verify configuration."""
        ...

    @abstractmethod
    def health_check(self) -> dict:
        """Inspect provider availability, latency, and quota."""
        ...

    @abstractmethod
    def discover_capabilities(self) -> dict:
        """Returns declared capabilities and parameters supported."""
        ...

    @abstractmethod
    def fetch(self, **kwargs) -> Any:
        """Execute external API or query and retrieve raw payload."""
        ...

    @abstractmethod
    def normalize(self, raw_data: Any) -> Any:
        """Convert raw provider payload into canonical schema."""
        ...

    @abstractmethod
    def validate(self, data: Any) -> tuple[bool, list[str]]:
        """Verify ranges, temporal logic, and completeness."""
        ...

    @abstractmethod
    def store(self, db: Any, data: Any, farm_id: Optional[uuid.UUID] = None) -> Any:
        """Persist normalized observation with provenance."""
        ...

    @abstractmethod
    def get_last_sync(self) -> Optional[datetime]:
        ...

    @abstractmethod
    def get_next_sync(self) -> Optional[datetime]:
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Clean up connection pool / sessions."""
        ...
