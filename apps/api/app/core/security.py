"""
Security primitives: password hashing and JWT access/refresh token
issuance & validation.

Passwords are never stored manually as plaintext or with a home-grown
hash -- bcrypt via passlib is used exclusively.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def _create_token(subject: str, expires_delta: timedelta, extra: Optional[dict[str, Any]] = None, token_type: str = "access") -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_delta,
        "type": token_type,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: str, role: str, state: Optional[str] = None) -> str:
    return _create_token(
        user_id,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        extra={"role": role, "state": state},
        token_type="access",
    )


def create_refresh_token(user_id: str) -> str:
    return _create_token(
        user_id,
        timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES),
        token_type="refresh",
    )


class TokenError(Exception):
    pass


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise TokenError(str(exc)) from exc
