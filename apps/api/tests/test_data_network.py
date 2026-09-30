"""
Integration & unit tests for BHOOMI Data Network:
- Universal Provider Abstraction & Adapters
- Data Normalization & Unit Conversions
- Quality & Freshness Evaluation
- Multi-tier Provider Resolver & Hierarchy
- Farm Data Endpoints (data-status, sources, water, timeline)
- Admin Provider Management (status, test, enable, disable)
"""
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from app.integrations.data_network.base import (
    FreshnessState,
    QualityStatus,
    CanonicalWeather,
    CanonicalSoil,
    CanonicalSatellite,
)
from app.integrations.data_network.normalizer import UnitNormalizer
from app.integrations.data_network.quality_service import DataQualityService
from app.integrations.data_network.resolver import DataProviderResolver
from app.integrations.data_network.imd_weather import IMDWeatherProvider
from app.integrations.data_network.soil_health_card import SoilHealthCardProvider
from app.integrations.data_network.isro_bhoonidhi import ISROBhoonidhiProvider
from app.integrations.data_network.copernicus_satellite import CopernicusSatelliteProvider
from app.integrations.data_network.nasa_power import NASAPowerProvider
from app.integrations.data_network.faostat import FAOSTATProvider
from app.models.user import Role


# ---------------------------------------------------------------------------
# Unit Normalization Tests
# ---------------------------------------------------------------------------

def test_unit_normalization_temperature():
    # Celsius (no conversion)
    val_c, rec_c = UnitNormalizer.normalize_temperature(25.0, "C")
    assert val_c == 25.0
    assert rec_c.normalized_unit == "°C"

    # Fahrenheit to Celsius
    val_f, rec_f = UnitNormalizer.normalize_temperature(77.0, "F")
    assert round(val_f, 1) == 25.0
    assert rec_f.conversion_method == "(F - 32) * 5/9"

    # Kelvin to Celsius
    val_k, rec_k = UnitNormalizer.normalize_temperature(300.15, "K")
    assert round(val_k, 1) == 27.0


def test_unit_normalization_rainfall_and_wind():
    # Inches to mm
    rain_mm, rec_rain = UnitNormalizer.normalize_rainfall(1.0, "inch")
    assert round(rain_mm, 2) == 25.4
    assert rec_rain.normalized_unit == "mm"

    # km/h to m/s
    ms, kmh, rec_wind = UnitNormalizer.normalize_wind_speed(36.0, "km/h")
    assert round(ms, 2) == 10.0
    assert rec_wind.normalized_unit == "m/s"

    # mph to m/s
    ms_mph, _, _ = UnitNormalizer.normalize_wind_speed(10.0, "mph")
    assert round(ms_mph, 2) == 4.47


def test_unit_normalization_area_and_coords():
    # Acres to hectares
    area_ha, rec_area = UnitNormalizer.normalize_area(2.47105, "acres")
    assert round(area_ha, 1) == 1.0
    assert rec_area.normalized_unit == "ha"

    # Coordinates
    lat, lon = UnitNormalizer.normalize_coordinates(11.6, 78.1)
    assert lat == 11.6 and lon == 78.1

    with pytest.raises(ValueError):
        UnitNormalizer.normalize_coordinates(95.0, 78.1)


# ---------------------------------------------------------------------------
# Data Quality & Freshness Tests
# ---------------------------------------------------------------------------

def test_freshness_evaluation_by_natural_domain_frequency():
    now = datetime.now(timezone.utc)

    # Weather: 20 minutes old is LIVE; 4 hours old is RECENT; 30 hours old is OUTDATED
    f_live_weather, _ = DataQualityService.evaluate_freshness("weather", now - timedelta(minutes=20))
    assert f_live_weather == FreshnessState.LIVE

    f_recent_weather, _ = DataQualityService.evaluate_freshness("weather", now - timedelta(hours=4))
    assert f_recent_weather == FreshnessState.RECENT

    f_stale_weather, _ = DataQualityService.evaluate_freshness("weather", now - timedelta(hours=18))
    assert f_stale_weather == FreshnessState.STALE

    # Satellite: 2 days old is RECENT (satellites pass every few days)
    f_recent_sat, _ = DataQualityService.evaluate_freshness("satellite", now - timedelta(days=2))
    assert f_recent_sat == FreshnessState.RECENT

    # Soil: 45 days old is RECENT (lab tests valid for multiple months)
    f_recent_soil, _ = DataQualityService.evaluate_freshness("soil", now - timedelta(days=45))
    assert f_recent_soil == FreshnessState.RECENT


def test_physical_range_validation():
    # Valid weather
    valid_cw = CanonicalWeather(temperature_c=31.5, humidity_pct=65.0, wind_speed_ms=4.2)
    st_valid, issues = DataQualityService.validate_weather(valid_cw)
    assert st_valid == QualityStatus.GOOD
    assert not issues

    # Impossible temperature (95°C) and humidity (150%)
    invalid_cw = CanonicalWeather(temperature_c=95.0, humidity_pct=150.0)
    st_inv, issues_inv = DataQualityService.validate_weather(invalid_cw)
    assert st_inv == QualityStatus.INVALID
    assert len(issues_inv) == 2

    # Valid soil
    valid_soil = CanonicalSoil(ph=6.8, electrical_conductivity_ds_m=0.45, organic_carbon_pct=0.55)
    st_soil, _ = DataQualityService.validate_soil(valid_soil)
    assert st_soil == QualityStatus.GOOD

    # Impossible soil pH (16.0)
    invalid_soil = CanonicalSoil(ph=16.0)
    st_bad_soil, _ = DataQualityService.validate_soil(invalid_soil)
    assert st_bad_soil == QualityStatus.INVALID


# ---------------------------------------------------------------------------
# Provider Abstraction & Capabilities Tests
# ---------------------------------------------------------------------------

def test_provider_declarations_and_capabilities():
    imd = IMDWeatherProvider()
    assert imd.country_scope == "India"
    assert "temperature" in imd.discover_capabilities()["parameters"]
    health = imd.health_check()
    assert "status" in health

    shc = SoilHealthCardProvider()
    assert shc.country_scope == "India"
    caps = shc.discover_capabilities()
    assert "ph" in caps["parameters"]
    assert "nitrogen" in caps["parameters"]
    assert "zinc" in caps["parameters"]

    bhoonidhi = ISROBhoonidhiProvider()
    assert bhoonidhi.country_scope == "India"
    assert "ndvi" in bhoonidhi.discover_capabilities()["parameters"]

    copernicus = CopernicusSatelliteProvider()
    assert copernicus.country_scope == "Global"
    assert "ndvi" in copernicus.discover_capabilities()["parameters"]

    nasa = NASAPowerProvider()
    assert nasa.country_scope == "Global"
    assert "temperature" in nasa.discover_capabilities()["parameters"]

    faostat = FAOSTATProvider()
    assert faostat.country_scope == "Global"
    assert "production" in faostat.discover_capabilities()["parameters"]


# ---------------------------------------------------------------------------
# Provider Resolver Hierarchy Tests
# ---------------------------------------------------------------------------

def test_provider_resolver_hierarchy():
    resolver = DataProviderResolver()

    # India weather: IMD is primary national, NASA POWER is global fallback
    weather_chain = resolver.resolve(country="India", state="Tamil Nadu", data_type="weather")
    assert len(weather_chain) >= 2
    assert weather_chain[0].name == "IMD"
    assert weather_chain[1].name == "NASA POWER"

    # India satellite: ISRO Bhoonidhi is primary national, Copernicus is global fallback
    sat_chain = resolver.resolve(country="India", state="Karnataka", data_type="satellite")
    assert len(sat_chain) >= 2
    assert sat_chain[0].name == "ISRO Bhoonidhi"
    assert sat_chain[1].name == "Copernicus Data Space"

    # Non-India weather: falls back to NASA POWER
    us_weather = resolver.resolve(country="United States", data_type="weather")
    assert len(us_weather) >= 1
    assert us_weather[0].name == "NASA POWER"


# ---------------------------------------------------------------------------
# API Endpoints: Providers & Data Status Tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def admin_headers(client):
    email = f"admin.{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Platform Admin", "email": email, "password": "password123", "role": "platform_admin", "state": "Tamil Nadu"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_get_providers_and_status(client, auth_headers):
    # GET /api/v1/providers
    resp = client.get("/api/v1/providers", headers=auth_headers)
    assert resp.status_code == 200
    providers = resp.json()
    assert len(providers) >= 6
    names = [p["provider_name"] for p in providers]
    assert "IMD" in names
    assert "Soil Health Card" in names
    assert "ISRO Bhoonidhi" in names
    assert "Copernicus Data Space" in names
    assert "NASA POWER" in names
    assert "FAOSTAT" in names

    # GET /api/v1/providers/status
    st_resp = client.get("/api/v1/providers/status", headers=auth_headers)
    assert st_resp.status_code == 200
    status_body = st_resp.json()
    assert "summary" in status_body
    assert status_body["summary"]["total_providers"] >= 6
    assert "providers" in status_body


def test_registry_entries_are_not_reported_as_connected(client, auth_headers):
    """A registry entry declares that a source exists; it is not proof that
    this deployment reached it. The test deployment configures no weather,
    satellite or disease credentials, so nothing may be reported healthy."""
    st = client.get("/api/v1/providers/status", headers=auth_headers).json()
    summary = st["summary"]
    assert summary["healthy"] == 0, st["providers"]
    assert summary["connected"] == 0
    assert summary["unverified"] >= 1
    for provider in st["providers"]:
        assert provider["status"] != "healthy", provider
        assert provider["last_sync"] is None, provider


def test_get_countries_and_country_providers(client, auth_headers):
    # GET /api/v1/countries
    resp = client.get("/api/v1/countries", headers=auth_headers)
    assert resp.status_code == 200
    countries = resp.json()
    assert any(c["country"] == "India" for c in countries)

    # GET /api/v1/countries/India/providers
    in_resp = client.get("/api/v1/countries/India/providers", headers=auth_headers)
    assert in_resp.status_code == 200
    in_providers = in_resp.json()
    p_names = [p["provider_name"] for p in in_providers]
    assert "IMD" in p_names
    assert "Soil Health Card" in p_names


def test_farm_data_status_and_sources(client, auth_headers):
    farm_payload = {
        "name": "Data Network Farm",
        "state": "Tamil Nadu",
        "district": "Salem",
        "latitude": 11.6,
        "longitude": 78.1,
        "area_hectares": 3.5,
    }
    farm_resp = client.post("/api/v1/farms", json=farm_payload, headers=auth_headers)
    assert farm_resp.status_code == 201
    farm_id = farm_resp.json()["id"]

    # GET /api/v1/farms/{id}/data-status
    status_resp = client.get(f"/api/v1/farms/{farm_id}/data-status", headers=auth_headers)
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["farm_id"] == farm_id
    assert "weather" in status_data["domains"]
    assert "soil" in status_data["domains"]
    assert "satellite" in status_data["domains"]
    assert "crop" in status_data["domains"]
    assert "water" in status_data["domains"]
    assert "disease" in status_data["domains"]

    # GET /api/v1/farms/{id}/sources
    sources_resp = client.get(f"/api/v1/farms/{farm_id}/sources", headers=auth_headers)
    assert sources_resp.status_code == 200
    sources_data = sources_resp.json()
    assert sources_data["farm_id"] == farm_id
    assert isinstance(sources_data["sources"], list)
    assert len(sources_data["sources"]) >= 1

    # GET /api/v1/farms/{id}/water
    water_resp = client.get(f"/api/v1/farms/{farm_id}/water", headers=auth_headers)
    assert water_resp.status_code == 200
    water_data = water_resp.json()
    assert "soil_moisture_lab" in water_data
    assert "soil_moisture_satellite" in water_data

    # GET /api/v1/farms/{id}/timeline
    timeline_resp = client.get(f"/api/v1/farms/{farm_id}/timeline?window=30d", headers=auth_headers)
    assert timeline_resp.status_code == 200
    timeline_data = timeline_resp.json()
    assert timeline_data["window"] == "30d"
    assert "timeline" in timeline_data


def test_admin_provider_management(client, admin_headers):
    # Test connection endpoint
    test_resp = client.post("/api/v1/admin/providers/nasa-power/test", headers=admin_headers)
    assert test_resp.status_code == 200
    assert "test_results" in test_resp.json()

    # Disable provider
    dis_resp = client.post("/api/v1/admin/providers/nasa-power/disable", headers=admin_headers)
    assert dis_resp.status_code == 200
    assert dis_resp.json()["enabled"] is False

    # Enable provider
    en_resp = client.post("/api/v1/admin/providers/nasa-power/enable", headers=admin_headers)
    assert en_resp.status_code == 200
    assert en_resp.json()["enabled"] is True
