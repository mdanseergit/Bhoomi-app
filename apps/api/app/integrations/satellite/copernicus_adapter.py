from datetime import date
from typing import List

from app.core.logging import get_logger
from app.integrations.data_network.copernicus_satellite import CopernicusSatelliteProvider
from app.integrations.satellite.base import SatelliteProvider, VegetationObservation

logger = get_logger("bhoomi.satellite.copernicus")


class CopernicusAdapter(SatelliteProvider):
    name = "copernicus"

    def __init__(self) -> None:
        self._provider = CopernicusSatelliteProvider()

    def get_vegetation_index(
        self, farm_id: str, latitude: float, longitude: float, start: date, end: date
    ) -> List[VegetationObservation]:
        try:
            features = self._provider.fetch(latitude, longitude, start_date=start, end_date=end)
            observations: List[VegetationObservation] = []
            for feat in features:
                canonical = self._provider.normalize(feat)
                observations.append(
                    VegetationObservation(
                        observation_date=canonical.observation_date,
                        ndvi=canonical.ndvi,
                        evi=canonical.evi,
                        vegetation_health=canonical.vegetation_health,
                        cloud_cover_pct=canonical.cloud_cover_pct,
                        source="copernicus_sentinel2",
                        is_dev_dataset=False,
                    )
                )
            return observations
        except Exception as exc:
            logger.info("copernicus_satellite_observations_unavailable", reason=str(exc))
            return []

    def get_satellite_observations(
        self, farm_id: str, latitude: float, longitude: float, start: date, end: date
    ) -> List[VegetationObservation]:
        return self.get_vegetation_index(farm_id, latitude, longitude, start, end)
