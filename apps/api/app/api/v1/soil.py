from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.v1.farms import _ensure_owner_or_privileged
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.repositories.farm_repository import FarmRepository
from app.schemas.soil import SoilProfileIn, SoilProfileOut
from app.services import audit_service
from app.services.soil_service import SoilService

router = APIRouter(prefix="/soil", tags=["soil"])
farm_repo = FarmRepository()
soil_service = SoilService()


def _out(profile) -> SoilProfileOut:
    return SoilProfileOut(
        id=str(profile.id),
        farm_id=str(profile.farm_id),
        ph=profile.ph,
        nitrogen=profile.nitrogen,
        phosphorus=profile.phosphorus,
        potassium=profile.potassium,
        organic_carbon=profile.organic_carbon,
        electrical_conductivity=profile.electrical_conductivity,
        sulfur=profile.sulfur,
        zinc=profile.zinc,
        iron=profile.iron,
        copper=profile.copper,
        manganese=profile.manganese,
        boron=profile.boron,
        moisture=profile.moisture,
        source=profile.source,
        sample_date=profile.sample_date,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.get("/{farm_id}", response_model=SoilProfileOut | None)
def get_soil(farm_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = farm_repo.get(db, farm_id)
    if not farm:
        raise NotFoundError("Farm not found.")
    _ensure_owner_or_privileged(farm, user)
    from app.models.soil import SoilProfile

    profile = db.query(SoilProfile).filter(SoilProfile.farm_id == farm.id).first()
    return _out(profile) if profile else None


@router.put("/{farm_id}", response_model=SoilProfileOut)
def upsert_soil(farm_id: str, payload: SoilProfileIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = farm_repo.get(db, farm_id)
    if not farm:
        raise NotFoundError("Farm not found.")
    _ensure_owner_or_privileged(farm, user)
    profile = soil_service.upsert_profile(db, farm, payload)
    audit_service.record(db, user_id=str(user.id), action="SOIL_UPDATED", resource="soil_profile", resource_id=str(profile.id), ip=request.client.host if request.client else None)
    return _out(profile)


@router.post("/{farm_id}/import", response_model=SoilProfileOut)
async def import_soil_csv(farm_id: str, request: Request, file: UploadFile = File(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = farm_repo.get(db, farm_id)
    if not farm:
        raise NotFoundError("Farm not found.")
    _ensure_owner_or_privileged(farm, user)
    content = await file.read()
    profile = soil_service.import_csv(db, farm, content)
    audit_service.record(db, user_id=str(user.id), action="SOIL_IMPORTED_CSV", resource="soil_profile", resource_id=str(profile.id), ip=request.client.host if request.client else None)
    return _out(profile)
