"""SoilHealthService -- deterministic soil-health scoring."""
from app.services.agriculture.rules.thresholds import THRESHOLDS
from app.services.agriculture.schema import Factor, ServiceResult, SoilSnapshot


class SoilHealthService:
    def evaluate(self, soil: SoilSnapshot) -> ServiceResult:
        factors: list[Factor] = []
        score = 60.0
        # Only pH and organic carbon currently drive the score, so only they
        # count as evidence that a score can be produced. Nutrients are
        # recorded as present but must not make an unscored result look
        # measured.
        scored_known = 0
        unscored_known = 0

        if soil.ph is not None:
            scored_known += 1
            if THRESHOLDS.ph_low <= soil.ph <= THRESHOLDS.ph_high:
                score += 10
                factors.append(Factor("ph_in_range", impact=0.15, detail=f"Soil pH {soil.ph:.1f} is within the favorable range."))
            else:
                score -= 15
                factors.append(Factor("ph_out_of_range", impact=0.25, detail=f"Soil pH {soil.ph:.1f} is outside the {THRESHOLDS.ph_low}-{THRESHOLDS.ph_high} favorable range."))

        if soil.organic_carbon is not None:
            scored_known += 1
            if soil.organic_carbon >= THRESHOLDS.organic_carbon_good_pct:
                score += 15
                factors.append(Factor("organic_carbon_good", impact=0.2, detail=f"Organic carbon {soil.organic_carbon:.2f}% supports long-term soil resilience."))
            elif soil.organic_carbon < THRESHOLDS.organic_carbon_low_pct:
                score -= 15
                factors.append(Factor("organic_carbon_low", impact=0.3, detail=f"Organic carbon {soil.organic_carbon:.2f}% is below the {THRESHOLDS.organic_carbon_low_pct}% target."))

        for nutrient, value in (("nitrogen", soil.nitrogen), ("phosphorus", soil.phosphorus), ("potassium", soil.potassium)):
            if value is not None:
                unscored_known += 1
                factors.append(
                    Factor(
                        f"{nutrient}_recorded",
                        impact=0.0,
                        detail=f"{nutrient.capitalize()} {value} is on record but is not yet used in the soil-health score.",
                    )
                )

        if scored_known == 0:
            if unscored_known:
                factors.append(
                    Factor(
                        "insufficient_soil_data",
                        impact=0.4,
                        detail=(
                            f"Only nutrient values ({unscored_known} recorded) are available; pH and organic "
                            "carbon are needed to score soil health."
                        ),
                    )
                )
            else:
                factors.append(Factor("no_soil_data", impact=0.4, detail="No soil profile has been recorded for this farm yet."))
            score = 40.0

        score = max(0.0, min(100.0, score))
        if score >= 70:
            severity = "low"  # low risk / good health
        elif score >= 50:
            severity = "moderate"
        elif score >= 30:
            severity = "high"
        else:
            severity = "critical"

        return ServiceResult(score=score, severity=severity, factors=factors, has_data=scored_known > 0)
