"""
Common FastAPI dependencies: DB session, current user resolution, and
role-based access control guards.
"""
from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import TokenError, decode_token
from app.models.user import Role, User


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Missing or invalid authorization header.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except TokenError as exc:
        raise UnauthorizedError("Session expired or invalid. Please log in again.") from exc
    if payload.get("type") != "access":
        raise UnauthorizedError("Invalid token type.")
    user_id = payload.get("sub")
    user = db.get(User, UUID(user_id)) if user_id else None
    if user is None or not user.is_active:
        raise UnauthorizedError("Account not found or disabled.")
    return user


def require_roles(*roles: Role) -> Callable[[User], User]:
    target_roles = roles[0] if (len(roles) == 1 and isinstance(roles[0], (list, tuple, set))) else roles

    def _guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in target_roles:
            raise ForbiddenError("Your role does not permit this action.")
        return user

    return _guard


def get_optional_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    if not authorization:
        return None
    try:
        return get_current_user(authorization, db)
    except UnauthorizedError:
        return None
