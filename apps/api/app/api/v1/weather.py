from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.farms import _ensure_owner_or_privileged
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.repositories.farm_repository import FarmRepository
from app.services.weather_service import WeatherService

router = APIRouter(prefix="/weather", tags=["weather"])
farm_repo = FarmRepository()
weather_service = WeatherService()


@router.get("/{farm_id}")
def get_weather(farm_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = farm_repo.get(db, farm_id)
    if not farm:
        raise NotFoundError("Farm not found.")
    _ensure_owner_or_privileged(farm, user)
    snapshot = weather_service.get_current_snapshot(db, farm)
    return {
        "temperature_c": snapshot.temperature_c,
        "humidity_pct": snapshot.humidity_pct,
        "rainfall_mm": snapshot.rainfall_mm,
        "rain_probability_pct": snapshot.rain_probability_pct,
        "wind_speed_kmh": snapshot.wind_speed_kmh,
        "condition": snapshot.condition,
        "warning_level": snapshot.warning_level,
        "source": snapshot.source,
        "is_stale": snapshot.is_stale,
        "observed_at": snapshot.observed_at.isoformat() if snapshot.observed_at else None,
    }
