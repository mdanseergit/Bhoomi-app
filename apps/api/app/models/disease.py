from sqlalchemy import Float, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class DiseaseModel(UUIDPKMixin, TimestampMixin, Base):
    """Registered ML model used for disease inference (see /ml/disease)."""

    __tablename__ = "disease_models"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    architecture: Mapped[str] = mapped_column(String(60), default="heuristic-baseline")
    crop_scope: Mapped[str] = mapped_column(String(120), default="general")
    is_dev_model: Mapped[bool] = mapped_column(default=True)
    accuracy_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")


class DiseaseScan(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "disease_scans"

    farm_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("farms.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    image_path: Mapped[str] = mapped_column(String(255), nullable=False)
    crop: Mapped[str] = mapped_column(String(60), nullable=False)
    possible_disease: Mapped[str] = mapped_column(String(120), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    top_k: Mapped[list] = mapped_column(JSON, default=list)
    recommended_actions: Mapped[list] = mapped_column(JSON, default=list)
    limitations: Mapped[list] = mapped_column(JSON, default=list)
    model_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("disease_models.id"), nullable=True)
    llm_explanation: Mapped[str | None] = mapped_column(String(2000), nullable=True)
