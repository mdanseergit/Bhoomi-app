from sqlalchemy import Float, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class StateNode(UUIDPKMixin, TimestampMixin, Base):
    """Logical representation of a participating state's agriculture
    intelligence node, present only once a real integration has been
    established with that state administration."""

    __tablename__ = "state_nodes"

    state: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    node_id: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="online")  # online | offline | degraded
    data_policy: Mapped[str] = mapped_column(String(500), default="Local data remains controlled by the state node.")
    available_models: Mapped[int] = mapped_column(default=0)
    supported_crops: Mapped[list] = mapped_column(JSON, default=list)
    is_demo: Mapped[bool] = mapped_column(default=False)


class StateDataset(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "state_datasets"

    state_node_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("state_nodes.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), default="agri.schema.v1")
    record_count: Mapped[int] = mapped_column(default=0)
    visibility: Mapped[str] = mapped_column(String(20), default="state_only")  # state_only | shared


class DataContract(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "data_contracts"

    from_state_node_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("state_nodes.id"), nullable=False)
    to_state_node_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("state_nodes.id"), nullable=False)
    scope: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")


class ModelRegistryEntry(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "model_registry"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="")
    publisher_state_node_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("state_nodes.id"), nullable=False)
    version: Mapped[str] = mapped_column(String(20), default="v1.0")
    model_type: Mapped[str] = mapped_column(String(60), nullable=False)  # disease_classification | risk | yield | soil
    crop: Mapped[str] = mapped_column(String(60), default="general")
    supported_regions: Mapped[list] = mapped_column(JSON, default=list)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    training_dataset_description: Mapped[str] = mapped_column(String(500), default="")
    license: Mapped[str] = mapped_column(String(80), default="BHOOMI Cooperative License")
    visibility: Mapped[str] = mapped_column(String(20), default="state_only")  # state_only | shared
    status: Mapped[str] = mapped_column(
        String(20), default="draft"
    )  # draft|pending_review|published|requested|approved|rejected|deprecated
    is_demo: Mapped[bool] = mapped_column(default=False)


class ModelVersion(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "model_versions"

    model_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("model_registry.id"), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    changelog: Mapped[str] = mapped_column(String(500), default="")
    artifact_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ModelRequest(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "model_requests"

    model_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("model_registry.id"), nullable=False)
    requesting_state_node_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("state_nodes.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="requested")  # requested|approved|rejected
    justification: Mapped[str] = mapped_column(String(500), default="")
    decided_by_user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
