from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.crop import CropVariety
from app.models.user import User

router = APIRouter(prefix="/crops", tags=["crops"])


@router.get("/varieties")
def list_varieties(crop: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(CropVariety)
    if crop:
        query = query.filter(CropVariety.crop == crop)
    varieties = query.all()
    return [
        {"id": str(v.id), "crop": v.crop, "variety_name": v.variety_name, "duration_days": v.duration_days, "recommended_states": v.recommended_states}
        for v in varieties
    ]
