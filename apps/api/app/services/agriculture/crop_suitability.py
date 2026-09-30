"""CropSuitabilityService -- deterministic crop/rotation suitability check."""
from app.services.agriculture.schema import Factor, ServiceResult, SoilSnapshot

# Simplified, clearly-labeled development reference data: crop family
# groupings used only to flag repeated-family rotation risk. This is not an
# authoritative agronomic dataset.
CROP_FAMILY = {
    "rice": "cereal",
    "wheat": "cereal",
    "ragi": "millet",
    "maize": "cereal",
    "groundnut": "legume",
    "pulses": "legume",
    "cotton": "fiber",
    "sugarcane": "cash",
    "banana": "cash",
    "tomato": "solanaceous",
    "chilli": "solanaceous",
}


class CropSuitabilityService:
    def evaluate(self, crop: str | None, previous_crop: str | None, soil: SoilSnapshot) -> ServiceResult:
        factors: list[Factor] = []
        score = 75.0

        if crop and previous_crop:
            crop_family = CROP_FAMILY.get(crop.lower())
            prev_family = CROP_FAMILY.get(previous_crop.lower())
            if crop.lower() == previous_crop.lower():
                score -= 20
                factors.append(Factor("same_crop_repeat", impact=0.3, detail=f"{crop.title()} was also grown in the previous cycle, raising pest/nutrient-depletion pressure."))
            elif crop_family and prev_family and crop_family == prev_family:
                score -= 10
                factors.append(Factor("same_family_rotation", impact=0.15, detail=f"{crop.title()} and {previous_crop.title()} belong to the same crop family."))
            else:
                score += 10
                factors.append(Factor("healthy_rotation", impact=0.15, detail=f"Rotating from {previous_crop.title()} to {crop.title()} supports nutrient balance."))

        if soil.ph is not None and crop:
            # Rice tolerates a wider pH band than most row crops (dev heuristic only).
            if crop.lower() == "rice" and soil.ph < 5.0:
                score -= 10
                factors.append(Factor("ph_marginal_for_crop", impact=0.2, detail="Soil pH is on the acidic edge of the suitable range for rice."))

        score = max(0.0, min(100.0, score))
        if score >= 70:
            severity = "low"
        elif score >= 50:
            severity = "moderate"
        elif score >= 30:
            severity = "high"
        else:
            severity = "critical"

        return ServiceResult(
            score=score,
            severity=severity,
            factors=factors,
            has_data=bool(crop) and bool(previous_crop),
        )
