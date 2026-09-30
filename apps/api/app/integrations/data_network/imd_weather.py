"""
India Meteorological Department (IMD) Weather Provider Adapter.
Official weather platform for India observations, forecasts, and agricultural warnings.
"""
from datetime import datetime, timezone
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.exceptions import ProviderUnavailableError
from app.core.logging import get_logger
from app.integrations.data_network.base import (
    CanonicalWeather,
    DataProvider,
    FreshnessState,
    ProvenanceMetadata,
    QualityStatus,
)
from app.integrations.data_network.normalizer import UnitNormalizer
from app.integrations.data_network.quality_service import DataQualityService
from app.models.weather import WeatherObservation

logger = get_logger("bhoomi.datanetwork.imd")


class IMDWeatherProvider(DataProvider):
    name = "IMD"
    data_type = "weather"
    country_scope = "India"
    region_scope = None
    is_fallback = False

    def __init__(self) -> None:
        self.base_url = settings.IMD_API_BASE_URL
        self.api_key = settings.IMD_API_KEY
        self._last_sync: datetime | None = None
        self._next_sync: datetime | None = None

    def connect(self) -> bool:
        return bool(self.base_url and self.api_key)

    def health_check(self) -> dict:
        configured = self.connect()
        return {
            "provider": self.name,
            "country": self.country_scope,
            "data_type": self.data_type,
            "status": "healthy" if configured else "authentication_required",
            "auth_status": "active" if configured else "authentication_required",
            "base_url": self.base_url or "https://api.imd.gov.in (unconfigured)",
            "message": "IMD platform connected" if configured else "IMD API credentials (IMD_API_KEY) required for live telemetry",
        }

    def discover_capabilities(self) -> dict:
        return {
            "parameters": ["temperature", "humidity", "rainfall", "rain_probability", "wind_speed", "weather_condition", "warning_level"],
            "update_frequency_minutes": 30,
            "forecast_days": 5,
            "spatial_resolution": "station / district level",
            "license": "Government of India Open Data / IMD Data Sharing Policy",
            "terms_url": "https://mausam.imd.gov.in/",
        }

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    def _request(self, endpoint: str, params: dict) -> dict:
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        with httpx.Client(timeout=settings.AI_REQUEST_TIMEOUT_SECONDS) as client:
            resp = client.get(f"{self.base_url}{endpoint}", params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()

    def fetch(self, latitude: float, longitude: float, **kwargs) -> dict:
        if not self.connect():
            raise ProviderUnavailableError("IMD weather provider is not configured (missing IMD_API_KEY or BASE_URL).")
        try:
            return self._request("/current", {"lat": latitude, "lon": longitude})
        except httpx.HTTPError as exc:
            logger.warning("imd_fetch_failed", error=str(exc))
            raise ProviderUnavailableError(f"IMD weather endpoint unreachable: {exc}") from exc

    def normalize(self, raw_data: dict) -> CanonicalWeather:
        conversions = []
        raw_temp = raw_data.get("temperature")
        temp_c, conv_t = UnitNormalizer.normalize_temperature(raw_temp, raw_data.get("temp_unit", "C"))
        if conv_t:
            conversions.append(conv_t)

        raw_wind = raw_data.get("wind_speed")
        wind_ms, wind_kmh, conv_w = UnitNormalizer.normalize_wind_speed(raw_wind, raw_data.get("wind_unit", "km/h"))
        if conv_w:
            conversions.append(conv_w)

        raw_rain = raw_data.get("rainfall")
        rain_mm, conv_r = UnitNormalizer.normalize_rainfall(raw_rain, raw_data.get("rain_unit", "mm"))
        if conv_r:
            conversions.append(conv_r)

        obs_time_str = raw_data.get("observation_time")
        if obs_time_str:
            try:
                obs_time = datetime.fromisoformat(obs_time_str)
            except Exception:
                obs_time = datetime.now(timezone.utc)
        else:
            obs_time = datetime.now(timezone.utc)

        freshness, age_hours = DataQualityService.evaluate_freshness("weather", obs_time)

        provenance = ProvenanceMetadata(
            provider_name=self.name,
            source_dataset="IMD_AWS_ARG_Platform",
            external_id=raw_data.get("station_id"),
            observed_at=obs_time,
            ingested_at=datetime.now(timezone.utc),
            license="Government of India / IMD",
            terms_url="https://mausam.imd.gov.in/",
            attribution="India Meteorological Department",
            quality_score=0.98,
            freshness=freshness,
            data_age_hours=age_hours,
        )

        reading = CanonicalWeather(
            temperature_c=temp_c,
            humidity_pct=float(raw_data.get("humidity")) if raw_data.get("humidity") is not None else None,
            rainfall_mm=rain_mm,
            rain_probability_pct=float(raw_data.get("rain_probability")) if raw_data.get("rain_probability") is not None else None,
            wind_speed_ms=wind_ms,
            wind_speed_kmh=wind_kmh,
            condition=raw_data.get("condition") or raw_data.get("weather_condition"),
            warning_level=raw_data.get("warning_level", "none"),
            observed_at=obs_time,
            source="imd",
            freshness=freshness,
            provenance=provenance,
            conversions=conversions,
        )

        quality_status, _ = DataQualityService.validate_weather(reading)
        reading.quality = quality_status
        return reading

    def validate(self, data: CanonicalWeather) -> tuple[bool, list[str]]:
        status, issues = DataQualityService.validate_weather(data)
        return status != QualityStatus.INVALID, issues

    def store(self, db, data: CanonicalWeather, farm_id=None) -> WeatherObservation:
        if not farm_id:
            raise ValueError("farm_id required to store weather observation")
        obs = WeatherObservation(
            farm_id=farm_id,
            temperature=data.temperature_c,
            humidity=data.humidity_pct,
            rainfall=data.rainfall_mm,
            wind_speed=data.wind_speed_kmh,
            weather_condition=data.condition,
            warning_level=data.warning_level,
            source=data.source,
            freshness_status=data.freshness.value,
            quality_status=data.quality.value,
            external_id=data.provenance.external_id if data.provenance else None,
            observed_at=data.observed_at or datetime.now(timezone.utc),
            ingested_at=datetime.now(timezone.utc),
        )
        db.add(obs)
        db.commit()
        db.refresh(obs)
        self._last_sync = datetime.now(timezone.utc)
        return obs

    def get_last_sync(self) -> datetime | None:
        return self._last_sync

    def get_next_sync(self) -> datetime | None:
        return self._next_sync

    def disconnect(self) -> None:
        pass
