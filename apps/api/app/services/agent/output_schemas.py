"""
Typed output contracts for the agent tools.

Every tool declares the shape of the ``data`` it returns. This is what makes a
handler's contract reviewable instead of implicit: the registry advertises the
schema to callers, and the runtime can validate a handler's payload against it
before it reaches the model or the database.

Fields are permissive on purpose. An upstream provider can legitimately return
humidity without temperature, or NDVI without EVI, and a real partial
observation must survive validation rather than be dropped. ``available`` is
the flag that distinguishes "the provider answered" from "there is nothing to
report", and ``missing_data`` names exactly what is absent.
"""
from pydantic import BaseModel, ConfigDict, Field


class ToolOutput(BaseModel):
    """Base for every tool output.

    Subclasses add their domain fields. Keeping ``available`` on the base means
    a caller can branch on one attribute regardless of which tool produced the
    payload.

    ``protected_namespaces`` is cleared because several domain fields are named
    after their domain ("model_type", "model_id"), which would otherwise collide
    with pydantic's protected ``model_`` prefix and warn on every import.
    """

    model_config = ConfigDict(protected_namespaces=())

    available: bool = True


# --- Farm ------------------------------------------------------------------


class FarmProfileOutput(ToolOutput):
    id: str
    name: str
    location: str | None = None
    district: str | None = None
    state: str | None = None
    area_hectares: float | None = None
    soil_type: str | None = None
    irrigation_type: str | None = None
    water_source: str | None = None
    current_crop: str | None = None
    crop_variety: str | None = None
    crop_stage: str | None = None
    sowing_date: str | None = None
    previous_crop: str | None = None
    updated_at: str | None = None


class FarmListItem(BaseModel):
    id: str
    name: str
    state: str | None = None
    district: str | None = None
    area_hectares: float | None = None
    current_crop: str | None = None
    crop_stage: str | None = None


class FarmListOutput(ToolOutput):
    count: int
    items: list[FarmListItem] = Field(default_factory=list)


class FarmHistoryOutput(ToolOutput):
    """Recorded event timeline for a farm, newest first."""

    count: int = 0
    items: list[dict] = Field(default_factory=list)
    current_crop: str | None = None
    previous_crop: str | None = None
    sowing_date: str | None = None
    note: str | None = None


# --- Weather ---------------------------------------------------------------


class WeatherOutput(ToolOutput):
    temperature_c: float | None = None
    humidity_pct: float | None = None
    rainfall_mm: float | None = None
    rain_probability_pct: float | None = None
    wind_speed_kmh: float | None = None
    condition: str | None = None
    warning_level: str | None = None
    observed_at: str | None = None
    is_stale: bool = False


class ForecastDay(BaseModel):
    forecast_time: str | None = None
    temperature_c: float | None = None
    humidity_pct: float | None = None
    rain_probability_pct: float | None = None
    rainfall_expected_mm: float | None = None
    wind_speed_kmh: float | None = None
    condition: str | None = None
    warning_level: str | None = None


class WeatherForecastOutput(ToolOutput):
    count: int = 0
    items: list[ForecastDay] = Field(default_factory=list)


class WeatherAlert(BaseModel):
    severity: str
    headline: str
    detail: str | None = None


class WeatherAlertsOutput(ToolOutput):
    count: int = 0
    items: list[WeatherAlert] = Field(default_factory=list)


# --- Soil ------------------------------------------------------------------


class SoilOutput(ToolOutput):
    ph: float | None = None
    nitrogen: float | None = None
    phosphorus: float | None = None
    potassium: float | None = None
    organic_carbon: float | None = None
    moisture: float | None = None
    sample_date: str | None = None
    soil_type: str | None = None


class SoilHealthOutput(ToolOutput):
    score: float | None = None
    label: str | None = None
    ph: float | None = None
    organic_carbon: float | None = None
    nitrogen: float | None = None
    phosphorus: float | None = None
    potassium: float | None = None
    recommendations: list[str] = Field(default_factory=list)


# --- Satellite / vegetation ------------------------------------------------


class SatelliteOutput(ToolOutput):
    ndvi: float | None = None
    evi: float | None = None
    vegetation_health: str | None = None
    cloud_cover_pct: float | None = None
    observation_date: str | None = None
    is_dev_dataset: bool = False
    freshness_status: str | None = None


class NdviPoint(BaseModel):
    observation_date: str | None = None
    ndvi: float | None = None


class VegetationTrendOutput(ToolOutput):
    points: list[NdviPoint] = Field(default_factory=list)
    trend_7d_pct: float | None = None
    direction: str | None = None


# --- Water / climate -------------------------------------------------------


class WaterOutput(ToolOutput):
    soil_moisture_pct: float | None = None
    rainfall_mm: float | None = None
    irrigation_applied_mm: float | None = None
    drought_index: float | None = None
    moisture_source_type: str | None = None
    observed_at: str | None = None


class IrrigationEvent(BaseModel):
    observed_at: str | None = None
    applied_mm: float | None = None
    moisture_source_type: str | None = None
    quality_status: str | None = None
    source: str | None = None


class IrrigationHistoryOutput(ToolOutput):
    days: int = 30
    event_count: int = 0
    total_applied_mm: float = 0.0
    mean_soil_moisture_pct: float | None = None
    items: list[IrrigationEvent] = Field(default_factory=list)


class WaterRiskOutput(ToolOutput):
    stress_level: str | None = None
    drought_index: float | None = None
    soil_moisture_pct: float | None = None
    irrigation_type: str | None = None
    water_source: str | None = None
    recommendation: str | None = None


class ClimateRiskOutput(ToolOutput):
    risk_level: str | None = None
    heat_stress_days: int | None = None
    rainfall_anomaly_pct: float | None = None
    frost_risk: bool | None = None
    recommendation: str | None = None


# --- Crop / health ---------------------------------------------------------


class CropHealthOutput(ToolOutput):
    health_score: float | None = None
    label: str | None = None
    current_crop: str | None = None
    stage: str | None = None
    days_after_sowing: int | None = None
    factors: list[str] = Field(default_factory=list)


class CropStageOutput(ToolOutput):
    current_crop: str | None = None
    stage: str | None = None
    sowing_date: str | None = None
    days_after_sowing: int | None = None
    expected_stage: str | None = None
    # Distance in growth stages between the recorded stage and the coarse
    # day-band expectation. None when either stage is unknown.
    stage_gap: int | None = None
    on_track: bool | None = None


class CropRiskOutput(ToolOutput):
    overall_risk: str | None = None
    dimensions: dict = Field(default_factory=dict)
    top_factor: str | None = None


class FarmHealthOutput(ToolOutput):
    """Composite farm health, mirroring ``FarmHealthResult.to_json()``.

    ``score`` is None when no component had a real observation; ``has_data`` is
    what tells a caller whether that None means "poor" or "not measured".
    ``factors`` are dicts, not strings, because each one carries a name, an
    impact weight and a human-readable detail.
    """

    score: float | None = None
    label: str | None = None
    has_data: bool = False
    data_coverage: float | None = None
    climate_risk: str | None = None
    water_stress: str | None = None
    disease_risk: str | None = None
    vegetation_stress: str | None = None
    soil_health: str | None = None
    factors: list[dict] = Field(default_factory=list)
    breakdown: dict = Field(default_factory=dict)
    missing_inputs: list[str] = Field(default_factory=list)
    risk_dimensions: dict = Field(default_factory=dict)
    farm_id: str | None = None
    computed_at: str | None = None


# --- Advisory / actions ----------------------------------------------------


class AdvisoryItem(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: str | None = None
    type: str
    severity: str
    title: str
    summary: str
    # The rule engine emits structured steps ({"title", "priority", "reason"});
    # an agronomist may write a plain sentence. Both are real, so both validate.
    actions: list[dict | str] = Field(default_factory=list)
    confidence: float | None = None
    evidence: list[dict] = Field(default_factory=list)
    review_status: str | None = None
    created_at: str | None = None


class AdvisoryListOutput(ToolOutput):
    count: int = 0
    items: list[AdvisoryItem] = Field(default_factory=list)


class CreateAdvisoryOutput(ToolOutput):
    advisory_id: str
    farm_id: str
    type: str
    severity: str
    title: str
    created: bool = True
    verification: str | None = None


class NotificationOutput(ToolOutput):
    notification_id: str
    title: str
    created: bool = True
    verification: str | None = None


class ReportOutput(ToolOutput):
    report_id: str
    report_type: str
    farm_id: str | None = None
    created: bool = True
    verification: str | None = None


class ExpertReviewOutput(ToolOutput):
    request_id: str
    status: str
    requires_approval: bool = True
    verification: str | None = None


class ActionResultOutput(ToolOutput):
    action_id: str | None = None
    status: str
    detail: str | None = None


# --- Disease ---------------------------------------------------------------


class DiseaseScanItem(BaseModel):
    crop: str | None = None
    possible_disease: str | None = None
    hypothesis_confidence: float | None = None
    severity: str | None = None
    limitations: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    observed_at: str | None = None


class DiseaseHistoryOutput(ToolOutput):
    count: int = 0
    items: list[DiseaseScanItem] = Field(default_factory=list)
    disclaimer: str | None = None


class CropImageAnalysisOutput(ToolOutput):
    scan_id: str | None = None
    crop: str | None = None
    hypothesis: str | None = None
    hypothesis_confidence: float | None = None
    severity: str | None = None
    recommended_actions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    disclaimer: str | None = None


# --- Knowledge / cooperation -----------------------------------------------


class KnowledgeResult(BaseModel):
    document_id: str
    title: str | None = None
    authority: str | None = None
    excerpt: str | None = None


class KnowledgeSearchOutput(ToolOutput):
    query: str
    count: int = 0
    results: list[KnowledgeResult] = Field(default_factory=list)


class SharedModelItem(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: str
    name: str
    model_type: str | None = None
    crop: str | None = None
    version: str | None = None
    accuracy: float | None = None
    description: str | None = None
    # Seeded/demo entries are carried through rather than hidden, so the
    # planner can tell a real published model from a placeholder.
    is_demo: bool = False


class SharedModelsOutput(ToolOutput):
    count: int = 0
    items: list[SharedModelItem] = Field(default_factory=list)


class ModelDetailOutput(ToolOutput):
    model_config = ConfigDict(protected_namespaces=())

    id: str
    # ``id`` is the identity of a detail lookup, so it is the only field a
    # not-found response has to carry: making ``name`` required would force a
    # miss to be reported as a failure instead of an honest empty state.
    name: str = ""
    model_type: str | None = None
    crop: str | None = None
    version: str | None = None
    accuracy: float | None = None
    description: str | None = None
    supported_regions: list[str] = Field(default_factory=list)
    license: str | None = None
    publisher_state: str | None = None
    is_demo: bool = False


# --- Analysis --------------------------------------------------------------


class FarmAnalysisOutput(ToolOutput):
    farm_id: str
    summary: str | None = None
    health: dict = Field(default_factory=dict)
    risks: list[str] = Field(default_factory=list)
    advisories: list[AdvisoryItem] = Field(default_factory=list)
    data_coverage: float | None = None


__all__ = [name for name in dir() if name.endswith("Output")]