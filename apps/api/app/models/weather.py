from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class WeatherObservation(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "weather_observations"

    farm_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("farms.id"), nullable=False, index=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    rainfall: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    weather_condition: Mapped[str | None] = mapped_column(String(60), nullable=True)
    warning_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source: Mapped[str] = mapped_column(String(40), default="imd")
    freshness_status: Mapped[str] = mapped_column(String(30), default="unknown")
    quality_status: Mapped[str] = mapped_column(String(30), default="good")
    external_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    observed_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WeatherForecast(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "weather_forecasts"

    farm_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("farms.id"), nullable=False, index=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    rain_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    rainfall_expected_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    weather_condition: Mapped[str | None] = mapped_column(String(60), nullable=True)
    warning_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source: Mapped[str] = mapped_column(String(40), default="imd")
    forecast_time: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
