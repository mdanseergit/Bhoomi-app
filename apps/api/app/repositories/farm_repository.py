"""
Thin repository layer over the `Farm` model. Keeps query construction out
of the API layer and in one testable place.
"""
from uuid import UUID

from geoalchemy2.shape import from_shape
from shapely.geometry import Point, shape
from sqlalchemy.orm import Session

from app.models.farm import Farm


class FarmRepository:
    def list_for_user(self, db: Session, user_id: str) -> list[Farm]:
        return (
            db.query(Farm)
            .filter(Farm.user_id == user_id, Farm.deleted_at.is_(None))
            .order_by(Farm.created_at.desc())
            .all()
        )

    def get(self, db: Session, farm_id: str) -> Farm | None:
        try:
            uid = UUID(farm_id)
        except ValueError:
            return None
        return db.query(Farm).filter(Farm.id == uid, Farm.deleted_at.is_(None)).first()

    def create(self, db: Session, *, user_id: str, data: dict) -> Farm:
        boundary_geojson = data.pop("boundary_geojson", None)
        farm = Farm(user_id=user_id, **data)
        farm.location = from_shape(Point(data["longitude"], data["latitude"]), srid=4326)
        if boundary_geojson:
            farm.boundary_polygon = from_shape(shape(boundary_geojson), srid=4326)
        db.add(farm)
        db.commit()
        db.refresh(farm)
        return farm

    def update(self, db: Session, farm: Farm, data: dict) -> Farm:
        boundary_geojson = data.pop("boundary_geojson", None)
        for key, value in data.items():
            if value is not None:
                setattr(farm, key, value)
        if "latitude" in data or "longitude" in data:
            farm.location = from_shape(Point(farm.longitude, farm.latitude), srid=4326)
        if boundary_geojson:
            farm.boundary_polygon = from_shape(shape(boundary_geojson), srid=4326)
        db.commit()
        db.refresh(farm)
        return farm

    def soft_delete(self, db: Session, farm: Farm) -> None:
        from datetime import datetime, timezone

        farm.deleted_at = datetime.now(timezone.utc)
        db.commit()
