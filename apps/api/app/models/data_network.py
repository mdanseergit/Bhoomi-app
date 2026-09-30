import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class DataProvider(UUIDPKMixin, TimestampMixin, Base):
    """Database-driven country & regional data provider registry."""

    __tablename__ = "data_providers"

    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False, default="Global")
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)  # State/Province or None if national/global
    data_type: Mapped[str] = mapped_column(String(60), nullable=False)  # weather, soil, satellite, statistics, water, climate
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    authentication_type: Mapped[str] = mapped_column(String(50), default="none")  # none, api_key, oauth2, bearer_token
    api_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 1 = highest / national primary, 2 = regional, 3 = global fallback
    refresh_interval_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="healthy", nullable=False)  # healthy, degraded, failed, auth_required, disabled
    auth_status: Mapped[str] = mapped_column(String(60), default="configured", nullable=False)  # active, authentication_required, unconfigured
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_success: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    license: Mapped[str | None] = mapped_column(String(200), nullable=True)
    terms_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    documentation_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    capabilities: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    sync_runs = relationship("ProviderSyncRun", back_populates="provider", cascade="all, delete-orphan")


class ProviderSyncRun(UUIDPKMixin, TimestampMixin, Base):
    """Execution history of synchronization runs per provider."""

    __tablename__ = "provider_sync_runs"

    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("data_providers.id"), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(40), default="scheduled")  # scheduled, manual, farm_access, failover
    status: Mapped[str] = mapped_column(String(40), default="running")  # running, success, failed, degraded
    records_ingested: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    provider = relationship("DataProvider", back_populates="sync_runs")


class RawObservation(UUIDPKMixin, TimestampMixin, Base):
    """Immutable log of raw external payloads received before normalization."""

    __tablename__ = "raw_observations"

    provider_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("data_providers.id"), nullable=True, index=True)
    source_dataset: Mapped[str] = mapped_column(String(100), nullable=False)
    external_record_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    farm_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("farms.id"), nullable=True, index=True)
    data_type: Mapped[str] = mapped_column(String(60), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class WaterObservation(UUIDPKMixin, TimestampMixin, Base):
    """Normalized water layer: rainfall, soil moisture, irrigation, drought indicators."""

    __tablename__ = "water_observations"

    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("farms.id"), nullable=False, index=True)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("data_providers.id"), nullable=True)
    rainfall_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    soil_moisture_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    moisture_source_type: Mapped[str] = mapped_column(String(50), default="modelled")  # lab, field_sensor, satellite_estimate, modelled
    irrigation_applied_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    drought_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(60), default="unknown")
    quality_status: Mapped[str] = mapped_column(String(30), default="good")  # good, warning, stale, invalid
    freshness_status: Mapped[str] = mapped_column(String(30), default="unknown")  # live, recent, stale, outdated, unknown
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class AgricultureStatistic(UUIDPKMixin, TimestampMixin, Base):
    """Regional & country-level historical statistics (e.g. FAOSTAT baselines)."""

    __tablename__ = "agriculture_statistics"

    country: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    crop: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    element: Mapped[str] = mapped_column(String(60), nullable=False)  # Area harvested, Production, Yield
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    source: Mapped[str] = mapped_column(String(60), default="FAOSTAT")
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class DataQualityRecord(UUIDPKMixin, TimestampMixin, Base):
    """Audit records created by DataQualityService for validation and freshness tracking."""

    __tablename__ = "data_quality_records"

    observation_type: Mapped[str] = mapped_column(String(60), nullable=False)  # weather, soil, satellite, water
    observation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    quality_status: Mapped[str] = mapped_column(String(30), nullable=False)  # good, warning, stale, invalid
    freshness_status: Mapped[str] = mapped_column(String(30), nullable=False)  # live, recent, stale, outdated, unknown
    data_age_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    issues: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class DataConflict(UUIDPKMixin, TimestampMixin, Base):
    """Tracks conflicting observations between multiple providers for the same parameter."""

    __tablename__ = "data_conflicts"

    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("farms.id"), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(60), nullable=False)
    provider_a_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    value_a: Mapped[str] = mapped_column(String(200), nullable=False)
    provider_b_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    value_b: Mapped[str] = mapped_column(String(200), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    resolution_status: Mapped[str] = mapped_column(String(40), default="unresolved")  # unresolved, priority_selected, resolved_by_rule


class FarmDataSnapshot(UUIDPKMixin, TimestampMixin, Base):
    """Auditable, immutable snapshot of farm conditions assembled before AI generation."""

    __tablename__ = "farm_data_snapshots"

    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("farms.id"), nullable=False, index=True)
    snapshot_version: Mapped[str] = mapped_column(String(40), nullable=False)
    weather_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    soil_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    satellite_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    water_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    crop_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    missing_fields: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    source_attributions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class SyncEvent(UUIDPKMixin, TimestampMixin, Base):
    """Internal real-time event log when meaningful new data arrives."""

    __tablename__ = "sync_events"

    farm_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("farms.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)  # DATA_INGESTED, SATELLITE_UPDATED, WEATHER_ALERT, SOIL_UPDATED, DISEASE_ANALYZED
    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
