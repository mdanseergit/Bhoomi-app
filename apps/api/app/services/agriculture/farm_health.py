"""
FarmHealthService -- combines component services into the explainable
"BHOOMI Intelligence Score".

Weights (see PRODUCT SPEC section 17):
    Vegetation      30%
    Soil            25%
    Water           20%
    Weather/Climate 15%
    Crop condition  10%

This score is a BHOOMI-internal composite index, not an official
agricultural standard.
"""
from dataclasses import dataclass

from app.services.agriculture.climate import ClimateRiskService
from app.services.agriculture.crop_suitability import CropSuitabilityService
from app.services.agriculture.schema import (
    Factor,
    FarmContext,
    SoilSnapshot,
    VegetationSnapshot,
    WeatherSnapshot,
)
from app.services.agriculture.soil_health import SoilHealthService
from app.services.agriculture.vegetation import VegetationHealthService
from app.services.agriculture.water import WaterStressService

WEIGHTS = {
    "vegetation": 0.30,
    "soil": 0.25,
    "water": 0.20,
    "climate": 0.15,
    "crop": 0.10,
}


@dataclass
class FarmHealthResult:
    # None when no component had real observations. Callers must render
    # "Not enough data" rather than a number in that case.
    farm_health_score: float | None
    climate_risk: str
    water_stress: str
    disease_risk: str
    vegetation_stress: str
    soil_health: str
    breakdown: dict
    factors: list[dict]
    label: str = "BHOOMI Intelligence Score"
    # Fraction of the total weight that came from real observations (0..1).
    data_coverage: float = 0.0
    missing_inputs: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.missing_inputs is None:
            self.missing_inputs = []

    @property
    def has_data(self) -> bool:
        return self.farm_health_score is not None

    def to_json(self) -> dict:
        return {
            "score": self.farm_health_score,
            "label": self.label,
            "has_data": self.has_data,
            "data_coverage": round(self.data_coverage, 2),
            "missing_inputs": list(self.missing_inputs),
            "climate_risk": self.climate_risk,
            "water_stress": self.water_stress,
            "disease_risk": self.disease_risk,
            "vegetation_stress": self.vegetation_stress,
            "soil_health": self.soil_health,
            "breakdown": self.breakdown,
            "factors": self.factors,
        }


class FarmHealthService:
    def __init__(self) -> None:
        self.climate = ClimateRiskService()
        self.water = WaterStressService()
        self.vegetation = VegetationHealthService()
        self.soil = SoilHealthService()
        self.crop = CropSuitabilityService()

    def compute(
        self,
        farm: FarmContext,
        weather: WeatherSnapshot,
        soil: SoilSnapshot,
        veg: VegetationSnapshot,
        disease_risk_hint: str = "unknown",
    ) -> FarmHealthResult:
        climate_res = self.climate.evaluate(weather)
        water_res = self.water.evaluate(weather, soil, farm.irrigation_type)
        veg_res = self.vegetation.evaluate(veg)
        soil_res = self.soil.evaluate(soil)
        crop_res = self.crop.evaluate(farm.crop, farm.previous_crop, soil)

        components = (
            ("vegetation", veg_res, WEIGHTS["vegetation"]),
            ("soil", soil_res, WEIGHTS["soil"]),
            ("water", water_res, WEIGHTS["water"]),
            ("climate", climate_res, WEIGHTS["climate"]),
            ("crop", crop_res, WEIGHTS["crop"]),
        )

        # Only components backed by real observations may influence the score.
        # Missing components are excluded and their weight is NOT silently
        # redistributed as if the data existed.
        scored = [(name, res, weight) for name, res, weight in components if res.has_data]
        missing_inputs = [name for name, res, _ in components if not res.has_data]

        if not scored:
            return FarmHealthResult(
                farm_health_score=None,
                climate_risk=climate_res.severity,
                water_stress=water_res.severity,
                disease_risk=disease_risk_hint,
                vegetation_stress=veg_res.severity,
                soil_health=soil_res.severity,
                breakdown={
                    name: {"weight": weight, "score": None, "has_data": res.has_data}
                    for name, res, weight in components
                },
                factors=[
                    {
                        "name": "insufficient_data",
                        "impact": 0.0,
                        "detail": "No measured weather, soil, vegetation or crop-history data is available for this farm yet, so no score can be calculated.",
                    }
                ],
                data_coverage=0.0,
                missing_inputs=missing_inputs,
            )

        total_weight = sum(weight for _, _, weight in scored)
        weighted = sum(res.score * weight for _, res, weight in scored)

        # Renormalise within observed components so the reported score is not
        # depressed merely because one feed is offline. `data_coverage` tells
        # the UI how much of the intended basis was actually available.
        score = weighted / total_weight
        coverage = total_weight / sum(WEIGHTS.values())

        all_factors: list[Factor] = []
        for _, res, weight in scored:
            scale = (weight / total_weight) * (total_weight / sum(WEIGHTS.values()))
            for f in res.factors:
                all_factors.append(
                    Factor(name=f.name, impact=round(f.impact * scale, 3), detail=f.detail)
                )

        for name in missing_inputs:
            all_factors.append(
                Factor(
                    name=f"{name}_unavailable",
                    impact=0.0,
                    detail=f"No {name} data available; this component was excluded from the score.",
                )
            )

        all_factors.sort(key=lambda f: f.impact, reverse=True)

        def invert_to_risk(score: float) -> str:
            if score >= 70:
                return "low"
            if score >= 50:
                return "moderate"
            if score >= 30:
                return "high"
            return "critical"

        return FarmHealthResult(
            farm_health_score=round(score, 1),
            climate_risk=invert_to_risk(climate_res.score) if climate_res.has_data else "unknown",
            water_stress=invert_to_risk(water_res.score) if water_res.has_data else "unknown",
            disease_risk=disease_risk_hint,
            vegetation_stress=invert_to_risk(veg_res.score) if veg_res.has_data else "unknown",
            soil_health=soil_res.severity if soil_res.has_data else "unknown",
            breakdown={
                name: {"weight": weight, "score": res.score if res.has_data else None, "has_data": res.has_data}
                for name, res, weight in components
            },
            factors=[{"name": f.name, "impact": f.impact, "detail": f.detail} for f in all_factors],
            data_coverage=coverage,
            missing_inputs=missing_inputs,
        )
