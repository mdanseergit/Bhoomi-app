from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.farms import _ensure_owner_or_privileged
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.repositories.farm_repository import FarmRepository
from app.services import audit_service
from app.services.intelligence_service import IntelligenceService

router = APIRouter(prefix="/farms", tags=["intelligence"])
farm_repo = FarmRepository()
intelligence_service = IntelligenceService()


@router.get("/{farm_id}/intelligence")
def get_intelligence(farm_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = farm_repo.get(db, farm_id)
    if not farm:
        raise NotFoundError("Farm not found.")
    _ensure_owner_or_privileged(farm, user)
    return intelligence_service.compute_and_persist(db, farm, user_id=str(user.id), with_ai=True)


@router.post("/{farm_id}/analyze")
def analyze_farm(farm_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Force a recompute of the intelligence pipeline (e.g. after new soil data)."""
    farm = farm_repo.get(db, farm_id)
    if not farm:
        raise NotFoundError("Farm not found.")
    _ensure_owner_or_privileged(farm, user)
    result = intelligence_service.compute_and_persist(db, farm, user_id=str(user.id), with_ai=True)
    audit_service.record(db, user_id=str(user.id), action="ADVISORY_GENERATED", resource="farm", resource_id=str(farm.id))
    return result
