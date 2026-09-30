from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.auth import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserOut)
def update_profile(payload: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    allowed = {"full_name", "phone", "preferred_language", "state"}
    for key, value in payload.items():
        if key in allowed and value is not None:
            setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return UserOut(id=str(user.id), full_name=user.full_name, email=user.email, role=user.role, state=user.state, preferred_language=user.preferred_language)
