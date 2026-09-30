from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.farms import _ensure_owner_or_privileged
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.models.satellite import SatelliteObservation
from app.models.user import User
from app.repositories.farm_repository import FarmRepository
from app.services.satellite_service import SatelliteService

router = APIRouter(prefix="/satellite", tags=["satellite"])
farm_repo = FarmRepository()
satellite_service = SatelliteService()


@router.get("/{farm_id}")
def get_satellite(farm_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = farm_repo.get(db, farm_id)
    if not farm:
        raise NotFoundError("Farm not found.")
    _ensure_owner_or_privileged(farm, user)
    snapshot = satellite_service.get_latest_snapshot(db, farm)
    history = (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.farm_id == farm.id)
        .order_by(SatelliteObservation.observation_date.asc())
        .all()
    )
    # No observation means no `latest` payload at all, so the UI can render a
    # truthful empty state instead of a card full of nulls.
    has_observation = snapshot.ndvi is not None or snapshot.evi is not None
    return {
        "latest": (
            {
                "ndvi": snapshot.ndvi,
                "evi": snapshot.evi,
                "trend_7d_pct": snapshot.trend_7d_pct,
                "vegetation_health": snapshot.vegetation_health,
                "observation_date": snapshot.observation_date.isoformat() if snapshot.observation_date else None,
                "source": snapshot.source,
                "is_dev_dataset": snapshot.is_dev_dataset,
            }
            if has_observation
            else None
        ),
        "history": [
            {"date": h.observation_date.isoformat(), "ndvi": h.ndvi, "evi": h.evi, "vegetation_health": h.vegetation_health}
            for h in history
        ],
    }
