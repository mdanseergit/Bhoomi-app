from sqlalchemy import Date, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from geoalchemy2 import Geometry

from app.core.database import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPKMixin


class Farm(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "farms"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(80), nullable=False)
    district: Mapped[str] = mapped_column(String(80), nullable=False)
    taluk: Mapped[str | None] = mapped_column(String(80), nullable=True)
    village: Mapped[str | None] = mapped_column(String(80), nullable=True)

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    # Point geometry (SRID 4326) for spatial indexing / queries.
    location: Mapped[str | None] = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    boundary_polygon: Mapped[str | None] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326), nullable=True
    )

    area_hectares: Mapped[float] = mapped_column(Float, nullable=False)
    soil_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    irrigation_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    water_source: Mapped[str | None] = mapped_column(String(60), nullable=True)

    current_crop: Mapped[str | None] = mapped_column(String(60), nullable=True)
    crop_variety: Mapped[str | None] = mapped_column(String(80), nullable=True)
    crop_stage: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sowing_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    previous_crop: Mapped[str | None] = mapped_column(String(60), nullable=True)
