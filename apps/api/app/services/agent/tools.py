"""
The read-only BHOOMI tools the agent is allowed to call for observations.

Every handler here delegates to the same services the product screens already
use, so the agent cannot see anything a farmer cannot see on their own
dashboard. Where a capability has no real provider configured, the handler
returns ``ToolResult.unavailable`` with the missing input named -- it never
invents a measurement.

Writes live in ``action_tools.py``, behind the approval gate in
``executor.py``. Keeping observation and action in separate modules is what
makes "this run only read things" a structural property rather than a promise.

Each tool declares an ``output_model`` from ``output_schemas``. The executor
validates every handler's payload against it, so a handler cannot quietly drift
away from the contract the model and the UI were told about.
"""
from datetime import date, datetime, timedelta, timezone

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models.advisory import Advisory
from app.models.agent import ToolRiskLevel
from app.models.cooperation import ModelRegistryEntry, StateNode
from app.models.disease import DiseaseScan
from app.models.farm import Farm
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.risk import FarmRiskScore
from app.models.satellite import SatelliteObservation
from app.models.data_network import WaterObservation
from app.models.weather import WeatherForecast, WeatherObservation
from app.services.advisory_engine import generate_deterministic_advisories
from app.services.agriculture.climate import ClimateRiskService
from app.services.agriculture.crop_suitability import CropSuitabilityService
from app.services.agriculture.farm_health import FarmHealthService
from app.services.agriculture.schema import FarmContext
from app.services.agriculture.soil_health import SoilHealthService
from app.services.agriculture.vegetation import VegetationHealthService
from app.services.agriculture.water import WaterStressService
from app.services.agent.output_schemas import (
    AdvisoryListOutput,
    ClimateRiskOutput,
    CropHealthOutput,
    CropRiskOutput,
    CropStageOutput,
    DiseaseHistoryOutput,
    FarmAnalysisOutput,
    FarmHealthOutput,
    FarmHistoryOutput,
    FarmListOutput,
    FarmProfileOutput,
    IrrigationHistoryOutput,
    KnowledgeSearchOutput,
    ModelDetailOutput,
    SatelliteOutput,
    SharedModelsOutput,
    SoilHealthOutput,
    SoilOutput,
    VegetationTrendOutput,
    WaterOutput,
    WaterRiskOutput,
    WeatherAlertsOutput,
    WeatherForecastOutput,
    WeatherOutput,
)
from app.services.agent.registry import (
    SCOPE_ADVISORY_READ,
    SCOPE_COOPERATION_READ,
    SCOPE_DISEASE_READ,
    SCOPE_FARM_READ,
    SCOPE_INTELLIGENCE_READ,
    SCOPE_KNOWLEDGE_READ,
    SCOPE_SATELLITE_READ,
    SCOPE_SOIL_READ,
    SCOPE_WATER_READ,
    SCOPE_WEATHER_READ,
    ToolContext,
    ToolHandler,
    ToolRegistry,
    ToolResult,
    ToolSpec,
    registry,
)
from app.services.embedding_service import EmbeddingService
from app.services.intelligence_service import IntelligenceService
from app.services.satellite_service import SatelliteService
from app.services.soil_service import SoilService
from app.services.water_service import WaterService
from app.services.weather_service import WeatherService

TOOL_VERSION = "1.0.0"

_CROP_STAGE_ORDER = (
    "sowing",
    "germination",
    "vegetative",
    "flowering",
    "fruiting",
    "maturity",
    "harvest",
    "post_harvest",
)

# Canonical verb-first names for the tools above. They resolve to the same
# registered spec, so a caller can use `get_farm` or the original
# `farm_snapshot` and get one handler, one permission check and one audit row.
_TOOL_ALIASES: dict[str, tuple[str, ...]] = {
    "farm_snapshot": ("get_farm",),
    "get_crop_cycle": ("get_crop_stage",),
    "weather_now": ("get_weather", "get_current_weather"),
    "get_weather_forecast": ("get_forecast",),
    "soil_profile": ("get_soil", "get_latest_soil_profile"),
    "vegetation_index": ("get_satellite", "get_latest_satellite_observation", "get_ndvi"),
    "water_status": ("get_water_status",),
    "farm_health": ("calculate_farm_health",),
    "disease_history": ("get_recent_disease_scans",),
    "search_agricultural_knowledge": ("search_knowledge",),
}

# The tuple below annotates its handler column, so it needs the real protocol
# rather than a placeholder: `object` would silence the import-time reference
# but tell a reader nothing.
ToolHandler_ = ToolHandler

# Coarse day bands per growth stage for a typical Indian cereal/vegetable
# season. Used for one purpose only: to say whether the stage the farmer
# recorded is roughly consistent with the days elapsed since sowing. It is an
# internal approximation, not agronomic guidance, and it is never used to
# recommend a crop operation.
_STAGE_DAY_BANDS: dict[str, tuple[int, int]] = {
    "sowing": (0, 10),
    "germination": (6, 20),
    "vegetative": (15, 45),
    "flowering": (40, 75),
    "fruiting": (65, 110),
    "maturity": (100, 145),
    "harvest": (140, 185),
    "post_harvest": (180, 260),
}


class _NoInput(BaseModel):
    """Tools that operate on the farm already resolved for the task."""


class ListMyFarmsInput(BaseModel):
    limit: int = Field(default=20, ge=1, le=50)


class AdvisoryInput(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)
    severity: str | None = Field(default=None, pattern="^(low|moderate|high|critical)$")


class DiseaseInput(BaseModel):
    limit: int = Field(default=5, ge=1, le=20)


class HistoryInput(BaseModel):
    days: int = Field(default=30, ge=7, le=365)
    limit: int = Field(default=20, ge=1, le=100)


class KnowledgeQueryInput(BaseModel):
    query: str = Field(min_length=2, max_length=300)
    limit: int = Field(default=5, ge=1, le=20)


class ModelLookupInput(BaseModel):
    model_id: str = Field(min_length=1, max_length=64)


def _require_farm(ctx: ToolContext) -> Farm:
    if ctx.farm is None:
        raise ValueError("This request is about a specific farm, but no farm was selected.")
    return ctx.farm


def _farm_context(farm: Farm) -> FarmContext:
    return FarmContext(
        farm_id=str(farm.id),
        crop=farm.current_crop,
        crop_stage=farm.crop_stage,
        previous_crop=farm.previous_crop,
        irrigation_type=farm.irrigation_type,
        water_source=farm.water_source,
        area_hectares=farm.area_hectares,
        state=farm.state,
        district=farm.district,
    )


def _service_result_payload(result) -> dict:
    return result.to_json()


# --- Farm ------------------------------------------------------------------


def get_farm_snapshot(ctx: ToolContext, _args: BaseModel) -> ToolResult:
    farm = _require_farm(ctx)
    data = {
        "id": str(farm.id),
        "name": farm.name,
        "location": f"{farm.village or farm.taluk or farm.district}, {farm.state}",
        "district": farm.district,
        "state": farm.state,
        "area_hectares": farm.area_hectares,
        "soil_type": farm.soil_type,
        "irrigation_type": farm.irrigation_type,
        "water_source": farm.water_source,
        "current_crop": farm.current_crop,
        "crop_variety": farm.crop_variety,
        "crop_stage": farm.crop_stage,
        "sowing_date": farm.sowing_date.isoformat() if farm.sowing_date else None,
        "previous_crop": farm.previous_crop,
        "updated_at": farm.updated_at.isoformat() if farm.updated_at else None,
    }
    missing = [k for k in ("current_crop", "crop_stage", "soil_type") if not data.get(k)]
    return ToolResult(
        data=data,
        summary=(
            f"{farm.name} ({farm.area_hectares} ha, {farm.current_crop or 'no crop recorded'} "
            f"at {farm.crop_stage or 'unknown stage'}) in {farm.district}, {farm.state}."
        ),
        sources=[{"domain": "Farm profile", "provider": "farmer_recorded", "status": "RECENT"}],
        missing_data=missing,
        confidence=0.95,
    )


def list_my_farms(ctx: ToolContext, args: BaseModel) -> ToolResult:
    """The user's own farms, for questions like "which farm needs attention?".

    Non-farmers see only farms they own. Platform-wide visibility for admins is
    available through the farms screen, not through the agent, so the agent
    cannot become a bulk data-exfiltration path.
    """
    payload = ListMyFarmsInput.model_validate(args.model_dump())
    rows = (
        ctx.db.query(Farm)
        .filter(Farm.user_id == ctx.user_id, Farm.deleted_at.is_(None))
        .order_by(Farm.created_at.desc())
        .limit(payload.limit)
        .all()
    )
    return ToolResult(
        data={
            "count": len(rows),
            "items": [
                {
                    "id": str(f.id),
                    "name": f.name,
                    "state": f.state,
                    "district": f.district,
                    "area_hectares": f.area_hectares,
                    "current_crop": f.current_crop,
                    "crop_stage": f.crop_stage,
                }
                for f in rows
            ],
        },
        summary=f"{len(rows)} farm(s) on your account." if rows else "You have not registered any farms yet.",
        sources=[{"domain": "Farm profile", "provider": "farmer_recorded", "status": "RECENT"}],
        confidence=0.95,
    )


def get_crop_cycle(ctx: ToolContext, _args: BaseModel) -> ToolResult:
    """Where this season is, and how far along it is.

    Derived from the sowing date and recorded stage, so a farmer asking "when
    should I harvest?" gets an answer grounded in their own record rather than
    a generic calendar.
    """
    farm = _require_farm(ctx)
    days_after = None
    expected = None
    on_track = None
    stage_gap = None
    if farm.sowing_date:
        days_after = (date.today() - farm.sowing_date).days
        expected = _expected_stage(days_after)
        stage_gap = _stage_distance(farm.crop_stage, expected)
        # One band of slack: a farmer who recorded "vegetative" a week either
        # side of the expected window has not done anything wrong.
        on_track = stage_gap is not None and stage_gap <= 1

    data = {
        "current_crop": farm.current_crop,
        "stage": farm.crop_stage,
        "sowing_date": farm.sowing_date.isoformat() if farm.sowing_date else None,
        "days_after_sowing": days_after,
        "expected_stage": expected,
        "stage_gap": stage_gap,
        "on_track": on_track,
    }
    missing = [k for k, v in (("sowing_date", farm.sowing_date), ("crop_stage", farm.crop_stage)) if not v]
    return ToolResult(
        data=data,
        summary=(
            f"{farm.current_crop or 'No crop'} at the {farm.crop_stage or 'unrecorded'} stage, "
            f"{days_after} days after sowing."
            if days_after is not None
            else f"{farm.current_crop or 'No crop recorded'}; sowing date is not on record."
        ),
        sources=[{"domain": "Farm profile", "provider": "farmer_recorded", "status": "RECENT"}],
        missing_data=missing,
        confidence=0.85 if days_after is not None else 0.4,
    )


def get_farm_history(ctx: ToolContext, args: BaseModel) -> ToolResult:
    """The recorded timeline for this farm.

    Assembled from what is genuinely on record -- advisories, risk scores,
    satellite observations and the current/previous crop. BHOOMI does not keep
    a multi-season crop-cycle table, so where one would be expected the tool
    says so rather than implying depth it does not have.
    """
    farm = _require_farm(ctx)
    payload = HistoryInput.model_validate(args.model_dump())
    since = datetime_now() - timedelta(days=payload.days)

    advisories = (
        ctx.db.query(Advisory)
        .filter(Advisory.farm_id == farm.id, Advisory.created_at >= since)
        .order_by(Advisory.created_at.desc())
        .limit(payload.limit)
        .all()
    )
    risks = (
        ctx.db.query(FarmRiskScore)
        .filter(FarmRiskScore.farm_id == farm.id, FarmRiskScore.created_at >= since)
        .order_by(FarmRiskScore.created_at.desc())
        .limit(payload.limit)
        .all()
    )
    vegetation = (
        ctx.db.query(SatelliteObservation)
        .filter(SatelliteObservation.farm_id == farm.id)
        .order_by(SatelliteObservation.observation_date.desc())
        .limit(payload.limit)
        .all()
    )

    timeline: list[dict] = []
    timeline.extend(
        {
            "kind": "advisory",
            "at": a.created_at.isoformat() if a.created_at else None,
            "detail": f"{a.title} ({a.severity.value})",
        }
        for a in advisories
    )
    timeline.extend(
        {
            "kind": "risk_score",
            "at": r.created_at.isoformat() if r.created_at else None,
            "detail": f"health {round(r.farm_health_score, 1)}, water stress {r.water_stress}",
        }
        for r in risks
    )
    timeline.extend(
        {
            "kind": "vegetation",
            "at": o.observation_date.isoformat() if o.observation_date else None,
            "detail": f"NDVI {o.ndvi}" if o.ndvi is not None else "observation without NDVI",
        }
        for o in vegetation
    )
    timeline.sort(key=lambda item: item["at"] or "", reverse=True)

    data = {
        "count": len(timeline),
        "items": timeline[: payload.limit],
        "current_crop": farm.current_crop,
        "previous_crop": farm.previous_crop,
        "sowing_date": farm.sowing_date.isoformat() if farm.sowing_date else None,
        "note": (
            "BHOOMI stores the current and previous crop only; a full multi-season "
            "crop-cycle history is not recorded."
        ),
    }
    missing = ["crop_cycle_history"] if not advisories and not risks else []
    return ToolResult(
        data=data,
        summary=(
            f"{len(timeline)} recorded event(s) in the last {payload.days} days for {farm.name}."
            if timeline
            else f"No recorded events in the last {payload.days} days for {farm.name}."
        ),
        sources=[
            {"domain": "Advisories", "provider": "rule_engine", "status": "RECENT"},
            {"domain": "Risk scores", "provider": "bhoomi-risk-engine", "status": "RECENT"},
            {"domain": "Satellite", "provider": "bhoomi-sync-engine", "status": "RECENT"},
        ],
        missing_data=missing,
        confidence=0.7 if timeline else 0.3,
    )


# --- Weather ---------------------------------------------------------------


def get_weather(ctx: ToolContext, _args: BaseModel) -> ToolResult:
    farm = _require_farm(ctx)
    w = WeatherService().get_current_snapshot(ctx.db, farm)
    if not w.has_observations:
        return ToolResult.unavailable(
            "No weather observation is available for this location from any configured provider.",
            missing=["weather.temperature", "weather.humidity", "weather.rain_probability"],
            source=w.source,
        )
    data = {
        "temperature_c": w.temperature_c,
        "humidity_pct": w.humidity_pct,
        "rainfall_mm": w.rainfall_mm,
        "rain_probability_pct": w.rain_probability_pct,
        "wind_speed_kmh": w.wind_speed_kmh,
        "condition": w.condition,
        "warning_level": w.warning_level,
        "observed_at": w.observed_at.isoformat() if w.observed_at else None,
        "is_stale": w.is_stale,
    }
    # Built field by field: a provider can legitimately return humidity but no
    # temperature, and formatting a None as a float would crash the tool call.
    parts: list[str] = []
    if w.temperature_c is not None:
        parts.append(f"{w.temperature_c:.1f}°C")
    if w.humidity_pct is not None:
        parts.append(f"humidity {w.humidity_pct:.0f}%")
    if w.rain_probability_pct is not None:
        parts.append(f"rain probability {w.rain_probability_pct:.0f}%")
    if w.condition:
        parts.append(w.condition)
    observed_at = data["observed_at"] or ""
    return ToolResult(
        data=data,
        summary=", ".join(parts) or "A weather observation exists but contains no comparable fields.",
        sources=[{"domain": "Weather", "provider": w.source, "status": "STALE" if w.is_stale else "FRESH"}],
        evidence=[{"source": "weather", "value": ", ".join(parts), "timestamp": observed_at}]
        if parts
        else [],
        confidence=0.5 if w.is_stale else 0.85,
    )


def get_weather_forecast(ctx: ToolContext, args: BaseModel) -> ToolResult:
    """The stored forecast for the farm's location.

    Reads what a provider has already ingested; it does not call out to a
    provider mid-task, so a farmer's answer about tomorrow is based on the
    same forecast the weather screen shows.
    """
    farm = _require_farm(ctx)
    payload = HistoryInput.model_validate(args.model_dump())
    rows = (
        ctx.db.query(WeatherForecast)
        .filter(WeatherForecast.farm_id == farm.id)
        .order_by(WeatherForecast.forecast_time.asc())
        .limit(payload.limit)
        .all()
    )
    if not rows:
        return ToolResult.unavailable(
            "No forecast has been ingested for this farm's location.",
            missing=["weather.forecast"],
            source="forecast_not_synced",
        )
    return ToolResult(
        data={
            "count": len(rows),
            "items": [
                {
                    "forecast_time": r.forecast_time.isoformat() if r.forecast_time else None,
                    "temperature_c": r.temperature,
                    "humidity_pct": r.humidity,
                    "rain_probability_pct": r.rain_probability,
                    "rainfall_expected_mm": r.rainfall_expected_mm,
                    "wind_speed_kmh": r.wind_speed,
                    "condition": r.weather_condition,
                    "warning_level": r.warning_level,
                }
                for r in rows
            ],
        },
        summary=f"{len(rows)} forecast period(s) on record; next is {rows[0].forecast_time:%d %b %H:%M}."
        if rows[0].forecast_time
        else f"{len(rows)} forecast period(s) on record.",
        sources=[{"domain": "Weather forecast", "provider": rows[0].source, "status": "RECENT"}],
        confidence=0.7,
    )


def get_weather_alerts(ctx: ToolContext, _args: BaseModel) -> ToolResult:
    """Any active weather warning, from observations and forecast alike.

    An empty list is a real answer here: "no warning is in force" is exactly
    what a farmer needs to know before irrigating or spraying.
    """
    farm = _require_farm(ctx)
    warnings: list[dict] = []
    sources_seen: set[str] = set()

    forecasts = (
        ctx.db.query(WeatherForecast)
        .filter(WeatherForecast.farm_id == farm.id)
        .order_by(WeatherForecast.forecast_time.asc())
        .limit(10)
        .all()
    )
    for r in forecasts:
        if r.warning_level:
            warnings.append(
                {
                    "severity": str(r.warning_level).lower(),
                    "headline": f"{r.weather_condition or 'Weather warning'} on {r.forecast_time:%d %b}",
                    "detail": f"rain probability {r.rain_probability:.0f}%" if r.rain_probability is not None else None,
                }
            )
            sources_seen.add(r.source)

    observations = (
        ctx.db.query(WeatherObservation)
        .filter(WeatherObservation.farm_id == farm.id, WeatherObservation.warning_level.isnot(None))
        .order_by(WeatherObservation.observed_at.desc())
        .limit(10)
        .all()
    )
    for o in observations:
        if o.warning_level:
            warnings.append(
                {
                    "severity": str(o.warning_level).lower(),
                    "headline": o.weather_condition or "Weather warning",
                    "detail": f"observed at {o.observed_at:%d %b %H:%M}" if o.observed_at else None,
                }
            )
            sources_seen.add(o.source)

    return ToolResult(
        data={"count": len(warnings), "items": warnings},
        summary=(
            f"{len(warnings)} weather warning(s) in force for this location."
            if warnings
            else "No weather warning is in force for this location."
        ),
        sources=[
            {"domain": "Weather", "provider": s, "status": "RECENT"} for s in sorted(sources_seen)
        ]
        or [{"domain": "Weather", "provider": "forecast_store", "status": "NO_WARNING"}],
        confidence=0.75 if sources_seen else 0.6,
    )


# --- Soil ------------------------------------------------------------------


def get_soil(ctx: ToolContext, _args: BaseModel) -> ToolResult:
    farm = _require_farm(ctx)
    s = SoilService().get_snapshot(ctx.db, farm)
    if not s.has_observations:
        return ToolResult.unavailable(
            "No soil test or profile has been recorded for this farm.",
            missing=["soil.ph", "soil.npk", "soil.organic_carbon"],
            source=s.source,
        )
    parts: list[str] = []
    if s.ph is not None:
        parts.append(f"pH {s.ph:.1f}")
    if s.organic_carbon is not None:
        parts.append(f"organic carbon {s.organic_carbon:.2f}%")
    for label, value in (("N", s.nitrogen), ("P", s.phosphorus), ("K", s.potassium)):
        if value is not None:
            parts.append(f"{label} {value:.0f}")
    if s.moisture is not None:
        parts.append(f"moisture {s.moisture:.0f}%")
    return ToolResult(
        data={
            "ph": s.ph,
            "nitrogen": s.nitrogen,
            "phosphorus": s.phosphorus,
            "potassium": s.potassium,
            "organic_carbon": s.organic_carbon,
            "moisture": s.moisture,
            "sample_date": s.sample_date.isoformat() if s.sample_date else None,
            "soil_type": farm.soil_type,
        },
        summary=", ".join(parts) or "Partial soil data available.",
        sources=[{"domain": "Soil", "provider": s.source, "status": "RECENT"}],
        confidence=0.8,
    )


def get_soil_moisture(ctx: ToolContext, _args: BaseModel) -> ToolResult:
    farm = _require_farm(ctx)
    w = WaterService().get_snapshot(ctx.db, farm)
    if not w.has_data:
        return ToolResult.unavailable(
            "No water or soil-moisture reading is available for this farm.",
            missing=["water.soil_moisture", "water.rainfall"],
            source=w.source,
        )
    parts: list[str] = []
    if w.soil_moisture_pct is not None:
        parts.append(f"soil moisture {w.soil_moisture_pct:.0f}%")
    if w.rainfall_mm is not None:
        parts.append(f"rainfall {w.rainfall_mm:.1f} mm")
    if w.drought_index is not None:
        parts.append(f"drought index {w.drought_index:.2f}")
    if w.moisture_source_type:
        parts.append(f"via {w.moisture_source_type}")
    return ToolResult(
        data={
            "soil_moisture_pct": w.soil_moisture_pct,
            "rainfall_mm": w.rainfall_mm,
            "irrigation_applied_mm": w.irrigation_applied_mm,
            "drought_index": w.drought_index,
            "moisture_source_type": w.moisture_source_type,
            "observed_at": w.observed_at.isoformat() if w.observed_at else None,
        },
        summary=", ".join(parts),
        sources=[{"domain": "Water", "provider": w.source, "status": "RECENT"}],
        confidence=0.7,
    )


def get_soil_health(ctx: ToolContext, _args: BaseModel) -> ToolResult:
    farm = _require_farm(ctx)
    soil = SoilService().get_snapshot(ctx.db, farm)
    if not soil.has_observations:
        return ToolResult.unavailable(
            "Soil health cannot be scored: no soil test is on record.",
            missing=["soil.ph", "soil.organic_carbon"],
            source=soil.source,
        )
    result = SoilHealthService().evaluate(soil)
    payload = _service_result_payload(result)
    data = {
        "score": payload["score"] if payload["has_data"] else None,
        "label": payload["severity"] if payload["has_data"] else None,
        "ph": soil.ph,
        "organic_carbon": soil.organic_carbon,
        "nitrogen": soil.nitrogen,
        "phosphorus": soil.phosphorus,
        "potassium": soil.potassium,
        "recommendations": [f["detail"] or f["name"] for f in payload["factors"] if f.get("detail")],
    }
    return ToolResult(
        data=data,
        summary=(
            f"Soil health {data['label']} ({data['score']}/100)."
            if payload["has_data"]
            else "Soil health could not be scored from the available fields."
        ),
        sources=[{"domain": "Soil", "provider": soil.source, "status": "RECENT"}],
        confidence=0.75,
    )


# --- Satellite / vegetation ------------------------------------------------


def get_vegetation(ctx: ToolContext, _args: BaseModel) -> ToolResult:
    farm = _require_farm(ctx)
    v = SatelliteService().get_latest_snapshot(ctx.db, farm)
    if v.ndvi is None and v.evi is None:
        return ToolResult.unavailable(
            "No satellite vegetation observation is available for this farm.",
            missing=["vegetation.ndvi", "vegetation.evi"],
            source=v.source,
        )
    parts: list[str] = []
    if v.ndvi is not None:
        parts.append(f"NDVI {v.ndvi:.2f}")
    if v.evi is not None:
        parts.append(f"EVI {v.evi:.2f}")
    if v.trend_7d_pct is not None:
        parts.append(f"7-day trend {v.trend_7d_pct:+.1f}%")
    if v.vegetation_health:
        parts.append(v.vegetation_health)
    return ToolResult(
        data={
            "ndvi": v.ndvi,
            "evi": v.evi,
            "vegetation_health": v.vegetation_health,
            "observation_date": v.observation_date.isoformat() if v.observation_date else None,
            "is_dev_dataset": v.is_dev_dataset,
        },
        summary=", ".join(parts),
        sources=[
            {"domain": "Satellite", "provider": v.source, "status": "DEVELOPMENT_DATASET" if v.is_dev_dataset else "RECENT"}
        ],
        # A development dataset is not a real observation and must not be
        # presented with the same confidence as a live one.
        confidence=0.35 if v.is_dev_dataset else 0.8,
    )


def get_vegetation_trend(ctx: ToolContext, args: BaseModel) -> ToolResult:
    """NDVI direction over time, computed from the stored observation series.

    This is the tool behind "what changed this week": a single NDVI reading
    says nothing about direction, but a series does.
    """
    farm = _require_farm(ctx)
    payload = HistoryInput.model_validate(args.model_dump())
    rows = (
        ctx.db.query(SatelliteObservation)
        .filter(SatelliteObservation.farm_id == farm.id)
        .order_by(SatelliteObservation.observation_date.asc())
        .limit(payload.limit)
        .all()
    )
    points = [
        {
            "observation_date": o.observation_date.isoformat() if o.observation_date else None,
            "ndvi": o.ndvi,
        }
        for o in rows
    ]
    with_ndvi = [p["ndvi"] for p in points if p["ndvi"] is not None]
    if len(with_ndvi) < 2:
        return ToolResult(
            data={"points": points, "trend_7d_pct": None, "direction": None},
            summary=(
                "Fewer than two NDVI observations are on record, so no trend can be computed."
                if with_ndvi
                else "No NDVI observation is on record for this farm."
            ),
            sources=[{"domain": "Satellite", "provider": "bhoomi-sync-engine", "status": "RECENT"}],
            missing_data=["vegetation.ndvi_series"],
            confidence=0.3,
        )

    change_pct = round(((with_ndvi[-1] - with_ndvi[0]) / with_ndvi[0]) * 100, 1) if with_ndvi[0] else None
    direction = "rising" if (change_pct or 0) > 1 else "falling" if (change_pct or 0) < -1 else "flat"
    latest_is_dev = any(o.is_dev_dataset for o in rows[-3:])
    return ToolResult(
        data={"points": points, "trend_7d_pct": change_pct, "direction": direction},
        summary=(
            f"NDVI is {direction} ({change_pct:+.1f}%) across {len(with_ndvi)} observation(s), "
            f"now {with_ndvi[-1]:.2f}."
        ),
        sources=[
            {
                "domain": "Satellite",
                "provider": rows[-1].source,
                "status": "DEVELOPMENT_DATASET" if latest_is_dev else "RECENT",
            }
        ],
        confidence=0.4 if latest_is_dev else 0.8,
    )


# --- Water / climate risk --------------------------------------------------


def get_water(ctx: ToolContext, _args: BaseModel) -> ToolResult:
    farm = _require_farm(ctx)
    w = WaterService().get_snapshot(ctx.db, farm)
    if not w.has_data:
        return ToolResult.unavailable(
            "No water or soil-moisture reading is available for this farm.",
            missing=["water.soil_moisture", "water.rainfall"],
            source=w.source,
        )
    parts: list[str] = []
    if w.soil_moisture_pct is not None:
        parts.append(f"soil moisture {w.soil_moisture_pct:.0f}%")
    if w.rainfall_mm is not None:
        parts.append(f"rainfall {w.rainfall_mm:.1f} mm")
    if w.drought_index is not None:
        parts.append(f"drought index {w.drought_index:.2f}")
    if w.moisture_source_type:
        parts.append(f"via {w.moisture_source_type}")
    return ToolResult(
        data={
            "soil_moisture_pct": w.soil_moisture_pct,
            "rainfall_mm": w.rainfall_mm,
            "irrigation_applied_mm": w.irrigation_applied_mm,
            "drought_index": w.drought_index,
            "moisture_source_type": w.moisture_source_type,
            "observed_at": w.observed_at.isoformat() if w.observed_at else None,
        },
        summary=", ".join(parts),
        sources=[{"domain": "Water", "provider": w.source, "status": "RECENT"}],
        confidence=0.7,
    )


def get_irrigation_history(ctx: ToolContext, args: BaseModel) -> ToolResult:
    """Recorded water applied to this farm over a recent window.

    ``irrigation_applied_mm`` is what the data network reports alongside a
    moisture reading. Where a provider reports no applied depth, this says the
    volume is unknown rather than treating the absence as zero millimetres,
    because "not recorded" and "no water" lead to opposite irrigation advice.
    """
    farm = _require_farm(ctx)
    payload = HistoryInput.model_validate(args.model_dump())
    since = datetime.now(timezone.utc) - timedelta(days=payload.days)
    rows = (
        ctx.db.query(WaterObservation)
        .filter(
            WaterObservation.farm_id == farm.id,
            WaterObservation.observed_at >= since,
        )
        .order_by(WaterObservation.observed_at.desc())
        .limit(payload.limit)
        .all()
    )
    if not rows:
        return ToolResult.unavailable(
            f"No water reading was recorded for this farm in the last {payload.days} days.",
            missing=["water.irrigation_applied", "water.soil_moisture"],
            source="no_observations",
        )

    applied = [r.irrigation_applied_mm for r in rows if r.irrigation_applied_mm is not None]
    moisture = [r.soil_moisture_pct for r in rows if r.soil_moisture_pct is not None]
    total = round(sum(applied), 2)
    return ToolResult(
        data={
            "days": payload.days,
            "event_count": len(rows),
            "total_applied_mm": total,
            "mean_soil_moisture_pct": round(sum(moisture) / len(moisture), 1) if moisture else None,
            "items": [
                {
                    "observed_at": r.observed_at.isoformat() if r.observed_at else None,
                    "applied_mm": r.irrigation_applied_mm,
                    "moisture_source_type": r.moisture_source_type,
                    "quality_status": r.quality_status,
                    "source": r.source,
                }
                for r in rows
            ],
        },
        summary=(
            f"{len(rows)} water reading(s) in {payload.days} days"
            + (
                f"; {total:.1f} mm applied across {len(applied)} reading(s)"
                + (", not reported for the rest" if len(applied) < len(rows) else "")
                if applied
                else "; applied volume not reported for any reading"
            )
            + (
                f", mean moisture {sum(moisture) / len(moisture):.0f}%."
                if moisture
                else "."
            )
        ),
        sources=[{"domain": "Water", "provider": rows[0].source, "status": "RECENT"}],
        # Lower than a single reading: these rows come from a data network, and
        # a missing applied depth means the total is a floor, not an exact sum.
        confidence=0.6 if applied else 0.4,
    )


def calculate_water_risk(ctx: ToolContext, _args: BaseModel) -> ToolResult:
    """Water stress from the recorded weather and soil, plus irrigation setup."""
    farm = _require_farm(ctx)
    weather = WeatherService().get_current_snapshot(ctx.db, farm)
    soil = SoilService().get_snapshot(ctx.db, farm)
    result = WaterStressService().evaluate(weather, soil, farm.irrigation_type)
    payload = _service_result_payload(result)
    water = WaterService().get_snapshot(ctx.db, farm)
    data = {
        "stress_level": payload["severity"] if payload["has_data"] else None,
        "drought_index": water.drought_index,
        "soil_moisture_pct": water.soil_moisture_pct,
        "irrigation_type": farm.irrigation_type,
        "water_source": farm.water_source,
        "recommendation": next(
            (f["detail"] for f in payload["factors"] if f.get("detail")),
            None,
        ),
    }
    return ToolResult(
        data=data,
        summary=(
            f"Water stress is {payload['severity']} ({payload['score']}/100, 100 = no stress)."
            if payload["has_data"]
            else "Water stress could not be scored: no usable weather or soil observation."
        ),
        sources=[
            {"domain": "Weather", "provider": weather.source, "status": "STALE" if weather.is_stale else "FRESH"},
            {"domain": "Soil", "provider": soil.source, "status": "RECENT"},
        ],
        missing_data=[] if payload["has_data"] else ["water.stress_inputs"],
        confidence=0.7 if payload["has_data"] else 0.3,
    )


def calculate_climate_risk(ctx: ToolContext, _args: BaseModel) -> ToolResult:
    """Heat and rainfall risk for the current season from the live observation."""
    farm = _require_farm(ctx)
    weather = WeatherService().get_current_snapshot(ctx.db, farm)
    if not weather.has_observations:
        return ToolResult.unavailable(
            "Climate risk cannot be assessed without a current weather observation.",
            missing=["weather.temperature", "weather.rain_probability"],
            source=weather.source,
        )
    result = ClimateRiskService().evaluate(weather)
    payload = _service_result_payload(result)
    data = {
        "risk_level": payload["severity"] if payload["has_data"] else None,
        "heat_stress_days": None,
        "rainfall_anomaly_pct": None,
        "frost_risk": bool(
            weather.temperature_c is not None and weather.temperature_c <= 2.0
        ),
        "recommendation": next(
            (f["detail"] for f in payload["factors"] if f.get("detail")),
            None,
        ),
    }
    return ToolResult(
        data=data,
        summary=(
            f"Climate risk is {payload['severity']} ({payload['score']}/100, 100 = minimal risk)."
            if payload["has_data"]
            else "Climate risk could not be scored."
        ),
        sources=[
            {"domain": "Weather", "provider": weather.source, "status": "STALE" if weather.is_stale else "FRESH"}
        ],
        confidence=0.55 if weather.is_stale else 0.75,
    )


# --- Crop health / risk ----------------------------------------------------


def get_crop_health(ctx: ToolContext, _args: BaseModel) -> ToolResult:
    """Crop vigour from the vegetation index, scored by the crop-health engine."""
    farm = _require_farm(ctx)
    veg = SatelliteService().get_latest_snapshot(ctx.db, farm)
    if veg.ndvi is None and veg.evi is None:
        return ToolResult.unavailable(
            "Crop health cannot be scored: no vegetation index is on record.",
            missing=["vegetation.ndvi"],
            source=veg.source,
        )
    result = VegetationHealthService().evaluate(veg)
    payload = _service_result_payload(result)
    days_after = (
        (date.today() - farm.sowing_date).days if farm.sowing_date else None
    )
    data = {
        "health_score": payload["score"] if payload["has_data"] else None,
        "label": payload["severity"] if payload["has_data"] else None,
        "current_crop": farm.current_crop,
        "stage": farm.crop_stage,
        "days_after_sowing": days_after,
        "factors": [f["detail"] or f["name"] for f in payload["factors"]],
    }
    return ToolResult(
        data=data,
        summary=(
            f"Crop health {payload['severity']} ({payload['score']}/100) from the latest vegetation index."
            if payload["has_data"]
            else "Crop health could not be scored."
        ),
        sources=[
            {
                "domain": "Satellite",
                "provider": veg.source,
                "status": "DEVELOPMENT_DATASET" if veg.is_dev_dataset else "RECENT",
            }
        ],
        confidence=0.35 if veg.is_dev_dataset else 0.75,
    )


def get_crop_risk(ctx: ToolContext, _args: BaseModel) -> ToolResult:
    """The last computed multi-dimensional risk score for this farm."""
    farm = _require_farm(ctx)
    latest = (
        ctx.db.query(FarmRiskScore)
        .filter(FarmRiskScore.farm_id == farm.id)
        .order_by(FarmRiskScore.created_at.desc())
        .first()
    )
    if latest is None:
        return ToolResult.unavailable(
            "No risk score has been computed for this farm yet.",
            missing=["risk.score"],
            source="risk_engine",
        )
    dimensions = {
        "climate_risk": latest.climate_risk,
        "water_stress": latest.water_stress,
        "disease_risk": latest.disease_risk,
        "vegetation_stress": latest.vegetation_stress,
        "soil_health": latest.soil_health,
    }
    top = max(dimensions.items(), key=lambda kv: _severity_rank(kv[1]))
    data = {
        "overall_risk": top[1],
        "dimensions": dimensions,
        "top_factor": f"{top[0]} is the highest current risk ({top[1]})",
    }
    return ToolResult(
        data=data,
        summary=f"Highest current risk is {top[0]} ({top[1]}).",
        sources=[{"domain": "Risk engine", "provider": "bhoomi-risk-engine", "status": "RECENT"}],
        confidence=0.75,
    )


def get_farm_health(ctx: ToolContext, _args: BaseModel) -> ToolResult:
    """The composite farm health score with its component breakdown."""
    farm = _require_farm(ctx)
    weather = WeatherService().get_current_snapshot(ctx.db, farm)
    soil = SoilService().get_snapshot(ctx.db, farm)
    veg = SatelliteService().get_latest_snapshot(ctx.db, farm)
    health = FarmHealthService().compute(_farm_context(farm), weather, soil, veg)

    data = {
        "farm_id": str(farm.id),
        "score": health.farm_health_score,
        "label": health.label,
        "has_data": health.has_data,
        "data_coverage": round(health.data_coverage, 2),
        "missing_inputs": health.missing_inputs,
        "climate_risk": health.climate_risk,
        "water_stress": health.water_stress,
        "disease_risk": health.disease_risk,
        "vegetation_stress": health.vegetation_stress,
        "soil_health": health.soil_health,
        "breakdown": health.breakdown,
        "factors": health.factors,
    }

    latest = (
        ctx.db.query(FarmRiskScore)
        .filter(FarmRiskScore.farm_id == farm.id)
        .order_by(FarmRiskScore.created_at.desc())
        .first()
    )
    if latest:
        # The stored row carries the engine's own dimension snapshot and the
        # timestamp it was computed at. Its `factors` column is a dict keyed by
        # factor name, so it is reported separately rather than merged into the
        # list the health result uses.
        data["risk_dimensions"] = {
            "climate_risk": latest.climate_risk,
            "water_stress": latest.water_stress,
            "disease_risk": latest.disease_risk,
            "vegetation_stress": latest.vegetation_stress,
            "soil_health": latest.soil_health,
        }
        data["computed_at"] = latest.created_at.isoformat() if latest.created_at else None

    if not health.has_data:
        return ToolResult.unavailable(
            "No farm health score can be computed yet: none of the required observations are present.",
            missing=health.missing_inputs,
        )

    return ToolResult(
        data=data,
        summary=(
            f"Farm health {health.label} ({round(health.farm_health_score, 1)}/100) from "
            f"{int(health.data_coverage * 100)}% data coverage."
        ),
        sources=[
            {"domain": "Weather", "provider": weather.source, "status": "STALE" if weather.is_stale else "FRESH"},
            {"domain": "Soil", "provider": soil.source, "status": "RECENT"},
            {"domain": "Satellite", "provider": veg.source, "status": "RECENT"},
        ],
        missing_data=health.missing_inputs,
        confidence=0.8 if health.data_coverage > 0.6 else 0.55,
    )


def analyze_farm(ctx: ToolContext, _args: BaseModel) -> ToolResult:
    """The full data-fusion intelligence view for this farm.

    This is the one tool that answers "check my farm" end to end. It reuses the
    pipeline the Farm Intelligence screen runs, so the agent's answer and the
    screen cannot disagree. It is registered read-only with respect to the
    agent's own tables; the pipeline's own risk-score snapshot is written by the
    intelligence service exactly as it would be from the screen.
    """
    farm = _require_farm(ctx)
    report = IntelligenceService().compute_and_persist(ctx.db, farm, user_id=ctx.user_id, with_ai=False)
    health = report.get("health") or {}
    risks = [
        f"{name.replace('_', ' ')}: {value}"
        for name, value in (
            ("climate", health.get("climate_risk")),
            ("water stress", health.get("water_stress")),
            ("soil health", health.get("soil_health")),
            ("vegetation stress", health.get("vegetation_stress")),
            ("disease", health.get("disease_risk")),
        )
        if value
    ]
    data = {
        "farm_id": str(farm.id),
        "summary": (
            f"{farm.name}: health {health.get('label')} "
            f"({round(health['score'], 1) if health.get('score') is not None else 'n/a'}/100), "
            f"{len(report.get('advisories') or [])} advisory(ies), "
            f"{int((health.get('data_coverage') or 0) * 100)}% data coverage."
        ),
        "health": health,
        "risks": risks,
        "advisories": [
            {
                "type": a.get("type"),
                "severity": a.get("severity"),
                "title": a.get("title"),
                "summary": a.get("summary"),
                "actions": a.get("actions") or [],
                "confidence": a.get("confidence"),
            }
            for a in (report.get("advisories") or [])
        ],
        "data_coverage": health.get("data_coverage"),
    }
    return ToolResult(
        data=data,
        summary=data["summary"],
        sources=report.get("sources") or [],
        missing_data=health.get("missing_inputs") or [],
        confidence=0.8 if (health.get("data_coverage") or 0) > 0.6 else 0.5,
    )


# --- Advisory --------------------------------------------------------------


def list_advisories(ctx: ToolContext, args: BaseModel) -> ToolResult:
    farm = _require_farm(ctx)
    payload = AdvisoryInput.model_validate(args.model_dump())
    query = ctx.db.query(Advisory).filter(Advisory.farm_id == farm.id)
    if payload.severity:
        query = query.filter(Advisory.severity == payload.severity)
    rows = query.order_by(Advisory.created_at.desc()).limit(payload.limit).all()
    return ToolResult(
        data={
            "count": len(rows),
            "items": [
                {
                    "id": str(a.id),
                    "type": a.type.value,
                    "severity": a.severity.value,
                    "title": a.title,
                    "summary": a.summary,
                    "actions": a.actions,
                    "confidence": a.confidence,
                    "review_status": a.review_status.value,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in rows
            ],
        },
        summary=(
            f"{len(rows)} advisory(ies) on record"
            + (f", most recent is '{rows[0].title}' ({rows[0].severity.value})." if rows else ".")
        ),
        sources=[{"domain": "Advisories", "provider": "rule_engine", "status": "RECENT"}],
        confidence=0.75,
    )


def compute_advisories(ctx: ToolContext, _args: BaseModel) -> ToolResult:
    """Recompute rule-based advisories from current observations.

    Returns the engine's output rather than persisting it, so running it cannot
    create advisory rows the farmer did not ask for. Persisting is what the
    separate, approval-gated ``create_advisory`` action is for.
    """
    farm = _require_farm(ctx)
    weather = WeatherService().get_current_snapshot(ctx.db, farm)
    soil = SoilService().get_snapshot(ctx.db, farm)
    veg = SatelliteService().get_latest_snapshot(ctx.db, farm)
    health = FarmHealthService().compute(_farm_context(farm), weather, soil, veg)
    advisories = generate_deterministic_advisories(ctx.db, farm, _farm_context(farm), weather, soil, veg, health)
    return ToolResult(
        data={
            "items": [
                {
                    "type": a.type.value,
                    "severity": a.severity.value,
                    "title": a.title,
                    "summary": a.summary,
                    "actions": a.actions,
                    "evidence": a.evidence,
                    "confidence": a.confidence,
                }
                for a in advisories
            ]
        },
        summary=(
            f"{len(advisories)} rule-based advisory(ies) derived from current observations."
            if advisories
            else "No advisory is triggered by the current observations."
        ),
        sources=[{"domain": "Rule engine", "provider": "bhoomi-deterministic-rules", "status": "COMPUTED"}],
        missing_data=health.missing_inputs,
        confidence=0.7,
    )


# --- Disease ---------------------------------------------------------------


def get_disease_history(ctx: ToolContext, args: BaseModel) -> ToolResult:
    farm = _require_farm(ctx)
    payload = DiseaseInput.model_validate(args.model_dump())
    rows = (
        ctx.db.query(DiseaseScan)
        .filter(DiseaseScan.farm_id == farm.id)
        .order_by(DiseaseScan.created_at.desc())
        .limit(payload.limit)
        .all()
    )
    if not rows:
        return ToolResult(
            data={"count": 0, "items": []},
            summary="No crop-disease image has been analysed for this farm yet.",
            missing_data=["disease.scan"],
            sources=[{"domain": "Disease", "provider": "not_assessed", "status": "NOT_ASSESSED"}],
            confidence=0.9,
        )
    return ToolResult(
        data={
            "count": len(rows),
            "items": [
                {
                    "crop": s.crop,
                    "possible_disease": s.possible_disease,
                    # Always framed as a hypothesis: a leaf-image classifier
                    # is not a diagnosis.
                    "hypothesis_confidence": s.confidence,
                    "severity": s.severity,
                    "limitations": s.limitations,
                    "recommended_actions": s.recommended_actions,
                    "observed_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in rows
            ],
            "disclaimer": (
                "Leaf-image results are hypotheses for agronomist review, not a confirmed diagnosis."
            ),
        },
        summary=f"{len(rows)} previous crop-disease scan(s); latest hypothesis '{rows[0].possible_disease}'.",
        sources=[{"domain": "Disease", "provider": "disease_classifier", "status": "RECENT"}],
        confidence=0.5,
    )


# --- Knowledge / cooperation -----------------------------------------------


def search_knowledge(ctx: ToolContext, args: BaseModel) -> ToolResult:
    """Semantic search over the curated agricultural knowledge base.

    Returns excerpts only -- never a whole document -- and each hit carries the
    publishing authority so an answer can be traced back to its source. The
    table has no review/approval column, so every row in it is treated as
    publishable; the curation itself happens when documents are loaded.
    """
    payload = KnowledgeQueryInput.model_validate(args.model_dump())
    vector = EmbeddingService().embed([payload.query])[0]
    rows = (
        ctx.db.query(KnowledgeChunk, KnowledgeDocument)
        .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .filter(KnowledgeChunk.embedding.isnot(None))
        .order_by(KnowledgeChunk.embedding.cosine_distance(vector))
        .limit(payload.limit)
        .all()
    )
    return ToolResult(
        data={
            "query": payload.query,
            "count": len(rows),
            "results": [
                {
                    "document_id": str(doc.id),
                    "title": doc.title,
                    "authority": doc.authority,
                    "excerpt": chunk.content[:280],
                }
                for chunk, doc in rows
            ],
        },
        summary=(
            f"{len(rows)} knowledge document(s) matched '{payload.query}'."
            if rows
            else f"No knowledge document matched '{payload.query}'."
        ),
        sources=[{"domain": "Knowledge base", "provider": "bhoomi-knowledge", "status": "RECENT"}],
        missing_data=[] if rows else ["knowledge.match"],
        confidence=0.7 if rows else 0.3,
    )


def find_shared_models(ctx: ToolContext, _args: BaseModel) -> ToolResult:
    """Models other state nodes have published for sharing.

    Only entries explicitly marked ``shared`` are returned; a state node's
    internal model is not part of the cooperative surface.
    """
    rows = (
        ctx.db.query(ModelRegistryEntry)
        .filter(
            ModelRegistryEntry.visibility == "shared",
            ModelRegistryEntry.status == "published",
        )
        .order_by(ModelRegistryEntry.created_at.desc())
        .limit(50)
        .all()
    )
    return ToolResult(
        data={
            "count": len(rows),
            "items": [
                {
                    "id": str(m.id),
                    "name": m.name,
                    "model_type": m.model_type,
                    "crop": m.crop,
                    "version": m.version,
                    "accuracy": m.accuracy,
                    "description": m.description,
                    "is_demo": m.is_demo,
                }
                for m in rows
            ],
        },
        summary=(
            f"{len(rows)} shared model(s) available from the cooperation network."
            if rows
            else "No models are currently shared on the cooperation network."
        ),
        sources=[{"domain": "Cooperation", "provider": "bhoomi-state-nodes", "status": "RECENT"}],
        missing_data=[] if rows else ["cooperation.shared_models"],
        confidence=0.9,
    )


def get_model_details(ctx: ToolContext, args: BaseModel) -> ToolResult:
    payload = ModelLookupInput.model_validate(args.model_dump())
    entry = ctx.db.get(ModelRegistryEntry, payload.model_id)
    if entry is None:
        # A miss is an answer, not an error: the model asked for a record that
        # does not exist, which it must be told plainly rather than have the
        # call recorded as a tool failure.
        return ToolResult(
            data={"id": payload.model_id},
            summary="No model with that id is published on the cooperation network.",
            sources=[{"domain": "Cooperation", "provider": "bhoomi-state-nodes", "status": "NOT_FOUND"}],
            missing_data=["cooperation.shared_model"],
            available=False,
        )
    node = ctx.db.get(StateNode, entry.publisher_state_node_id)
    return ToolResult(
        data={
            "id": str(entry.id),
            "name": entry.name,
            "model_type": entry.model_type,
            "crop": entry.crop,
            "version": entry.version,
            "accuracy": entry.accuracy,
            "description": entry.description,
            "supported_regions": entry.supported_regions or [],
            "license": entry.license,
            "publisher_state": node.state if node else None,
            "is_demo": entry.is_demo,
        },
        summary=(
            f"{entry.name} ({entry.model_type}, {entry.crop}) v{entry.version}"
            + (f", reported accuracy {entry.accuracy:.0%}" if entry.accuracy is not None else "")
            + "."
        ),
        sources=[{"domain": "Cooperation", "provider": "bhoomi-state-nodes", "status": "RECENT"}],
        confidence=0.9,
    )


# --- helpers ---------------------------------------------------------------


def datetime_now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def _severity_rank(value: str | None) -> int:
    return {"low": 0, "moderate": 1, "high": 2, "critical": 3}.get(str(value or "").lower(), -1)


def _expected_stage(days_after: int) -> str | None:
    """The stage whose coarse day band contains ``days_after``, if any."""
    for stage, (low, high) in _STAGE_DAY_BANDS.items():
        if low <= days_after <= high:
            return stage
    return None


def _stage_distance(recorded: str | None, expected: str | None) -> int | None:
    """How many stages apart the recorded and expected stages are.

    None when either stage is unrecorded or outside the known order, so an
    unknown stage is reported as unknown rather than as "on track".
    """
    if not recorded or not expected:
        return None
    recorded = recorded.lower()
    if recorded not in _CROP_STAGE_ORDER or expected not in _CROP_STAGE_ORDER:
        return None
    return abs(_CROP_STAGE_ORDER.index(recorded) - _CROP_STAGE_ORDER.index(expected))


# --- Registration ----------------------------------------------------------

_READ_TOOLS: tuple[tuple[str, str, ToolHandler_, type[BaseModel], type[BaseModel] | None, tuple[str, ...], tuple[str, ...]], ...] = (
    # (name, summary, handler, input_model, output_model, scopes, tags)
    (
        "farm_snapshot",
        "Get the current crop, area, location and irrigation details of the selected farm.",
        get_farm_snapshot,
        _NoInput,
        FarmProfileOutput,
        (SCOPE_FARM_READ,),
        ("farm", "profile"),
    ),
    (
        "list_my_farms",
        "List the farms registered on the user's own account.",
        list_my_farms,
        ListMyFarmsInput,
        FarmListOutput,
        (SCOPE_FARM_READ,),
        ("farm", "profile"),
    ),
    (
        "get_crop_cycle",
        "Current crop stage and days elapsed since sowing for the selected farm.",
        get_crop_cycle,
        _NoInput,
        CropStageOutput,
        (SCOPE_FARM_READ,),
        ("farm", "crop", "history"),
    ),
    (
        "get_farm_history",
        "Recorded advisories, risk scores and vegetation observations for the farm over a time window.",
        get_farm_history,
        HistoryInput,
        FarmHistoryOutput,
        (SCOPE_FARM_READ, SCOPE_ADVISORY_READ, SCOPE_SATELLITE_READ),
        ("farm", "history"),
    ),
    (
        "weather_now",
        "Current weather observation for the farm's location.",
        get_weather,
        _NoInput,
        WeatherOutput,
        (SCOPE_WEATHER_READ,),
        ("weather",),
    ),
    (
        "get_weather_forecast",
        "Ingested multi-day weather forecast for the farm's location.",
        get_weather_forecast,
        HistoryInput,
        WeatherForecastOutput,
        (SCOPE_WEATHER_READ,),
        ("weather", "forecast"),
    ),
    (
        "get_weather_alerts",
        "Weather warnings currently in force for the farm's location.",
        get_weather_alerts,
        _NoInput,
        WeatherAlertsOutput,
        (SCOPE_WEATHER_READ,),
        ("weather", "alert"),
    ),
    (
        "soil_profile",
        "Recorded soil chemistry for the farm.",
        get_soil,
        _NoInput,
        SoilOutput,
        (SCOPE_SOIL_READ,),
        ("soil",),
    ),
    (
        "get_soil_moisture",
        "Soil moisture, rainfall and drought indicators for the farm.",
        get_soil_moisture,
        _NoInput,
        WaterOutput,
        (SCOPE_WATER_READ,),
        ("soil", "water"),
    ),
    (
        "get_irrigation_history",
        "Water applied to the farm over a recent window, with moisture context.",
        get_irrigation_history,
        HistoryInput,
        IrrigationHistoryOutput,
        (SCOPE_WATER_READ,),
        ("soil", "water", "history"),
    ),
    (
        "get_soil_health",
        "Scored soil health with pH, organic carbon and nutrient context.",
        get_soil_health,
        _NoInput,
        SoilHealthOutput,
        (SCOPE_SOIL_READ,),
        ("soil", "health"),
    ),
    (
        "vegetation_index",
        "Latest satellite vegetation indices (NDVI/EVI) for the farm.",
        get_vegetation,
        _NoInput,
        SatelliteOutput,
        (SCOPE_SATELLITE_READ,),
        ("vegetation", "satellite"),
    ),
    (
        "get_vegetation_trend",
        "NDVI direction and change over a series of stored observations.",
        get_vegetation_trend,
        HistoryInput,
        VegetationTrendOutput,
        (SCOPE_SATELLITE_READ,),
        ("vegetation", "satellite", "history"),
    ),
    (
        "water_status",
        "Soil moisture and drought indicators.",
        get_water,
        _NoInput,
        WaterOutput,
        (SCOPE_WATER_READ,),
        ("water",),
    ),
    (
        "calculate_water_risk",
        "Water stress score for the farm given current weather, soil and irrigation setup.",
        calculate_water_risk,
        _NoInput,
        WaterRiskOutput,
        (SCOPE_WATER_READ, SCOPE_INTELLIGENCE_READ),
        ("water", "risk"),
    ),
    (
        "calculate_climate_risk",
        "Heat and rainfall risk for the farm's current season.",
        calculate_climate_risk,
        _NoInput,
        ClimateRiskOutput,
        (SCOPE_WEATHER_READ, SCOPE_INTELLIGENCE_READ),
        ("climate", "risk"),
    ),
    (
        "get_crop_health",
        "Scored crop vigour from the latest vegetation index.",
        get_crop_health,
        _NoInput,
        CropHealthOutput,
        (SCOPE_SATELLITE_READ, SCOPE_INTELLIGENCE_READ),
        ("crop", "health"),
    ),
    (
        "get_crop_risk",
        "Highest current risk dimension for the farm from the risk engine.",
        get_crop_risk,
        _NoInput,
        CropRiskOutput,
        (SCOPE_INTELLIGENCE_READ,),
        ("crop", "risk"),
    ),
    (
        "farm_health",
        "Compute the composite farm health score with its component breakdown and missing inputs.",
        get_farm_health,
        _NoInput,
        FarmHealthOutput,
        (SCOPE_FARM_READ, SCOPE_INTELLIGENCE_READ),
        ("health", "risk"),
    ),
    (
        "analyze_farm",
        "Full data-fusion intelligence view: health, risks and rule-based advisories for the farm.",
        analyze_farm,
        _NoInput,
        FarmAnalysisOutput,
        (SCOPE_FARM_READ, SCOPE_INTELLIGENCE_READ, SCOPE_ADVISORY_READ),
        ("health", "risk", "advisory", "analysis"),
    ),
    (
        "list_advisories",
        "Advisories already generated for the farm.",
        list_advisories,
        AdvisoryInput,
        AdvisoryListOutput,
        (SCOPE_ADVISORY_READ,),
        ("advisory",),
    ),
    (
        "compute_advisories",
        "Derive fresh rule-based advisories from current observations without saving them.",
        compute_advisories,
        _NoInput,
        AdvisoryListOutput,
        (SCOPE_ADVISORY_READ, SCOPE_INTELLIGENCE_READ),
        ("advisory",),
    ),
    (
        "disease_history",
        "Previous crop-disease image analyses as hypotheses for review.",
        get_disease_history,
        DiseaseInput,
        DiseaseHistoryOutput,
        (SCOPE_DISEASE_READ,),
        ("disease",),
    ),
    (
        "search_agricultural_knowledge",
        "Semantic search over the curated agricultural knowledge base.",
        search_knowledge,
        KnowledgeQueryInput,
        KnowledgeSearchOutput,
        (SCOPE_KNOWLEDGE_READ,),
        ("knowledge",),
    ),
    (
        "find_shared_models",
        "Models published for sharing by other state nodes.",
        find_shared_models,
        _NoInput,
        SharedModelsOutput,
        (SCOPE_COOPERATION_READ,),
        ("cooperation",),
    ),
    (
        "get_model_details",
        "Full record for one shared model on the cooperation network.",
        get_model_details,
        ModelLookupInput,
        ModelDetailOutput,
        (SCOPE_COOPERATION_READ,),
        ("cooperation",),
    ),
)




def build_default_registry() -> ToolRegistry:
    """Registers the read-only observation tools.

    Safe to call more than once: re-registering the same tool replaces it rather
    than raising, so a module reload or a second import path cannot leave the
    process with a half-populated registry.
    """
    reg = registry
    for name, summary, handler, input_model, output_model, scopes, tags in _READ_TOOLS:
        reg.register(
            ToolSpec(
                name=name,
                version=TOOL_VERSION,
                summary=summary,
                input_model=input_model,
                output_model=output_model,
                handler=handler,
                risk_level=ToolRiskLevel.READ_ONLY,
                required_permissions=scopes,
                source="bhoomi-services",
                tags=tags,
                aliases=_TOOL_ALIASES.get(name, ()),
            ),
            replace=True,
        )
    return reg


__all__ = ["build_default_registry", "registry", "TOOL_VERSION"]