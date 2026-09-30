import enum

from sqlalchemy import Enum, Float, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class AdvisoryType(str, enum.Enum):
    WEATHER = "weather"
    IRRIGATION = "irrigation"
    SOIL = "soil"
    CROP = "crop"
    DISEASE = "disease"
    CLIMATE = "climate"
    REGENERATIVE = "regenerative"


class Severity(str, enum.Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"


class Advisory(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "advisories"

    farm_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("farms.id"), nullable=False, index=True)
    type: Mapped[AdvisoryType] = mapped_column(Enum(AdvisoryType, name="advisory_type"), nullable=False)
    severity: Mapped[Severity] = mapped_column(Enum(Severity, name="advisory_severity"), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    actions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_references: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.6)
    generated_by: Mapped[str] = mapped_column(String(40), default="rule_engine")  # rule_engine | ai | agronomist
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="advisory_review_status"), default=ReviewStatus.AUTO_APPROVED
    )
