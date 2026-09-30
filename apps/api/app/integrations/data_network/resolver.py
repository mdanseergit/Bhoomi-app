"""
DataProviderResolver Engine (BHOOMI Data Network).
Dynamically resolves the highest-priority, geographically appropriate provider
with automatic fallback and multi-source awareness.
"""
from typing import List, Optional, Tuple, Type
from sqlalchemy.orm import Session

from app.core.exceptions import ProviderUnavailableError
from app.core.logging import get_logger
from app.integrations.data_network.base import DataProvider
from app.integrations.data_network.copernicus_satellite import CopernicusSatelliteProvider
from app.integrations.data_network.faostat import FAOSTATProvider
from app.integrations.data_network.imd_weather import IMDWeatherProvider
from app.integrations.data_network.isro_bhoonidhi import ISROBhoonidhiProvider
from app.integrations.data_network.nasa_power import NASAPowerProvider
from app.integrations.data_network.soil_health_card import SoilHealthCardProvider
from app.models.data_network import DataProvider as DataProviderModel

logger = get_logger("bhoomi.datanetwork.resolver")


class DataProviderResolver:
    # Provider mapping registry
    _ADAPTERS: dict[str, Type[DataProvider]] = {
        "IMD": IMDWeatherProvider,
        "Soil Health Card": SoilHealthCardProvider,
        "ISRO Bhoonidhi": ISROBhoonidhiProvider,
        "Copernicus Data Space": CopernicusSatelliteProvider,
        "NASA POWER": NASAPowerProvider,
        "FAOSTAT": FAOSTATProvider,
    }

    @classmethod
    def resolve_chain(
        cls,
        country: str,
        state: Optional[str],
        data_type: str,
        db: Optional[Session] = None,
    ) -> List[DataProvider]:
        """
        Resolves an ordered list of providers for the requested location and data type.
        Order:
            1. Official National Primary
            2. Regional / State-specific (if exists)
            3. Trusted Global Fallback
        """
        dt = data_type.lower()
        c = country.strip() if country else "India"
        chain: List[DataProvider] = []

        if dt in ("weather", "current_weather"):
            if c.lower() == "india":
                chain.append(IMDWeatherProvider())
            # NASA POWER is global weather/climate fallback for all countries
            chain.append(NASAPowerProvider())

        elif dt in ("soil", "soil_profile"):
            if c.lower() == "india":
                chain.append(SoilHealthCardProvider())

        elif dt in ("satellite", "vegetation", "ndvi"):
            if c.lower() == "india":
                chain.append(ISROBhoonidhiProvider())
            # Copernicus is global satellite provider
            chain.append(CopernicusSatelliteProvider())

        elif dt in ("climate",):
            chain.append(NASAPowerProvider())

        elif dt in ("statistics", "crop_stats"):
            chain.append(FAOSTATProvider())

        return chain

    @classmethod
    def resolve(
        cls,
        country: str = "India",
        state: Optional[str] = None,
        district: Optional[str] = None,
        data_type: str = "weather",
        db: Optional[Session] = None,
    ) -> List[DataProvider]:
        """Convenience resolver satisfying BHOOMI provider resolution requirement."""
        return cls.resolve_chain(country, state, data_type, db)

    @classmethod
    def resolve_primary(
        cls,
        country: str,
        state: Optional[str] = None,
        district: Optional[str] = None,
        data_type: str = "weather",
        db: Optional[Session] = None,
    ) -> DataProvider:
        """
        Resolves the single highest-priority provider that is configured,
        or the first provider in the priority chain.
        """
        chain = cls.resolve_chain(country, state, data_type, db)
        if not chain:
            raise ProviderUnavailableError(f"No data providers registered for country '{country}' and data type '{data_type}'.")

        # Try to find first connected / active provider in chain
        for provider in chain:
            if provider.connect():
                return provider

        # If none connected (e.g. API keys not configured in local environment),
        # return the primary provider so caller receives the honest error / status
        return chain[0]
