from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.exceptions import ConflictError, UnauthorizedError, ValidationFailedError
from app.core.rate_limit import rate_limit
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password, TokenError
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, UserOut
from app.services import audit_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, dependencies=[Depends(rate_limit("auth"))])
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    # Self-registration may never mint an administrative role. Privileged
    # roles are provisioned out-of-band by a platform administrator.
    allowed = settings.registration_allowed_role_list
    if payload.role.value not in allowed:
        raise ValidationFailedError(
            f"Role '{payload.role.value}' cannot be self-registered. Allowed roles: {', '.join(allowed)}."
        )

    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise ConflictError("An account with this email already exists.")
    user = User(
        full_name=payload.full_name,
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        state=payload.state,
        phone=payload.phone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = str(user.id)
    user_role = user.role.value
    user_state = user.state
    audit_service.record(db, user_id=user_id, action="USER_REGISTERED", resource="user", resource_id=user_id, ip=request.client.host if request.client else None)
    return TokenResponse(
        access_token=create_access_token(user_id, user_role, user_state),
        refresh_token=create_refresh_token(user_id),
    )


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(rate_limit("auth"))])
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise UnauthorizedError("Invalid email or password.")
    if not user.is_active:
        raise UnauthorizedError("This account has been disabled.")
    user_id = str(user.id)
    user_role = user.role.value
    user_state = user.state
    audit_service.record(db, user_id=user_id, action="USER_LOGIN", resource="user", resource_id=user_id, ip=request.client.host if request.client else None)
    return TokenResponse(
        access_token=create_access_token(user_id, user_role, user_state),
        refresh_token=create_refresh_token(user_id),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        data = decode_token(payload.refresh_token)
    except TokenError as exc:
        raise UnauthorizedError("Refresh token expired or invalid. Please log in again.") from exc
    if data.get("type") != "refresh":
        raise UnauthorizedError("Invalid token type.")
    from uuid import UUID

    user = db.get(User, UUID(data["sub"]))
    if not user or not user.is_active:
        raise UnauthorizedError("Account not found or disabled.")
    return TokenResponse(
        access_token=create_access_token(str(user.id), user.role.value, user.state),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut(id=str(user.id), full_name=user.full_name, email=user.email, role=user.role, state=user.state, preferred_language=user.preferred_language)


@router.post("/logout")
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    audit_service.record(db, user_id=str(user.id), action="USER_LOGOUT", resource="user", resource_id=str(user.id))
    return {"status": "ok"}
