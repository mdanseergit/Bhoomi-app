from sqlalchemy import Date, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class SoilProfile(UUIDPKMixin, TimestampMixin, Base):
    """Latest normalized soil profile snapshot for a farm."""

    __tablename__ = "soil_profiles"

    farm_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("farms.id"), nullable=False, index=True)

    ph: Mapped[float | None] = mapped_column(Float, nullable=True)
    nitrogen: Mapped[float | None] = mapped_column(Float, nullable=True)  # kg/ha
    phosphorus: Mapped[float | None] = mapped_column(Float, nullable=True)  # kg/ha
    potassium: Mapped[float | None] = mapped_column(Float, nullable=True)  # kg/ha
    organic_carbon: Mapped[float | None] = mapped_column(Float, nullable=True)  # %
    electrical_conductivity: Mapped[float | None] = mapped_column(Float, nullable=True)  # dS/m
    sulfur: Mapped[float | None] = mapped_column(Float, nullable=True)  # ppm
    zinc: Mapped[float | None] = mapped_column(Float, nullable=True)  # ppm
    iron: Mapped[float | None] = mapped_column(Float, nullable=True)
    copper: Mapped[float | None] = mapped_column(Float, nullable=True)
    manganese: Mapped[float | None] = mapped_column(Float, nullable=True)
    boron: Mapped[float | None] = mapped_column(Float, nullable=True)
    moisture: Mapped[float | None] = mapped_column(Float, nullable=True)  # %

    source: Mapped[str] = mapped_column(String(40), default="manual")  # manual | csv_import | api | seed
    sample_date: Mapped[str | None] = mapped_column(Date, nullable=True)


class SoilObservation(UUIDPKMixin, TimestampMixin, Base):
    """Historical time-series of soil samples (append-only log)."""

    __tablename__ = "soil_observations"

    farm_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("farms.id"), nullable=False, index=True)
    ph: Mapped[float | None] = mapped_column(Float, nullable=True)
    nitrogen: Mapped[float | None] = mapped_column(Float, nullable=True)
    phosphorus: Mapped[float | None] = mapped_column(Float, nullable=True)
    potassium: Mapped[float | None] = mapped_column(Float, nullable=True)
    organic_carbon: Mapped[float | None] = mapped_column(Float, nullable=True)
    moisture: Mapped[float | None] = mapped_column(Float, nullable=True)
    electrical_conductivity: Mapped[float | None] = mapped_column(Float, nullable=True)
    sulfur: Mapped[float | None] = mapped_column(Float, nullable=True)
    zinc: Mapped[float | None] = mapped_column(Float, nullable=True)
    iron: Mapped[float | None] = mapped_column(Float, nullable=True)
    copper: Mapped[float | None] = mapped_column(Float, nullable=True)
    manganese: Mapped[float | None] = mapped_column(Float, nullable=True)
    boron: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(40), default="manual")
    freshness_status: Mapped[str] = mapped_column(String(30), default="unknown")
    quality_status: Mapped[str] = mapped_column(String(30), default="good")
    external_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    sample_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    ingested_at: Mapped[Date | None] = mapped_column(Date, nullable=True)
