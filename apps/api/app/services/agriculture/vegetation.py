"""VegetationHealthService -- deterministic NDVI/EVI trend interpretation."""
from app.services.agriculture.rules.thresholds import THRESHOLDS
from app.services.agriculture.schema import Factor, ServiceResult, VegetationSnapshot


class VegetationHealthService:
    def evaluate(self, veg: VegetationSnapshot) -> ServiceResult:
        factors: list[Factor] = []
        score = 50.0

        if veg.ndvi is not None:
            if veg.ndvi >= THRESHOLDS.ndvi_good:
                score = 85.0
                factors.append(Factor("ndvi_healthy", impact=0.3, detail=f"NDVI {veg.ndvi:.2f} indicates healthy, dense vegetation."))
            elif veg.ndvi >= THRESHOLDS.ndvi_moderate:
                score = 60.0
                factors.append(Factor("ndvi_moderate", impact=0.2, detail=f"NDVI {veg.ndvi:.2f} indicates moderate vegetation vigor."))
            else:
                score = 30.0
                factors.append(Factor("ndvi_low", impact=0.35, detail=f"NDVI {veg.ndvi:.2f} is low for this crop stage."))
        else:
            factors.append(Factor("ndvi_unavailable", impact=0.1, detail="No recent satellite vegetation observation available."))
        if veg.trend_7d_pct is not None:
            if veg.trend_7d_pct <= THRESHOLDS.ndvi_decline_alert_pct:
                score -= 15
                factors.append(Factor("vegetation_stress_trend", impact=0.3, detail=f"Vegetation index declined {abs(veg.trend_7d_pct):.1f}% over the last 7 days."))
            elif veg.trend_7d_pct > 0:
                score += 5
                factors.append(Factor("vegetation_improving", impact=0.1, detail=f"Vegetation index improved {veg.trend_7d_pct:.1f}% over the last 7 days."))

        if veg.is_dev_dataset:
            factors.append(Factor("dev_dataset", impact=0.0, detail="Vegetation data is sourced from a seeded development dataset, not a live satellite feed."))

        score = max(0.0, min(100.0, score))
        if score >= 70:
            severity = "low"
        elif score >= 50:
            severity = "moderate"
        elif score >= 30:
            severity = "high"
        else:
            severity = "critical"

        return ServiceResult(score=score, severity=severity, factors=factors, has_data=veg.ndvi is not None)
