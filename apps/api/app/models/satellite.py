from sqlalchemy import Date, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class SatelliteObservation(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "satellite_observations"

    farm_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("farms.id"), nullable=False, index=True)
    observation_date: Mapped[Date] = mapped_column(Date, nullable=False)
    ndvi: Mapped[float | None] = mapped_column(Float, nullable=True)
    evi: Mapped[float | None] = mapped_column(Float, nullable=True)
    vegetation_health: Mapped[str | None] = mapped_column(String(20), nullable=True)  # poor|fair|good|excellent
    cloud_cover_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(60), default="unavailable")
    is_dev_dataset: Mapped[bool] = mapped_column(default=False)
    freshness_status: Mapped[str] = mapped_column(String(30), default="unknown")
    quality_status: Mapped[str] = mapped_column(String(30), default="good")
    external_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    ingested_at: Mapped[Date | None] = mapped_column(Date, nullable=True)
