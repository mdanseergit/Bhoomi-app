"""Unit tests for the deterministic agriculture intelligence engine.
No database or network access required."""
from datetime import date, datetime, timezone

from app.services.agriculture.climate import ClimateRiskService
from app.services.agriculture.crop_suitability import CropSuitabilityService
from app.services.agriculture.regenerative import RegenerativeRecommendationService
from app.services.agriculture.schema import SoilSnapshot, VegetationSnapshot, WeatherSnapshot
from app.services.agriculture.soil_health import SoilHealthService
from app.services.agriculture.vegetation import VegetationHealthService
from app.services.agriculture.water import WaterStressService


def _weather(**overrides) -> WeatherSnapshot:
    base = dict(
        temperature_c=30.0, humidity_pct=60.0, rainfall_mm=2.0, rain_probability_pct=30.0,
        wind_speed_kmh=10.0, condition="Clear", warning_level="none", source="test", observed_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return WeatherSnapshot(**base)


def _soil(**overrides) -> SoilSnapshot:
    base = dict(ph=6.5, nitrogen=150.0, phosphorus=20.0, potassium=120.0, organic_carbon=0.7, moisture=30.0, source="test", sample_date=date.today())
    base.update(overrides)
    return SoilSnapshot(**base)


def _veg(**overrides) -> VegetationSnapshot:
    base = dict(ndvi=0.65, evi=0.5, trend_7d_pct=1.0, vegetation_health="good", source="test", observation_date=date.today(), is_dev_dataset=True)
    base.update(overrides)
    return VegetationSnapshot(**base)


class TestWaterStressService:
    def test_low_moisture_increases_stress(self):
        svc = WaterStressService()
        healthy = svc.evaluate(_weather(), _soil(moisture=40), "drip")
        dry = svc.evaluate(_weather(rain_probability_pct=10), _soil(moisture=8), "rainfed")
        assert dry.score < healthy.score
        assert dry.severity in ("high", "critical", "moderate")

    def test_rain_expected_reduces_stress(self):
        svc = WaterStressService()
        no_rain = svc.evaluate(_weather(rain_probability_pct=10), _soil(moisture=25), "drip")
        with_rain = svc.evaluate(_weather(rain_probability_pct=80), _soil(moisture=25), "drip")
        assert with_rain.score >= no_rain.score


class TestClimateRiskService:
    def test_heat_stress_triggers_risk(self):
        svc = ClimateRiskService()
        normal = svc.evaluate(_weather(temperature_c=28))
        hot = svc.evaluate(_weather(temperature_c=41))
        assert hot.score < normal.score
        assert any(f.name == "heat_stress" for f in hot.factors)

    def test_active_warning_reduces_score(self):
        svc = ClimateRiskService()
        clear = svc.evaluate(_weather(warning_level="none"))
        warned = svc.evaluate(_weather(warning_level="orange"))
        assert warned.score < clear.score


class TestVegetationHealthService:
    def test_high_ndvi_is_healthy(self):
        svc = VegetationHealthService()
        result = svc.evaluate(_veg(ndvi=0.75))
        assert result.severity == "low"

    def test_declining_trend_flags_stress(self):
        svc = VegetationHealthService()
        result = svc.evaluate(_veg(ndvi=0.45, trend_7d_pct=-15))
        assert any(f.name == "vegetation_stress_trend" for f in result.factors)


class TestSoilHealthService:
    def test_low_organic_carbon_penalized(self):
        svc = SoilHealthService()
        good = svc.evaluate(_soil(organic_carbon=0.9))
        poor = svc.evaluate(_soil(organic_carbon=0.3))
        assert poor.score < good.score

    def test_missing_data_is_flagged(self):
        svc = SoilHealthService()
        empty = SoilSnapshot(None, None, None, None, None, None, source="unavailable", sample_date=None)
        result = svc.evaluate(empty)
        assert any(f.name == "no_soil_data" for f in result.factors)

    def test_nutrients_alone_do_not_count_as_scorable_data(self):
        """N/P/K are recorded but not scored, so they must not produce a
        number that looks measured."""
        svc = SoilHealthService()
        nutrients_only = svc.evaluate(
            SoilSnapshot(None, 150.0, 20.0, 120.0, None, 30.0, source="test", sample_date=date.today())
        )
        assert nutrients_only.has_data is False
        assert any(f.name == "insufficient_soil_data" for f in nutrients_only.factors)
        assert any(f.name == "nitrogen_recorded" for f in nutrients_only.factors)

    def test_ph_or_organic_carbon_is_scorable(self):
        svc = SoilHealthService()
        assert svc.evaluate(_soil(ph=6.5, organic_carbon=None)).has_data is True
        assert svc.evaluate(_soil(ph=None, organic_carbon=0.7)).has_data is True


class TestClimateDataAdequacy:
    def test_unscored_fields_alone_do_not_count_as_data(self):
        """Humidity/wind/rainfall are recorded but temperature, rainfall
        probability and warnings are what the score actually uses."""
        svc = ClimateRiskService()
        result = svc.evaluate(
            _weather(temperature_c=None, rain_probability_pct=None, warning_level="none")
        )
        assert result.has_data is False
        assert any(f.name == "weather_unavailable" for f in result.factors)

    def test_scored_fields_count_as_data(self):
        svc = ClimateRiskService()
        assert svc.evaluate(_weather(rain_probability_pct=None, warning_level="none")).has_data is True
        assert svc.evaluate(_weather(temperature_c=None, warning_level="none")).has_data is True


class TestCropSuitabilityService:
    def test_repeated_crop_penalized(self):
        svc = CropSuitabilityService()
        rotated = svc.evaluate("rice", "groundnut", _soil())
        repeated = svc.evaluate("rice", "rice", _soil())
        assert repeated.score < rotated.score


class TestRegenerativeRecommendationService:
    def test_low_organic_carbon_triggers_recommendation(self):
        svc = RegenerativeRecommendationService()
        recs = svc.generate("rice", "rice", _soil(organic_carbon=0.3), _weather(), "flood")
        titles = " ".join(r.title for r in recs)
        assert "rotation" in titles.lower() or "soil-building" in titles.lower()

    def test_never_recommends_chemical_dosage(self):
        svc = RegenerativeRecommendationService()
        recs = svc.generate("cotton", "cotton", _soil(ph=4.0), _weather(), "flood")
        combined = " ".join(r.reason + r.title for r in recs).lower()
        assert "ml/l" not in combined and "kg/acre" not in combined and "mix " not in combined
