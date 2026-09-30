from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.v1.farms import _ensure_owner_or_privileged
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.core.rate_limit import rate_limit
from app.models.disease import DiseaseScan
from app.models.user import User
from app.repositories.farm_repository import FarmRepository
from app.services import audit_service
from app.services.disease_service import DiseaseService

router = APIRouter(prefix="/disease", tags=["disease"])
farm_repo = FarmRepository()
disease_service = DiseaseService()


@router.post("/analyze", dependencies=[Depends(rate_limit("disease"))])
async def analyze(
    request: Request,
    farm_id: str = Form(...),
    crop: str | None = Form(default=None),
    image: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    farm = farm_repo.get(db, farm_id)
    if not farm:
        raise NotFoundError("Farm not found.")
    _ensure_owner_or_privileged(farm, user)

    if not image.content_type:
        raise ValidationFailedError("Image content type could not be determined.")
    content = await image.read()

    result = disease_service.analyze(
        db, farm=farm, user_id=str(user.id), image_bytes=content, content_type=image.content_type, crop=crop
    )
    audit_service.record(
        db,
        user_id=str(user.id),
        action="DISEASE_SCAN",
        resource="disease_scan",
        resource_id=result["scan_id"],
        ip=request.client.host if request.client else None,
        metadata={"possible_disease": result["possible_disease"], "confidence": result["confidence"]},
    )
    return result


@router.get("/history/{farm_id}")
def scan_history(farm_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = farm_repo.get(db, farm_id)
    if not farm:
        raise NotFoundError("Farm not found.")
    _ensure_owner_or_privileged(farm, user)
    scans = db.query(DiseaseScan).filter(DiseaseScan.farm_id == farm.id).order_by(DiseaseScan.created_at.desc()).all()
    return [
        {
            "id": str(s.id),
            "crop": s.crop,
            "possible_disease": s.possible_disease,
            "confidence": s.confidence,
            "severity": s.severity,
            "created_at": s.created_at.isoformat(),
        }
        for s in scans
    ]


@router.get("/image/{folder}/{filename}")
def get_scan_image(folder: str, filename: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Serves uploaded crop images from private local storage. Access is
    restricted to authenticated users; in production this should issue a
    signed URL against S3-compatible object storage instead."""
    import os

    path = os.path.join(settings.STORAGE_LOCAL_PATH, folder, filename)
    if not os.path.isfile(path):
        raise NotFoundError("Image not found.")
    return FileResponse(path)
