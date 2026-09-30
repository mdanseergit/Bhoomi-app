from sqlalchemy import Float, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class FarmRiskScore(UUIDPKMixin, TimestampMixin, Base):
    """Point-in-time snapshot of the BHOOMI Intelligence Score and its
    explainable breakdown, produced by the deterministic risk engine."""

    __tablename__ = "farm_risk_scores"

    farm_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("farms.id"), nullable=False, index=True)

    # Nullable: no score is stored when the farm has no real observations yet.
    farm_health_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    climate_risk: Mapped[str] = mapped_column(String(20), nullable=False)
    water_stress: Mapped[str] = mapped_column(String(20), nullable=False)
    disease_risk: Mapped[str] = mapped_column(String(20), nullable=False)
    vegetation_stress: Mapped[str] = mapped_column(String(20), nullable=False)
    soil_health: Mapped[str] = mapped_column(String(20), nullable=False)

    breakdown: Mapped[dict] = mapped_column(JSON, nullable=False)  # component weights/scores
    factors: Mapped[dict] = mapped_column(JSON, nullable=False)  # explainability factors
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False)  # source snapshot used
