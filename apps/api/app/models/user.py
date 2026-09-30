import enum

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class Role(str, enum.Enum):
    FARMER = "farmer"
    AGRONOMIST = "agronomist"
    STATE_ADMIN = "state_admin"
    PLATFORM_ADMIN = "platform_admin"


class User(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "users"

    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"), default=Role.FARMER, nullable=False)
    state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    oauth_provider: Mapped[str | None] = mapped_column(String(40), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.email} role={self.role}>"
