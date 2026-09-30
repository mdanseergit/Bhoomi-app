from datetime import date, datetime

from pydantic import BaseModel, Field


class FarmCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    state: str
    district: str
    taluk: str | None = None
    village: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    boundary_geojson: dict | None = None
    area_hectares: float = Field(gt=0)
    soil_type: str | None = None
    irrigation_type: str | None = None
    water_source: str | None = None
    current_crop: str | None = None
    crop_variety: str | None = None
    crop_stage: str | None = None
    sowing_date: date | None = None
    previous_crop: str | None = None


class FarmUpdate(BaseModel):
    name: str | None = None
    taluk: str | None = None
    village: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    boundary_geojson: dict | None = None
    area_hectares: float | None = None
    soil_type: str | None = None
    irrigation_type: str | None = None
    water_source: str | None = None
    current_crop: str | None = None
    crop_variety: str | None = None
    crop_stage: str | None = None
    sowing_date: date | None = None
    previous_crop: str | None = None


class FarmOut(BaseModel):
    id: str
    user_id: str
    name: str
    state: str
    district: str
    taluk: str | None
    village: str | None
    latitude: float
    longitude: float
    boundary_geojson: dict | None = None
    area_hectares: float
    soil_type: str | None
    irrigation_type: str | None
    water_source: str | None
    current_crop: str | None
    crop_variety: str | None
    crop_stage: str | None
    sowing_date: date | None
    previous_crop: str | None
    created_at: datetime
    updated_at: datetime
