"""WeatherProvider abstraction.

Concrete providers must implement `get_current` and `get_forecast`. Callers
must always be prepared for a `ProviderUnavailableError` and fall back to
cached/database data -- never crash the request.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class WeatherReading:
    temperature: float | None
    humidity: float | None
    rainfall: float | None
    rain_probability: float | None
    wind_speed: float | None
    weather_condition: str | None
    warning_level: str | None
    source: str
    forecast_time: datetime


class WeatherProvider(ABC):
    name: str = "base"

    @abstractmethod
    def get_current(self, latitude: float, longitude: float) -> WeatherReading:
        ...

    @abstractmethod
    def get_forecast(self, latitude: float, longitude: float, days: int = 3) -> list[WeatherReading]:
        ...
