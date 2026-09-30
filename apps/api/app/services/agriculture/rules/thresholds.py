"""
Configurable agronomic thresholds used by the deterministic rule engine.

These are development-stage heuristics inspired by widely published general
agronomy guidance (not official standards for any specific state) and are
intentionally centralized here (rather than scattered through UI code) so
they can be reviewed, versioned, and tuned by an agronomist without touching
application logic.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Thresholds:
    # Rainfall / irrigation
    high_rain_probability_pct: float = 60.0
    high_soil_moisture_pct: float = 35.0
    low_soil_moisture_pct: float = 20.0

    # Vegetation / NDVI
    ndvi_good: float = 0.6
    ndvi_moderate: float = 0.4
    ndvi_decline_alert_pct: float = -8.0  # 7-day relative decline

    # Temperature stress
    heat_stress_temp_c: float = 38.0
    cold_stress_temp_c: float = 8.0

    # Soil health
    organic_carbon_low_pct: float = 0.5
    organic_carbon_good_pct: float = 0.75
    ph_low: float = 5.5
    ph_high: float = 8.0

    # Disease
    disease_high_confidence: float = 0.75
    disease_moderate_confidence: float = 0.5


THRESHOLDS = Thresholds()
