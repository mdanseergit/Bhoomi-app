from app.core.config import settings
from app.core.exceptions import ProviderUnavailableError
from app.integrations.satellite.base import SatelliteProvider


class UnavailableSatelliteProvider(SatelliteProvider):
    """Fail-closed provider used when no Earth-observation source is wired up.

    BHOOMI must never invent vegetation indices. When no legitimate satellite
    source is configured, the intelligence engine receives an explicitly empty
    vegetation snapshot and the UI renders an honest "no observation" state.
    """

    name = "unavailable"

    def get_vegetation_index(
        self, farm_id: str, latitude: float, longitude: float, start, end
    ) -> list:
        return []

    def get_satellite_observations(
        self, farm_id: str, latitude: float, longitude: float, start, end
    ) -> list:
        return []


def get_satellite_provider() -> SatelliteProvider:
    """Returns the configured satellite provider, or a fail-closed no-op.

    Only providers with a real, credentialed Earth-observation integration are
    supported. Simulated/synthetic index generators are intentionally not
    part of the production provider set.
    """
    provider = (settings.SATELLITE_PROVIDER or "none").strip().lower()

    if provider in ("none", "", "unavailable"):
        return UnavailableSatelliteProvider()

    raise ProviderUnavailableError(
        f"Satellite provider '{provider}' has no adapter in this build. "
        "Set SATELLITE_PROVIDER=none or wire a real Earth-observation adapter."
    )
