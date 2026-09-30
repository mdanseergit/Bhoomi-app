"""RegenerativeRecommendationService -- long-term soil/water resilience advice.

Generates structured recommendations (never dosages/chemical instructions).
"""
from dataclasses import dataclass

from app.services.agriculture.rules.thresholds import THRESHOLDS
from app.services.agriculture.schema import SoilSnapshot, WeatherSnapshot


@dataclass
class Recommendation:
    title: str
    reason: str
    expected_goal: str
    priority: str  # low | medium | high


class RegenerativeRecommendationService:
    def generate(
        self,
        crop: str | None,
        previous_crop: str | None,
        soil: SoilSnapshot,
        weather: WeatherSnapshot,
        irrigation_type: str | None,
    ) -> list[Recommendation]:
        recs: list[Recommendation] = []

        if soil.organic_carbon is not None and soil.organic_carbon < THRESHOLDS.organic_carbon_low_pct:
            recs.append(
                Recommendation(
                    title="Consider a crop rotation and soil-building strategy after this cycle.",
                    reason="Organic carbon is below the desired farm target and continuous crop repetition increases nutrient pressure.",
                    expected_goal="Improve soil resilience and reduce long-term input dependency.",
                    priority="medium",
                )
            )

        if crop and previous_crop and crop.lower() == previous_crop.lower():
            recs.append(
                Recommendation(
                    title="Introduce a different crop family in the next cycle.",
                    reason=f"{crop.title()} has been repeated across consecutive cycles, which can build up crop-specific pests and deplete targeted nutrients.",
                    expected_goal="Break pest/disease cycles and diversify nutrient demand on the soil.",
                    priority="medium",
                )
            )

        if irrigation_type in (None, "flood"):
            recs.append(
                Recommendation(
                    title="Evaluate a more water-efficient irrigation method (e.g. drip/sprinkler) where feasible.",
                    reason="Flood or unspecified irrigation is typically less water-efficient than micro-irrigation methods.",
                    expected_goal="Reduce water use while maintaining yield potential and improving climate resilience.",
                    priority="low",
                )
            )

        if soil.ph is not None and not (THRESHOLDS.ph_low <= soil.ph <= THRESHOLDS.ph_high):
            recs.append(
                Recommendation(
                    title="Get soil pH re-verified by a soil testing lab or agricultural officer.",
                    reason=f"Recorded soil pH ({soil.ph:.1f}) falls outside the generally favorable range for most field crops.",
                    expected_goal="Confirm whether a targeted, locally-appropriate soil amendment is warranted.",
                    priority="high",
                )
            )

        if not recs:
            recs.append(
                Recommendation(
                    title="Continue current practices and monitor soil organic matter annually.",
                    reason="No major regenerative risk indicators were detected from the available farm data.",
                    expected_goal="Sustain current soil health and climate resilience.",
                    priority="low",
                )
            )

        return recs
