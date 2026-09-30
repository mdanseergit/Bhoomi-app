"""
IntelligenceService -- orchestrates the full data-fusion pipeline for a farm
and returns the consolidated view used by the "Farm Intelligence" screen.
"""
from sqlalchemy.orm import Session

from datetime import datetime, timezone
import uuid

from app.core.prompts import build_bhoomi_prompt
from app.integrations.data_network.base import FreshnessState
from app.integrations.data_network.quality_service import DataQualityService
from app.models.data_network import FarmDataSnapshot
from app.models.disease import DiseaseScan
from app.models.farm import Farm
from app.models.risk import FarmRiskScore
from app.services.advisory_engine import generate_deterministic_advisories
from app.services.agriculture.farm_health import FarmHealthService
from app.services.agriculture.schema import FarmContext
from app.services.ai_service import AIService
from app.services.satellite_service import SatelliteService
from app.services.soil_service import SoilService
from app.services.water_service import WaterService
from app.services.weather_service import WeatherService


class IntelligenceService:
    def __init__(self) -> None:
        self.weather_service = WeatherService()
        self.soil_service = SoilService()
        self.satellite_service = SatelliteService()
        self.water_service = WaterService()
        self.farm_health_service = FarmHealthService()
        self.ai_service = AIService()

    def compute_and_persist(self, db: Session, farm: Farm, user_id: str | None = None, with_ai: bool = True) -> dict:
        weather = self.weather_service.get_current_snapshot(db, farm)
        soil = self.soil_service.get_snapshot(db, farm)
        veg = self.satellite_service.get_latest_snapshot(db, farm)
        water = self.water_service.get_snapshot(db, farm)

        farm_ctx = FarmContext(
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

        health = self.farm_health_service.compute(farm_ctx, weather, soil, veg)

        risk_row = FarmRiskScore(
            farm_id=farm.id,
            farm_health_score=health.farm_health_score,
            climate_risk=health.climate_risk,
            water_stress=health.water_stress,
            disease_risk=health.disease_risk,
            vegetation_stress=health.vegetation_stress,
            soil_health=health.soil_health,
            breakdown=health.breakdown,
            factors=health.factors,
            evidence={
                "weather": {
                    "temperature_c": weather.temperature_c,
                    "rain_probability_pct": weather.rain_probability_pct,
                    "source": weather.source,
                    "is_stale": weather.is_stale,
                },
                "soil": {"ph": soil.ph, "organic_carbon": soil.organic_carbon, "source": soil.source},
                "vegetation": {"ndvi": veg.ndvi, "trend_7d_pct": veg.trend_7d_pct, "source": veg.source, "is_dev_dataset": veg.is_dev_dataset},
            },
        )
        db.add(risk_row)
        db.commit()
        db.refresh(risk_row)

        advisories = generate_deterministic_advisories(db, farm, farm_ctx, weather, soil, veg, health)

        # Check for any recent disease scans
        latest_disease = (
            db.query(DiseaseScan)
            .filter(DiseaseScan.farm_id == farm.id)
            .order_by(DiseaseScan.created_at.desc())
            .first()
        )

        ai_explanation = None
        raw_provider_used = None
        if with_ai:
            farm_data = {
                "id": str(farm.id),
                "name": farm.name,
                "location": f"{farm.district}, {farm.state}" if farm.district and farm.state else (farm.state or farm.district or "Not provided"),
                "state": farm.state,
                "district": farm.district,
                "area_hectares": farm.area_hectares,
                "crop": farm.current_crop,
                "crop_stage": farm.crop_stage,
                "previous_crop": farm.previous_crop,
                "irrigation_type": farm.irrigation_type,
                "water_source": farm.water_source,
                "soil": {
                    "ph": soil.ph,
                    "organic_carbon": soil.organic_carbon,
                    "nitrogen": soil.nitrogen,
                    "phosphorus": soil.phosphorus,
                    "potassium": soil.potassium,
                    "source": soil.source,
                },
                "water": {
                    "irrigation_type": farm.irrigation_type,
                    "water_source": farm.water_source,
                    "stress_level": health.water_stress,
                },
                "weather": {
                    "temperature_c": weather.temperature_c,
                    "humidity_pct": weather.humidity_pct,
                    "rain_probability_pct": weather.rain_probability_pct,
                    "condition": weather.condition,
                    "source": weather.source,
                    "is_stale": weather.is_stale,
                },
                "vegetation": {
                    "ndvi": veg.ndvi,
                    "evi": veg.evi,
                    "trend_7d_pct": veg.trend_7d_pct,
                    "vegetation_health": veg.vegetation_health,
                    "source": veg.source,
                },
                "disease": {
                    "possible_disease": latest_disease.possible_disease,
                    "confidence": f"{int(latest_disease.confidence * 100)}%",
                    "severity": latest_disease.severity,
                } if latest_disease else None,
                "health": {
                    "score": round(health.farm_health_score, 1) if health.has_data else None,
                    "label": health.label,
                    "has_data": health.has_data,
                    "data_coverage": round(health.data_coverage, 2),
                    "missing_inputs": health.missing_inputs,
                    "climate_risk": health.climate_risk,
                    "water_stress": health.water_stress,
                    "soil_health": health.soil_health,
                    "disease_risk": health.disease_risk,
                    "factors": health.factors,
                },
            }

            ai_explanation, raw_provider_used = self.ai_service.explain(
                db,
                user_id=user_id,
                request_type="advisory",
                user_prompt=build_bhoomi_prompt(farm_data),
            )

        # 1. Freshness evaluation for each domain
        w_freshness, w_age = DataQualityService.evaluate_freshness("weather", weather.observed_at)
        s_freshness, s_age = DataQualityService.evaluate_freshness("soil", soil.sample_date)
        v_freshness, v_age = DataQualityService.evaluate_freshness("satellite", veg.observation_date)
        wat_freshness, wat_age = DataQualityService.evaluate_freshness("water", water.observed_at)

        # 2. Build and persist immutable FarmDataSnapshot
        snapshot_id = uuid.uuid4()
        snapshot_version = f"snap-{snapshot_id.hex[:8]}"
        missing = []
        if weather.temperature_c is None:
            missing.append("weather.temperature")
        if soil.ph is None:
            missing.append("soil.ph")
        if veg.ndvi is None:
            missing.append("vegetation.ndvi")
        if not farm.current_crop:
            missing.append("crop.name")

        db_snapshot = FarmDataSnapshot(
            id=snapshot_id,
            farm_id=farm.id,
            snapshot_version=snapshot_version,
            weather_snapshot={
                "temperature_c": weather.temperature_c,
                "humidity_pct": weather.humidity_pct,
                "rainfall_mm": weather.rainfall_mm,
                "wind_speed_kmh": weather.wind_speed_kmh,
                "condition": weather.condition,
                "source": weather.source,
                "freshness": w_freshness.value,
                "observed_at": weather.observed_at.isoformat() if weather.observed_at else None,
            },
            soil_snapshot={
                "ph": soil.ph,
                "nitrogen": soil.nitrogen,
                "phosphorus": soil.phosphorus,
                "potassium": soil.potassium,
                "organic_carbon": soil.organic_carbon,
                "source": soil.source,
                "freshness": s_freshness.value,
                "sample_date": soil.sample_date.isoformat() if soil.sample_date else None,
            },
            satellite_snapshot={
                "ndvi": veg.ndvi,
                "evi": veg.evi,
                "vegetation_health": veg.vegetation_health,
                "source": veg.source,
                "freshness": v_freshness.value,
                "observation_date": veg.observation_date.isoformat() if veg.observation_date else None,
            },
            water_snapshot={
                "rainfall_mm": water.rainfall_mm,
                "soil_moisture_pct": water.soil_moisture_pct,
                "moisture_source_type": water.moisture_source_type,
                "source": water.source,
                "freshness": wat_freshness.value,
            },
            crop_snapshot={
                "crop": farm.current_crop,
                "crop_stage": farm.crop_stage,
                "area_hectares": farm.area_hectares,
                "source": "farmer_provided",
            },
            missing_fields=missing,
            source_attributions={
                "weather": weather.source,
                "soil": soil.source,
                "satellite": veg.source,
                "water": water.source,
            },
        )
        db.add(db_snapshot)
        db.commit()

        # Report the attribution honestly.
        if not ai_explanation:
            ai_source = None
        elif raw_provider_used and raw_provider_used.startswith("nvidia"):
            ai_source = "BHOOMI Farm Intelligence AI"
        else:
            ai_source = raw_provider_used

        data_freshness = {
            "weather": {
                "status": w_freshness.value,
                "data_age_hours": w_age,
                "source": weather.source,
                "observed_at": weather.observed_at.isoformat() if weather.observed_at else None,
            },
            "soil": {
                "status": s_freshness.value,
                "data_age_hours": s_age,
                "source": soil.source,
                "observed_at": soil.sample_date.isoformat() if soil.sample_date else None,
            },
            "satellite": {
                "status": v_freshness.value,
                "data_age_hours": v_age,
                "source": veg.source,
                "observed_at": veg.observation_date.isoformat() if veg.observation_date else None,
            },
            "crop": {
                "status": "RECENT",
                "source": "farmer_provided",
                "updated_at": farm.updated_at.isoformat() if farm.updated_at else None,
            },
            "water": {
                "status": wat_freshness.value,
                "moisture_source_type": water.moisture_source_type,
                "source": water.source,
                "observed_at": water.observed_at.isoformat() if water.observed_at else None,
            },
            "disease": {
                "status": "RECENT" if latest_disease else "NOT_ASSESSED",
                "possible_disease": latest_disease.possible_disease if latest_disease else None,
                "confidence": f"{int(latest_disease.confidence * 100)}%" if latest_disease else None,
                "observed_at": latest_disease.created_at.isoformat() if latest_disease else None,
            },
        }

        sources = [
            {"domain": "Weather", "provider": weather.source.upper(), "type": "Meteorological Telemetry", "status": w_freshness.value},
            {"domain": "Soil", "provider": soil.source.replace("_", " ").title(), "type": "Laboratory / Profile", "status": s_freshness.value},
            {"domain": "Satellite", "provider": veg.source.replace("_", " ").title(), "type": "Earth Observation", "status": v_freshness.value},
            {"domain": "Water", "provider": water.source.replace("_", " ").title(), "type": water.moisture_source_type.title(), "status": wat_freshness.value},
        ]

        audit_metadata = {
            "intelligence_id": str(snapshot_id),
            "farm_id": str(farm.id),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "prompt_version": "v2.0",
            "engine_version": "bhoomi-data-fabric-v2.0",
            "data_snapshot_version": snapshot_version,
            "model": raw_provider_used or "deterministic-rules",
            "source_observations": {
                "weather": weather.source,
                "soil": soil.source,
                "satellite": veg.source,
            },
        }

        return {
            "farm": {
                "id": str(farm.id),
                "name": farm.name,
                "crop": farm.current_crop,
                "crop_stage": farm.crop_stage,
                "area_hectares": farm.area_hectares,
                "state": farm.state,
                "district": farm.district,
            },
            "health": {
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
            },
            "weather": {
                "temperature_c": weather.temperature_c,
                "humidity_pct": weather.humidity_pct,
                "rain_probability_pct": weather.rain_probability_pct,
                "condition": weather.condition,
                "source": weather.source,
                "is_stale": weather.is_stale,
                "observed_at": weather.observed_at.isoformat() if weather.observed_at else None,
                "freshness": w_freshness.value,
            },
            "soil": {
                "ph": soil.ph,
                "organic_carbon": soil.organic_carbon,
                "nitrogen": soil.nitrogen,
                "phosphorus": soil.phosphorus,
                "potassium": soil.potassium,
                "moisture": soil.moisture,
                "sample_date": soil.sample_date.isoformat() if soil.sample_date else None,
                "source": soil.source,
                "freshness": s_freshness.value,
            },
            "vegetation": {
                "ndvi": veg.ndvi,
                "evi": veg.evi,
                "trend_7d_pct": veg.trend_7d_pct,
                "vegetation_health": veg.vegetation_health,
                "observation_date": veg.observation_date.isoformat() if veg.observation_date else None,
                "source": veg.source,
                "is_dev_dataset": veg.is_dev_dataset,
                "freshness": v_freshness.value,
            },
            "water": {
                "rainfall_mm": water.rainfall_mm,
                "soil_moisture_pct": water.soil_moisture_pct,
                "moisture_source_type": water.moisture_source_type,
                "irrigation_applied_mm": water.irrigation_applied_mm,
                "drought_index": water.drought_index,
                "source": water.source,
                "freshness": wat_freshness.value,
                "observed_at": water.observed_at.isoformat() if water.observed_at else None,
                "has_data": water.has_data,
            },
            "advisories": [
                {
                    "id": str(a.id),
                    "type": a.type.value,
                    "severity": a.severity.value,
                    "title": a.title,
                    "summary": a.summary,
                    "actions": a.actions,
                    "evidence": a.evidence,
                    "confidence": a.confidence,
                }
                for a in advisories
            ],
            "bhoomi_report": ai_explanation,
            "ai_interpretation": ai_explanation,
            "ai_provider_used": ai_source,
            "ai_is_model_generated": bool(raw_provider_used and raw_provider_used.startswith("nvidia")),
            "data_freshness": data_freshness,
            "sources": sources,
            "audit_metadata": audit_metadata,
        }
