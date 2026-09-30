"""
NASA POWER Agroclimatology Provider Adapter (BHOOMI Data Network).
Provides global weather/climate fallback using NASA's Prediction Of Worldwide Energy Resources API.
"""
from datetime import datetime, date, timedelta, timezone
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

logger = get_logger("bhoomi.datanetwork.nasa_power")

NASA_POWER_BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"


class NASAPowerProvider(DataProvider):
    name = "NASA POWER"
    data_type = "climate"
    country_scope = "Global"
    region_scope = None
    is_fallback = True  # Explicitly marked as Global Fallback

    def __init__(self) -> None:
        self.base_url = getattr(settings, "NASA_POWER_BASE_URL", NASA_POWER_BASE_URL)
        self._last_sync: datetime | None = None
        self._next_sync: datetime | None = None

    def connect(self) -> bool:
        if getattr(settings, "WEATHER_FALLBACK_PROVIDER", None) == "none":
            return False
        # NASA POWER is a public scientific service, no API key required
        return True

    def health_check(self) -> dict:
        try:
            with httpx.Client(timeout=4) as client:
                r = client.get("https://power.larc.nasa.gov/")
                status = "healthy" if r.status_code == 200 else "degraded"
        except Exception:
            status = "degraded"

        return {
            "provider": self.name,
            "country": self.country_scope,
            "data_type": self.data_type,
            "status": status,
            "auth_status": "open_access",
            "base_url": self.base_url,
            "message": "NASA POWER Agroclimatology API operational" if status == "healthy" else "NASA POWER service temporarily degraded",
        }

    def discover_capabilities(self) -> dict:
        return {
            # Canonical BHOOMI parameter names, so callers can reason about
            # providers uniformly. The upstream POWER variable codes are kept
            # alongside for traceability.
            "parameters": ["temperature", "humidity", "precipitation", "wind_speed", "solar_radiation"],
            "upstream_parameter_codes": {
                "temperature": "T2M",
                "humidity": "RH2M",
                "precipitation": "PRECTOTCORR",
                "wind_speed": "WS2M",
                "solar_radiation": "ALLSKY_SFC_SW_DWN",
            },
            "temporal_resolution": "daily / hourly agrometeorology",
            "spatial_coverage": "Global (0.5 x 0.625 degree resolution)",
            "license": "NASA Open Data Policy (Public Domain)",
            "terms_url": "https://power.larc.nasa.gov/",
        }

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    def _fetch_daily(self, lat: float, lon: float, start_date: str, end_date: str) -> dict:
        params = {
            "parameters": "T2M,RH2M,PRECTOTCORR,WS2M,ALLSKY_SFC_SW_DWN",
            "community": "AG",
            "longitude": lon,
            "latitude": lat,
            "start": start_date,
            "end": end_date,
            "format": "JSON",
        }
        with httpx.Client(timeout=settings.AI_REQUEST_TIMEOUT_SECONDS) as client:
            resp = client.get(self.base_url, params=params)
            resp.raise_for_status()
            return resp.json()

    def fetch(self, latitude: float, longitude: float, **kwargs) -> dict:
        end = date.today()
        start = end - timedelta(days=3)
        start_str = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")

        try:
            data = self._fetch_daily(latitude, longitude, start_str, end_str)
            return data
        except Exception as exc:
            logger.warning("nasa_power_fetch_failed", error=str(exc))
            raise ProviderUnavailableError(f"NASA POWER endpoint unreachable: {exc}") from exc

    def normalize(self, raw_data: dict) -> CanonicalWeather:
        properties = raw_data.get("properties", {})
        parameter = properties.get("parameter", {})

        t2m_dict = parameter.get("T2M", {})
        rh_dict = parameter.get("RH2M", {})
        rain_dict = parameter.get("PRECTOTCORR", {})
        wind_dict = parameter.get("WS2M", {})
        solar_dict = parameter.get("ALLSKY_SFC_SW_DWN", {})

        # Find latest available date with valid data (NASA POWER fills missing with -999)
        latest_date_str = None
        for d in sorted(t2m_dict.keys(), reverse=True):
            if t2m_dict[d] != -999:
                latest_date_str = d
                break

        if not latest_date_str:
            raise ProviderUnavailableError("No valid NASA POWER observation dates returned.")

        obs_date = datetime.strptime(latest_date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
        temp_val = t2m_dict.get(latest_date_str) if t2m_dict.get(latest_date_str) != -999 else None
        rh_val = rh_dict.get(latest_date_str) if rh_dict.get(latest_date_str) != -999 else None
        rain_val = rain_dict.get(latest_date_str) if rain_dict.get(latest_date_str) != -999 else None
        wind_ms_val = wind_dict.get(latest_date_str) if wind_dict.get(latest_date_str) != -999 else None
        solar_val = solar_dict.get(latest_date_str) if solar_dict.get(latest_date_str) != -999 else None

        temp_c, conv_t = UnitNormalizer.normalize_temperature(temp_val, "C")
        wind_ms, wind_kmh, conv_w = UnitNormalizer.normalize_wind_speed(wind_ms_val, "m/s")
        rain_mm, conv_r = UnitNormalizer.normalize_rainfall(rain_val, "mm")

        conversions = [c for c in [conv_t, conv_w, conv_r] if c]
        freshness, age_hours = DataQualityService.evaluate_freshness("weather", obs_date)

        condition = "Clear"
        if rain_mm and rain_mm > 5.0:
            condition = "Rain"
        elif rain_mm and rain_mm > 0.5:
            condition = "Light Rain"
        elif rh_val and rh_val > 80:
            condition = "Humid / Overcast"

        provenance = ProvenanceMetadata(
            provider_name=self.name,
            source_dataset="NASA_POWER_MERRA2_GEOS5",
            external_id=f"nasa_power_{latest_date_str}",
            observed_at=obs_date,
            ingested_at=datetime.now(timezone.utc),
            license="NASA Open Data / Public Domain",
            terms_url="https://power.larc.nasa.gov/",
            attribution="NASA Langley Research Center POWER Project",
            quality_score=0.92,
            freshness=freshness,
            data_age_hours=age_hours,
        )

        reading = CanonicalWeather(
            temperature_c=temp_c,
            humidity_pct=rh_val,
            rainfall_mm=rain_mm,
            rain_probability_pct=None,
            wind_speed_ms=wind_ms,
            wind_speed_kmh=wind_kmh,
            condition=condition,
            warning_level="none",
            solar_radiation_mj_m2=solar_val,
            observed_at=obs_date,
            source="nasa_power",
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
