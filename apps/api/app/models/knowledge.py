from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class KnowledgeDocument(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_documents"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    authority: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    crop: Mapped[str | None] = mapped_column(String(60), nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="en")
    publication_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    version: Mapped[str] = mapped_column(String(20), default="v1")


class KnowledgeChunk(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_chunks"

    document_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_documents.id"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(settings.EMBEDDING_DIM), nullable=True)
