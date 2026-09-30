from fastapi import APIRouter, Depends, Request
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.farm import Farm
from app.models.user import Role, User
from app.repositories.farm_repository import FarmRepository
from app.schemas.farm import FarmCreate, FarmOut, FarmUpdate
from app.services import audit_service

router = APIRouter(prefix="/farms", tags=["farms"])
repo = FarmRepository()


def _to_out(farm: Farm) -> FarmOut:
    boundary = None
    if farm.boundary_polygon is not None:
        try:
            boundary = mapping(to_shape(farm.boundary_polygon))
        except Exception:
            boundary = None
    return FarmOut(
        id=str(farm.id),
        user_id=str(farm.user_id),
        name=farm.name,
        state=farm.state,
        district=farm.district,
        taluk=farm.taluk,
        village=farm.village,
        latitude=farm.latitude,
        longitude=farm.longitude,
        boundary_geojson=boundary,
        area_hectares=farm.area_hectares,
        soil_type=farm.soil_type,
        irrigation_type=farm.irrigation_type,
        water_source=farm.water_source,
        current_crop=farm.current_crop,
        crop_variety=farm.crop_variety,
        crop_stage=farm.crop_stage,
        sowing_date=farm.sowing_date,
        previous_crop=farm.previous_crop,
        created_at=farm.created_at,
        updated_at=farm.updated_at,
    )


def _ensure_owner_or_privileged(farm: Farm, user: User) -> None:
    if user.role in (Role.PLATFORM_ADMIN, Role.AGRONOMIST, Role.STATE_ADMIN):
        return
    if str(farm.user_id) != str(user.id):
        raise ForbiddenError("You do not have access to this farm.")


@router.get("", response_model=list[FarmOut])
def list_farms(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role == Role.FARMER:
        farms = repo.list_for_user(db, str(user.id))
    else:
        farms = db.query(Farm).filter(Farm.deleted_at.is_(None)).order_by(Farm.created_at.desc()).limit(200).all()
    return [_to_out(f) for f in farms]


@router.post("", response_model=FarmOut, status_code=201)
def create_farm(payload: FarmCreate, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = repo.create(db, user_id=str(user.id), data=payload.model_dump())
    audit_service.record(db, user_id=str(user.id), action="FARM_CREATED", resource="farm", resource_id=str(farm.id), ip=request.client.host if request.client else None)
    return _to_out(farm)


@router.get("/{farm_id}", response_model=FarmOut)
def get_farm(farm_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = repo.get(db, farm_id)
    if not farm:
        raise NotFoundError("Farm not found.")
    _ensure_owner_or_privileged(farm, user)
    return _to_out(farm)


@router.patch("/{farm_id}", response_model=FarmOut)
def update_farm(farm_id: str, payload: FarmUpdate, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = repo.get(db, farm_id)
    if not farm:
        raise NotFoundError("Farm not found.")
    _ensure_owner_or_privileged(farm, user)
    farm = repo.update(db, farm, payload.model_dump(exclude_unset=True))
    audit_service.record(db, user_id=str(user.id), action="FARM_UPDATED", resource="farm", resource_id=str(farm.id), ip=request.client.host if request.client else None)
    return _to_out(farm)


@router.delete("/{farm_id}", status_code=204)
def delete_farm(farm_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = repo.get(db, farm_id)
    if not farm:
        raise NotFoundError("Farm not found.")
    _ensure_owner_or_privileged(farm, user)
    repo.soft_delete(db, farm)
    audit_service.record(db, user_id=str(user.id), action="FARM_DELETED", resource="farm", resource_id=str(farm.id), ip=request.client.host if request.client else None)
    return None
