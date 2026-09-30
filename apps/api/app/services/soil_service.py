"""
SoilService -- manual entry, CSV import, and normalized snapshot retrieval.

Units are normalized centrally here so downstream services never have to
guess whether a value is ppm, ppm-equivalent, or kg/ha.
"""
import csv
import io

from sqlalchemy.orm import Session

from app.core.exceptions import ValidationFailedError
from app.models.farm import Farm
from app.models.soil import SoilObservation, SoilProfile
from app.schemas.soil import SoilProfileIn
from app.services.agriculture.schema import SoilSnapshot

REQUIRED_CSV_COLUMNS = {"ph", "nitrogen", "phosphorus", "potassium", "organic_carbon"}


class SoilService:
    def upsert_profile(self, db: Session, farm: Farm, payload: SoilProfileIn) -> SoilProfile:
        profile = db.query(SoilProfile).filter(SoilProfile.farm_id == farm.id).first()
        if profile is None:
            profile = SoilProfile(farm_id=farm.id)
            db.add(profile)
        for field, value in payload.model_dump().items():
            setattr(profile, field, value)
        db.add(SoilObservation(farm_id=farm.id, **{
            k: v for k, v in payload.model_dump().items()
            if k in {"ph", "nitrogen", "phosphorus", "potassium", "organic_carbon", "moisture", "source", "sample_date"}
        }))
        db.commit()
        db.refresh(profile)
        return profile

    def import_csv(self, db: Session, farm: Farm, csv_bytes: bytes) -> SoilProfile:
        text = csv_bytes.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None or not REQUIRED_CSV_COLUMNS.issubset({f.strip().lower() for f in reader.fieldnames}):
            raise ValidationFailedError(
                f"CSV must include columns: {', '.join(sorted(REQUIRED_CSV_COLUMNS))}"
            )
        row = next(reader, None)
        if row is None:
            raise ValidationFailedError("CSV file contains no data rows.")
        normalized = {k.strip().lower(): v for k, v in row.items()}

        def _f(key: str) -> float | None:
            val = normalized.get(key)
            try:
                return float(val) if val not in (None, "") else None
            except ValueError:
                return None

        payload = SoilProfileIn(
            ph=_f("ph"),
            nitrogen=_f("nitrogen"),
            phosphorus=_f("phosphorus"),
            potassium=_f("potassium"),
            organic_carbon=_f("organic_carbon"),
            electrical_conductivity=_f("electrical_conductivity"),
            sulfur=_f("sulfur"),
            zinc=_f("zinc"),
            moisture=_f("moisture"),
            source="csv_import",
        )
        return self.upsert_profile(db, farm, payload)

    def get_snapshot(self, db: Session, farm: Farm) -> SoilSnapshot:
        profile = db.query(SoilProfile).filter(SoilProfile.farm_id == farm.id).first()
        if profile is None:
            return SoilSnapshot(None, None, None, None, None, None, source="unavailable", sample_date=None)
        return SoilSnapshot(
            ph=profile.ph,
            nitrogen=profile.nitrogen,
            phosphorus=profile.phosphorus,
            potassium=profile.potassium,
            organic_carbon=profile.organic_carbon,
            moisture=profile.moisture,
            source=profile.source,
            sample_date=profile.sample_date,
        )
