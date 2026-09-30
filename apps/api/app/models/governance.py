from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class Consent(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "consents"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(120), nullable=False)  # e.g. "advisory_generation", "cross_state_sharing"
    scope: Mapped[str] = mapped_column(String(255), nullable=False)
    granted: Mapped[bool] = mapped_column(default=True)
    retention_days: Mapped[int] = mapped_column(default=365)


class DataAccessPolicy(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "data_access_policies"

    resource_type: Mapped[str] = mapped_column(String(60), nullable=False)  # farm | soil | disease_scan | model
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    access_scope: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)


class AuditLog(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"

    user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    resource: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result: Mapped[str] = mapped_column(String(20), default="success")  # success | failure | denied
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
