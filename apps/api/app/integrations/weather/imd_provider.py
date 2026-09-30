"""
IMDWeatherProvider -- integration with the official India Meteorological
Department (IMD) API surface.

IMD_API_BASE_URL / IMD_API_KEY are read from the environment (see
.env.example) and are never hardcoded. When credentials are not configured
(typical for local development) this provider raises
`ProviderUnavailableError` rather than fabricating a live reading -- callers
are expected to fall back to cached data or a clearly-labeled seeded
baseline (see `app.services.weather_service`).
"""
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.exceptions import ProviderUnavailableError
from app.core.logging import get_logger
from app.integrations.weather.base import WeatherProvider, WeatherReading

logger = get_logger("bhoomi.weather.imd")


class IMDWeatherProvider(WeatherProvider):
    name = "imd"

    def __init__(self) -> None:
        self.base_url = settings.IMD_API_BASE_URL
        self.api_key = settings.IMD_API_KEY

    def _configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    def _request(self, path: str, params: dict) -> dict:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        with httpx.Client(timeout=settings.AI_REQUEST_TIMEOUT_SECONDS) as client:
            resp = client.get(f"{self.base_url}{path}", params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()

    def get_current(self, latitude: float, longitude: float):
        if not self._configured():
            raise ProviderUnavailableError(
                "IMD weather provider is not configured (missing IMD_API_BASE_URL/IMD_API_KEY)."
            )
        try:
            data = self._request("/current", {"lat": latitude, "lon": longitude})
        except httpx.HTTPError as exc:
            logger.warning("imd_request_failed", error=str(exc))
            raise ProviderUnavailableError("IMD weather service did not respond in time.") from exc
        return self._parse(data)

    def get_forecast(self, latitude: float, longitude: float, days: int = 3):
        if not self._configured():
            raise ProviderUnavailableError(
                "IMD weather provider is not configured (missing IMD_API_BASE_URL/IMD_API_KEY)."
            )
        try:
            data = self._request("/forecast", {"lat": latitude, "lon": longitude, "days": days})
        except httpx.HTTPError as exc:
            logger.warning("imd_forecast_failed", error=str(exc))
            raise ProviderUnavailableError("IMD forecast service did not respond in time.") from exc
        return [self._parse(item) for item in data.get("forecast", [])]

    @staticmethod
    def _parse(data: dict) -> WeatherReading:
        from datetime import datetime, timezone

        return WeatherReading(
            temperature=data.get("temperature"),
            humidity=data.get("humidity"),
            rainfall=data.get("rainfall"),
            rain_probability=data.get("rain_probability"),
            wind_speed=data.get("wind_speed"),
            weather_condition=data.get("condition"),
            warning_level=data.get("warning_level", "none"),
            source="imd",
            forecast_time=datetime.now(timezone.utc),
        )
