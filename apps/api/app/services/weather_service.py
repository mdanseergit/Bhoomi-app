"""
WeatherService orchestrates the WeatherProvider abstraction with Redis
caching and database-backed graceful degradation.

Resolution order for a farm's "current weather":
    1. Redis cache (fresh within WEATHER_CACHE_TTL_SECONDS)
    2. Live IMD provider call (cached on success)
    3. Most recent `weather_observations` row for the farm (labeled stale)

If none of the above produce a reading, an *empty* snapshot is returned:
every measurement is ``None`` and ``source`` is ``"unavailable"``. BHOOMI
never substitutes invented weather for a missing observation -- the UI is
expected to render an honest "unavailable" state instead.

Background jobs (see app/workers) are responsible for periodically
refreshing (1) so the API layer rarely needs to hit the live provider
synchronously during a page render.
"""
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ProviderUnavailableError
from app.core.logging import get_logger
from app.core.redis_client import get_redis
from app.integrations.weather.imd_provider import IMDWeatherProvider
from app.models.farm import Farm
from app.models.weather import WeatherObservation
from app.services.agriculture.schema import WeatherSnapshot

logger = get_logger("bhoomi.weather.service")

UNAVAILABLE_SOURCE = "unavailable"


class WeatherService:
    def __init__(self) -> None:
        self.provider = IMDWeatherProvider()
        self.redis = get_redis()

    def _cache_key(self, farm_id: str) -> str:
        return f"weather:current:{farm_id}"

    def get_current_snapshot(self, db: Session, farm: Farm) -> WeatherSnapshot:
        cache_key = self._cache_key(str(farm.id))
        try:
            cached = self.redis.get(cache_key)
            if cached:
                payload = json.loads(cached)
                return WeatherSnapshot(**{**payload, "observed_at": datetime.fromisoformat(payload["observed_at"])})
        except Exception:
            logger.warning("weather_cache_read_failed")

        # Try primary live provider (e.g. IMD)
        try:
            reading = self.provider.get_current(farm.latitude, farm.longitude)
            snapshot = WeatherSnapshot(
                temperature_c=reading.temperature,
                humidity_pct=reading.humidity,
                rainfall_mm=reading.rainfall,
                rain_probability_pct=reading.rain_probability,
                wind_speed_kmh=reading.wind_speed,
                condition=reading.weather_condition,
                warning_level=reading.warning_level,
                source="imd",
                observed_at=reading.forecast_time,
                is_stale=False,
            )
            self._store(db, farm, snapshot)
            self._cache(cache_key, snapshot)
            return snapshot
        except ProviderUnavailableError as exc:
            logger.info("primary_weather_provider_unavailable_trying_global_fallback", reason=str(exc))
            # Try global weather/climate fallback (NASA POWER) if enabled
            if (settings.WEATHER_FALLBACK_PROVIDER or "").lower() in ("nasa_power", "nasa"):
                try:
                    from app.integrations.data_network.nasa_power import NASAPowerProvider
                    nasa = NASAPowerProvider()
                    raw_power = nasa.fetch(latitude=farm.latitude, longitude=farm.longitude)
                    canonical = nasa.normalize(raw_power)
                    snapshot = WeatherSnapshot(
                        temperature_c=canonical.temperature_c,
                        humidity_pct=canonical.humidity_pct,
                        rainfall_mm=canonical.rainfall_mm,
                        rain_probability_pct=None,
                        wind_speed_kmh=canonical.wind_speed_kmh,
                        condition=canonical.condition,
                        warning_level=canonical.warning_level,
                        source="nasa_power",
                        observed_at=canonical.observed_at or datetime.now(timezone.utc),
                        is_stale=False,
                    )
                    self._store(db, farm, snapshot)
                    self._cache(cache_key, snapshot)
                    return snapshot
                except Exception as nasa_exc:
                    logger.info("nasa_power_fallback_unavailable", reason=str(nasa_exc))

            return self._fallback(db, farm)

    def _fallback(self, db: Session, farm: Farm) -> WeatherSnapshot:
        last = (
            db.query(WeatherObservation)
            .filter(WeatherObservation.farm_id == farm.id)
            .order_by(WeatherObservation.observed_at.desc())
            .first()
        )
        if last:
            return WeatherSnapshot(
                temperature_c=last.temperature,
                humidity_pct=last.humidity,
                rainfall_mm=last.rainfall,
                rain_probability_pct=None,
                wind_speed_kmh=last.wind_speed,
                condition=last.weather_condition,
                warning_level=last.warning_level,
                source=f"{last.source}_cached",
                observed_at=last.observed_at,
                is_stale=True,
            )
        # No live provider, no cached reading, no history. Report honestly.
        return WeatherSnapshot(
            temperature_c=None,
            humidity_pct=None,
            rainfall_mm=None,
            rain_probability_pct=None,
            wind_speed_kmh=None,
            condition=None,
            warning_level=None,
            source=UNAVAILABLE_SOURCE,
            observed_at=None,
            is_stale=True,
        )

    def _store(self, db: Session, farm: Farm, snapshot: WeatherSnapshot) -> None:
        # Verify farm exists before persisting foreign key
        existing_farm = db.query(Farm).filter(Farm.id == farm.id).first()
        if not existing_farm:
            return
        obs = WeatherObservation(
            farm_id=farm.id,
            temperature=snapshot.temperature_c,
            humidity=snapshot.humidity_pct,
            rainfall=snapshot.rainfall_mm,
            wind_speed=snapshot.wind_speed_kmh,
            weather_condition=snapshot.condition,
            warning_level=snapshot.warning_level,
            source=snapshot.source,
            observed_at=snapshot.observed_at or datetime.now(timezone.utc),
            ingested_at=datetime.now(timezone.utc),
            freshness_status="recent" if not snapshot.is_stale else "stale",
            quality_status="good",
        )
        db.add(obs)
        db.commit()

    def _cache(self, key: str, snapshot: WeatherSnapshot) -> None:
        try:
            payload = {
                "temperature_c": snapshot.temperature_c,
                "humidity_pct": snapshot.humidity_pct,
                "rainfall_mm": snapshot.rainfall_mm,
                "rain_probability_pct": snapshot.rain_probability_pct,
                "wind_speed_kmh": snapshot.wind_speed_kmh,
                "condition": snapshot.condition,
                "warning_level": snapshot.warning_level,
                "source": snapshot.source,
                "observed_at": snapshot.observed_at.isoformat(),
                "is_stale": snapshot.is_stale,
            }
            self.redis.setex(key, settings.WEATHER_CACHE_TTL_SECONDS, json.dumps(payload))
        except Exception:
            logger.warning("weather_cache_write_failed")
