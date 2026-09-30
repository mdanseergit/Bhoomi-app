from datetime import date, datetime

from pydantic import BaseModel


class SoilProfileIn(BaseModel):
    ph: float | None = None
    nitrogen: float | None = None
    phosphorus: float | None = None
    potassium: float | None = None
    organic_carbon: float | None = None
    electrical_conductivity: float | None = None
    sulfur: float | None = None
    zinc: float | None = None
    iron: float | None = None
    copper: float | None = None
    manganese: float | None = None
    boron: float | None = None
    moisture: float | None = None
    source: str = "manual"
    sample_date: date | None = None


class SoilProfileOut(SoilProfileIn):
    id: str
    farm_id: str
    created_at: datetime
    updated_at: datetime
