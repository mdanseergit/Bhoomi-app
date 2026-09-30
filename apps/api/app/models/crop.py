from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class CropVariety(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "crop_varieties"

    crop: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    variety_name: Mapped[str] = mapped_column(String(80), nullable=False)
    duration_days: Mapped[int | None] = mapped_column(nullable=True)
    recommended_states: Mapped[str | None] = mapped_column(String(255), nullable=True)


class CropCycle(UUIDPKMixin, TimestampMixin, Base):
    """A single sowing-to-harvest cycle for a farm; drives crop-stage logic."""

    __tablename__ = "crop_cycles"

    farm_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("farms.id"), nullable=False, index=True)
    crop: Mapped[str] = mapped_column(String(60), nullable=False)
    variety: Mapped[str | None] = mapped_column(String(80), nullable=True)
    stage: Mapped[str] = mapped_column(String(40), default="sowing")
    sowing_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    expected_harvest_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | completed | failed
