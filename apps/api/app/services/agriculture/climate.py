"""ClimateRiskService -- deterministic climate/weather risk estimation."""
from app.services.agriculture.rules.thresholds import THRESHOLDS
from app.services.agriculture.schema import Factor, ServiceResult, WeatherSnapshot


class ClimateRiskService:
    def evaluate(self, weather: WeatherSnapshot) -> ServiceResult:
        factors: list[Factor] = []
        score = 80.0  # 100 = minimal risk
        # Only temperature, rainfall probability and warnings move the score.
        # Humidity, wind and other recorded fields are not scored, so they
        # must not make an otherwise unscored result look measured.
        scored_known = 0

        temp = weather.temperature_c
        if temp is not None:
            scored_known += 1
            if temp >= THRESHOLDS.heat_stress_temp_c:
                score -= 25
                factors.append(Factor("heat_stress", impact=0.3, detail=f"Temperature {temp:.0f}°C exceeds the heat-stress threshold of {THRESHOLDS.heat_stress_temp_c:.0f}°C."))
            elif temp <= THRESHOLDS.cold_stress_temp_c:
                score -= 20
                factors.append(Factor("cold_stress", impact=0.25, detail=f"Temperature {temp:.0f}°C is unusually low for the crop cycle."))
        else:
            factors.append(Factor("weather_unavailable", impact=0.1, detail="No current weather observation is available for this farm."))

        rain_prob = weather.rain_probability_pct
        if rain_prob is not None:
            scored_known += 1
            if rain_prob >= THRESHOLDS.high_rain_probability_pct:
                score -= 12
                factors.append(Factor("rainfall_risk", impact=0.3, detail=f"Rainfall probability is elevated at {rain_prob:.0f}%, increasing waterlogging/drainage risk."))

        if weather.warning_level and weather.warning_level.lower() not in ("none", "nil", ""):
            scored_known += 1
            score -= 20
            factors.append(Factor("weather_warning", impact=0.35, detail=f"Active weather warning: {weather.warning_level}."))

        if weather.is_stale:
            factors.append(Factor("stale_weather_data", impact=0.05, detail="Weather data is cached and may not reflect current conditions."))

        score = max(0.0, min(100.0, score))
        if score >= 75:
            severity = "low"
        elif score >= 55:
            severity = "moderate"
        elif score >= 35:
            severity = "high"
        else:
            severity = "critical"

        return ServiceResult(score=score, severity=severity, factors=factors, has_data=scored_known > 0)
