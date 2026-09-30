"""SatelliteProvider abstraction.

Production deployments can plug in a legitimate Earth-observation source
(e.g. Sentinel Hub, Microsoft Planetary Computer, Bhuvan/ISRO). For local
development, `SeededDevSatelliteProvider` returns a clearly labeled seeded
historical dataset -- it never simulates a live external API response.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass
class VegetationObservation:
    observation_date: date
    ndvi: float | None
    evi: float | None
    vegetation_health: str | None
    cloud_cover_pct: float | None
    source: str
    is_dev_dataset: bool


class SatelliteProvider(ABC):
    name: str = "base"

    @abstractmethod
    def get_vegetation_index(self, farm_id: str, latitude: float, longitude: float, start: date, end: date) -> list[VegetationObservation]:
        ...

    @abstractmethod
    def get_satellite_observations(self, farm_id: str, latitude: float, longitude: float, start: date, end: date) -> list[VegetationObservation]:
        ...
