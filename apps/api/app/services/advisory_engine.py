"""
Advisory Engine -- the final stage of the data-fusion pipeline:

  weather + soil + satellite + crop + farm metadata + history
        -> normalization -> feature extraction -> risk engine (agriculture/*)
        -> ADVISORY ENGINE (this module)
        -> LLM EXPLANATION (app.services.ai_service)

Advisories are always generated from deterministic rules first; the LLM is
only used to *explain* already-computed, structured results in
plain language -- never to invent the underlying data.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.advisory import Advisory, AdvisoryType, ReviewStatus, Severity
from app.models.farm import Farm
from app.services.agriculture.farm_health import FarmHealthResult
from app.services.agriculture.regenerative import RegenerativeRecommendationService
from app.services.agriculture.rules.thresholds import THRESHOLDS
from app.services.agriculture.schema import FarmContext, SoilSnapshot, VegetationSnapshot, WeatherSnapshot

logger = get_logger("bhoomi.advisory_engine")

_SEVERITY_MAP = {"low": Severity.LOW, "moderate": Severity.MODERATE, "high": Severity.HIGH, "critical": Severity.CRITICAL}


def _evidence(weather: WeatherSnapshot, soil: SoilSnapshot, veg: VegetationSnapshot) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    items = []
    if weather.temperature_c is not None:
        items.append({"source": "weather", "value": f"{weather.temperature_c:.0f}°C, rain probability {weather.rain_probability_pct or 0:.0f}%", "timestamp": weather.observed_at.isoformat() if weather.observed_at else now})
    if soil.ph is not None:
        items.append({"source": "soil", "value": f"pH {soil.ph:.1f}, organic carbon {soil.organic_carbon or 0:.2f}%", "timestamp": now})
    if veg.ndvi is not None:
        items.append({"source": "vegetation", "value": f"NDVI {veg.ndvi:.2f}", "timestamp": now})
    return items


def generate_deterministic_advisories(
    db: Session,
    farm: Farm,
    farm_ctx: FarmContext,
    weather: WeatherSnapshot,
    soil: SoilSnapshot,
    veg: VegetationSnapshot,
    health: FarmHealthResult,
) -> list[Advisory]:
    """Rule-driven advisory generation (PRODUCT SPEC section 75)."""
    advisories: list[Advisory] = []
    evidence = _evidence(weather, soil, veg)

    # Irrigation delay rule
    if (weather.rain_probability_pct or 0) > THRESHOLDS.high_rain_probability_pct and (
        soil.moisture is None or soil.moisture > THRESHOLDS.low_soil_moisture_pct
    ):
        advisories.append(
            Advisory(
                farm_id=farm.id,
                type=AdvisoryType.IRRIGATION,
                severity=Severity.MODERATE,
                title="Delay irrigation for 1-2 days",
                summary=(
                    f"Rain is likely soon ({weather.rain_probability_pct:.0f}% probability), "
                    "so you can delay irrigation and avoid overwatering."
                ),
                actions=[{"title": "Delay irrigation by 1-2 days", "priority": "medium", "reason": "Elevated rainfall probability reduces near-term irrigation need."}],
                evidence=evidence,
                source_references=[{"source": "weather", "authority": "IMD or cached observation"}],
                confidence=0.72,
                generated_by="rule_engine",
                review_status=ReviewStatus.AUTO_APPROVED,
            )
        )
        advisories.append(
            Advisory(
                farm_id=farm.id,
                type=AdvisoryType.WEATHER,
                severity=Severity.LOW,
                title="Monitor drainage after rainfall",
                summary="Check field drainage paths so water does not pool around root zones after the expected rain.",
                actions=[{"title": "Inspect drainage channels", "priority": "low", "reason": "Prevent waterlogging after rainfall."}],
                evidence=evidence,
                source_references=[{"source": "weather", "authority": "IMD or cached observation"}],
                confidence=0.65,
                generated_by="rule_engine",
                review_status=ReviewStatus.AUTO_APPROVED,
            )
        )

    # Vegetation stress rule
    if veg.trend_7d_pct is not None and veg.trend_7d_pct <= THRESHOLDS.ndvi_decline_alert_pct:
        advisories.append(
            Advisory(
                farm_id=farm.id,
                type=AdvisoryType.CROP,
                severity=Severity.MODERATE,
                title="Vegetation stress has increased over the last 7 days",
                summary=(
                    f"Satellite vegetation index dropped {abs(veg.trend_7d_pct):.1f}% over the last week. "
                    "Inspect the lower leaves and check for early stress or pest signs."
                ),
                actions=[{"title": "Inspect lower leaves and canopy", "priority": "medium", "reason": "Declining vegetation index can indicate early stress, pest, or water issues."}],
                evidence=evidence,
                source_references=[{"source": "vegetation", "authority": "Satellite observation (see dataset label)"}],
                confidence=0.6,
                generated_by="rule_engine",
                review_status=ReviewStatus.AUTO_APPROVED,
            )
        )

    # Heat stress rule
    if weather.temperature_c is not None and weather.temperature_c >= THRESHOLDS.heat_stress_temp_c:
        advisories.append(
            Advisory(
                farm_id=farm.id,
                type=AdvisoryType.CLIMATE,
                severity=Severity.HIGH,
                title="Heat stress risk is elevated",
                summary=f"Temperature ({weather.temperature_c:.0f}°C) is high enough to stress most field crops. Consider light irrigation in the cooler hours.",
                actions=[{"title": "Irrigate during early morning or evening", "priority": "high", "reason": "Reduce heat stress and evapotranspiration losses."}],
                evidence=evidence,
                source_references=[{"source": "weather", "authority": "IMD or cached observation"}],
                confidence=0.68,
                generated_by="rule_engine",
                review_status=ReviewStatus.AUTO_APPROVED,
            )
        )

    # Regenerative recommendations
    regen_service = RegenerativeRecommendationService()
    for rec in regen_service.generate(farm_ctx.crop, farm_ctx.previous_crop, soil, weather, farm_ctx.irrigation_type):
        advisories.append(
            Advisory(
                farm_id=farm.id,
                type=AdvisoryType.REGENERATIVE,
                severity=Severity.LOW if rec.priority == "low" else (Severity.MODERATE if rec.priority == "medium" else Severity.HIGH),
                title=rec.title,
                summary=f"{rec.reason} Expected goal: {rec.expected_goal}",
                actions=[{"title": rec.title, "priority": rec.priority, "reason": rec.reason}],
                evidence=evidence,
                source_references=[{"source": "soil", "authority": "Farm soil profile"}],
                confidence=0.55,
                generated_by="rule_engine",
                review_status=ReviewStatus.AUTO_APPROVED,
            )
        )

    if not advisories:
        advisories.append(
            Advisory(
                farm_id=farm.id,
                type=AdvisoryType.CROP,
                severity=Severity.LOW,
                title="No urgent actions right now",
                summary="Current weather, soil, and vegetation indicators are within normal ranges for this farm.",
                actions=[{"title": "Continue routine monitoring", "priority": "low", "reason": "No risk thresholds were triggered."}],
                evidence=evidence,
                source_references=[{"source": "intelligence_engine", "authority": "BHOOMI deterministic rules"}],
                confidence=0.5,
                generated_by="rule_engine",
                review_status=ReviewStatus.AUTO_APPROVED,
            )
        )

    for adv in advisories:
        db.add(adv)
    db.commit()
    for adv in advisories:
        db.refresh(adv)
    return advisories
