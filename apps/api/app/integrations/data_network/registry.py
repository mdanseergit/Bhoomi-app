"""
CountryDataRegistry and RegionDataRegistry (BHOOMI Data Network).
Configures country-level and regional data providers hierarchically without hardcoding business logic.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.data_network import DataProvider


@dataclass
class ProviderDescriptor:
    provider_name: str
    data_type: str
    country: str = "Global"
    region: Optional[str] = None
    priority: int = 1  # 1 = national primary, 2 = regional, 3 = global fallback
    is_fallback: bool = False
    refresh_interval_minutes: int = 60
    base_url: Optional[str] = None
    authentication_type: str = "none"  # api_key, oauth2, none
    license: Optional[str] = None
    terms_url: Optional[str] = None
    documentation_url: Optional[str] = None
    capabilities: dict = field(default_factory=dict)
    rate_limit_per_minute: int = 60


class CountryDataRegistry:
    """Registry of agricultural intelligence sources configured per country."""

    COUNTRIES: Dict[str, Dict[str, List[ProviderDescriptor]]] = {
        "India": {
            "weather": [
                ProviderDescriptor(
                    provider_name="IMD",
                    data_type="weather",
                    country="India",
                    priority=1,
                    refresh_interval_minutes=30,
                    base_url="https://api.imd.gov.in",
                    authentication_type="api_key",
                    license="Government of India / IMD Open Data",
                    terms_url="https://mausam.imd.gov.in/",
                    documentation_url="https://mausam.imd.gov.in/api",
                    capabilities={"forecast_days": 5, "real_time": True, "district_advisories": True},
                ),
                ProviderDescriptor(
                    provider_name="NASA POWER",
                    data_type="weather",
                    country="Global",
                    priority=3,
                    is_fallback=True,
                    refresh_interval_minutes=180,
                    base_url="https://power.larc.nasa.gov/api",
                    authentication_type="none",
                    license="NASA Open Data Policy (Public Domain)",
                    terms_url="https://power.larc.nasa.gov/",
                    capabilities={"solar_radiation": True, "global_coverage": True},
                ),
            ],
            "soil": [
                ProviderDescriptor(
                    provider_name="Soil Health Card",
                    data_type="soil",
                    country="India",
                    priority=1,
                    refresh_interval_minutes=1440,
                    base_url="https://soilhealth.dac.gov.in/api",
                    authentication_type="api_key",
                    license="Government of India / DA&FW",
                    terms_url="https://soilhealth.dac.gov.in/",
                    capabilities={"parameters": 12, "source_type": "lab_test"},
                )
            ],
            "satellite": [
                ProviderDescriptor(
                    provider_name="ISRO Bhoonidhi",
                    data_type="satellite",
                    country="India",
                    priority=1,
                    refresh_interval_minutes=720,
                    base_url="https://bhoonidhi.nrsc.gov.in/api",
                    authentication_type="api_key",
                    license="ISRO / NRSC Data Dissemination Policy",
                    terms_url="https://bhoonidhi.nrsc.gov.in/",
                    capabilities={"sensors": ["Resourcesat-2A", "Sentinel-2 Indian AOI"], "indices": ["NDVI", "Moisture"]},
                ),
                ProviderDescriptor(
                    provider_name="Copernicus Data Space",
                    data_type="satellite",
                    country="Global",
                    priority=2,
                    refresh_interval_minutes=720,
                    base_url="https://catalogue.dataspace.copernicus.eu/stac",
                    authentication_type="none",
                    license="Copernicus Open Access / EU Regulation",
                    terms_url="https://dataspace.copernicus.eu/terms-and-conditions",
                    capabilities={"constellations": ["Sentinel-2", "Sentinel-1"], "indices": ["NDVI", "EVI"]},
                ),
            ],
            "climate": [
                ProviderDescriptor(
                    provider_name="NASA POWER",
                    data_type="climate",
                    country="Global",
                    priority=1,
                    refresh_interval_minutes=360,
                    base_url="https://power.larc.nasa.gov/api",
                    authentication_type="none",
                    license="NASA Open Data Policy",
                    terms_url="https://power.larc.nasa.gov/",
                )
            ],
            "statistics": [
                ProviderDescriptor(
                    provider_name="FAOSTAT",
                    data_type="statistics",
                    country="Global",
                    priority=1,
                    refresh_interval_minutes=43200,
                    base_url="https://fenixservices.fao.org/faostat/api",
                    authentication_type="none",
                    license="CC BY-NC-SA 3.0 IGO",
                    terms_url="https://www.fao.org/faostat/",
                )
            ],
        },
        "Global": {
            "weather": [
                ProviderDescriptor(
                    provider_name="NASA POWER",
                    data_type="weather",
                    country="Global",
                    priority=1,
                    is_fallback=True,
                    refresh_interval_minutes=180,
                    base_url="https://power.larc.nasa.gov/api",
                    authentication_type="none",
                    license="NASA Open Data",
                )
            ],
            "satellite": [
                ProviderDescriptor(
                    provider_name="Copernicus Data Space",
                    data_type="satellite",
                    country="Global",
                    priority=1,
                    refresh_interval_minutes=720,
                    base_url="https://catalogue.dataspace.copernicus.eu/stac",
                    authentication_type="none",
                    license="Copernicus Open Access",
                )
            ],
            "climate": [
                ProviderDescriptor(
                    provider_name="NASA POWER",
                    data_type="climate",
                    country="Global",
                    priority=1,
                    refresh_interval_minutes=360,
                    base_url="https://power.larc.nasa.gov/api",
                    authentication_type="none",
                    license="NASA Open Data",
                )
            ],
            "statistics": [
                ProviderDescriptor(
                    provider_name="FAOSTAT",
                    data_type="statistics",
                    country="Global",
                    priority=1,
                    refresh_interval_minutes=43200,
                    base_url="https://fenixservices.fao.org/faostat/api",
                    authentication_type="none",
                    license="CC BY-NC-SA 3.0 IGO",
                )
            ],
        }
    }

    @classmethod
    def get_supported_countries(cls) -> List[str]:
        return list(cls.COUNTRIES.keys())

    @classmethod
    def get_providers_for_country(cls, country: str, data_type: Optional[str] = None) -> List[ProviderDescriptor]:
        country_providers = cls.COUNTRIES.get(country, cls.COUNTRIES["Global"])
        if data_type:
            return country_providers.get(data_type, cls.COUNTRIES["Global"].get(data_type, []))
        result = []
        for dt_providers in country_providers.values():
            result.extend(dt_providers)
        return result


class RegionDataRegistry:
    """Regional and State/Province specific provider overlays."""

    REGIONS: Dict[str, Dict[str, Dict[str, List[ProviderDescriptor]]]] = {
        "India": {
            "Tamil Nadu": {
                # Inherits National IMD weather with district-level forecast, Soil Health Card state portal
            },
            "Karnataka": {
                # Inherits National IMD weather with KSNDMC integration capability
            },
            "Kerala": {
                # Inherits National IMD weather
            },
            "Maharashtra": {},
            "Punjab": {},
        }
    }

    @classmethod
    def get_supported_regions(cls, country: str) -> List[str]:
        return list(cls.REGIONS.get(country, {}).keys())


def _credential_state(desc) -> tuple[str, str]:
    """Derive (status, auth_status) for a registry entry from real configuration.

    A registry entry is a declaration that a data source exists, not evidence
    that this deployment can reach it. Seeding "healthy"/"active" would claim a
    live connection that was never established, so every entry starts
    unverified and is only promoted when the credentials it needs are present.
    """
    from app.core.config import settings

    configured = False
    if desc.authentication_type == "api_key":
        if desc.provider_name == "IMD":
            configured = bool(settings.IMD_API_BASE_URL and settings.IMD_API_KEY)
        elif desc.provider_name in ("ISRO Bhoonidhi", "Copernicus Data Space"):
            configured = bool(settings.SATELLITE_API_KEY and settings.SATELLITE_API_BASE_URL)
    elif desc.authentication_type == "none":
        # Open endpoints still need to be reachable; nothing here has probed
        # them, so they are reported as available but unverified.
        return "unverified", "not_required"

    if desc.authentication_type == "api_key":
        return ("configured", "active") if configured else ("auth_required", "authentication_required")
    return "unverified", "not_required"


def seed_database_provider_registry(db: Session) -> int:
    """Populates the data_providers database table with default registry entries if absent."""
    count = 0
    for country, categories in CountryDataRegistry.COUNTRIES.items():
        for data_type, descriptors in categories.items():
            for desc in descriptors:
                existing = (
                    db.query(DataProvider)
                    .filter(
                        DataProvider.provider_name == desc.provider_name,
                        DataProvider.data_type == desc.data_type,
                        DataProvider.country == desc.country,
                    )
                    .first()
                )
                if not existing:
                    status, auth_status = _credential_state(desc)

                    provider = DataProvider(
                        provider_name=desc.provider_name,
                        country=desc.country,
                        region=desc.region,
                        data_type=desc.data_type,
                        base_url=desc.base_url,
                        authentication_type=desc.authentication_type,
                        enabled=True,
                        priority=desc.priority,
                        refresh_interval_minutes=desc.refresh_interval_minutes,
                        status=status,
                        auth_status=auth_status,
                        license=desc.license,
                        terms_url=desc.terms_url,
                        documentation_url=desc.documentation_url,
                        capabilities=desc.capabilities,
                        rate_limit_per_minute=desc.rate_limit_per_minute,
                    )
                    db.add(provider)
                    count += 1
    if count > 0:
        db.commit()
    return count
