"""WaterStressService -- deterministic water-stress estimation."""
from app.services.agriculture.rules.thresholds import THRESHOLDS
from app.services.agriculture.schema import Factor, ServiceResult, SoilSnapshot, WeatherSnapshot


class WaterStressService:
    def evaluate(self, weather: WeatherSnapshot, soil: SoilSnapshot, irrigation_type: str | None) -> ServiceResult:
        factors: list[Factor] = []
        score = 70.0  # 100 = no stress, 0 = severe stress

        moisture = soil.moisture
        if moisture is not None:
            if moisture < THRESHOLDS.low_soil_moisture_pct:
                deficit = THRESHOLDS.low_soil_moisture_pct - moisture
                penalty = min(40.0, deficit * 2)
                score -= penalty
                factors.append(Factor("low_soil_moisture", impact=penalty / 100, detail=f"Soil moisture {moisture:.0f}% is below the {THRESHOLDS.low_soil_moisture_pct:.0f}% comfort threshold."))
            elif moisture > THRESHOLDS.high_soil_moisture_pct:
                factors.append(Factor("adequate_soil_moisture", impact=0.1, detail=f"Soil moisture {moisture:.0f}% is adequate."))
                score += 5
        else:
            factors.append(Factor("soil_moisture_unknown", impact=0.05, detail="No recent soil moisture reading available."))
            score -= 5

        rain_prob = weather.rain_probability_pct
        if rain_prob is not None:
            if rain_prob >= THRESHOLDS.high_rain_probability_pct:
                score += 10
                factors.append(Factor("rainfall_expected", impact=0.15, detail=f"Rain probability is {rain_prob:.0f}%, likely reducing near-term irrigation need."))
            elif rain_prob < 20 and (moisture is None or moisture < THRESHOLDS.low_soil_moisture_pct):
                score -= 10
                factors.append(Factor("low_rain_low_moisture", impact=0.2, detail="Low rainfall probability combined with low soil moisture."))

        if irrigation_type in (None, "rainfed"):
            score -= 8
            factors.append(Factor("rainfed_dependency", impact=0.12, detail="Farm relies on rainfed irrigation, increasing sensitivity to dry spells."))

        score = max(0.0, min(100.0, score))
        if score >= 70:
            severity = "low"
        elif score >= 50:
            severity = "moderate"
        elif score >= 30:
            severity = "high"
        else:
            severity = "critical"

        return ServiceResult(score=score, severity=severity, factors=factors, has_data=moisture is not None or rain_prob is not None)
