"""
FAOSTAT Agriculture Statistics Provider Adapter (BHOOMI Data Network).
Provides country and regional historical production, harvested area, and yield baselines.
"""
from datetime import datetime, timezone
from typing import Optional, List
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.exceptions import ProviderUnavailableError
from app.core.logging import get_logger
from app.integrations.data_network.base import (
    CanonicalStatistic,
    DataProvider,
    FreshnessState,
    ProvenanceMetadata,
    QualityStatus,
)
from app.models.data_network import AgricultureStatistic

logger = get_logger("bhoomi.datanetwork.faostat")

FAOSTAT_API_URL = "https://fenixservices.fao.org/faostat/api/v1/en/data/QCL"


class FAOSTATProvider(DataProvider):
    name = "FAOSTAT"
    data_type = "statistics"
    country_scope = "Global"
    region_scope = None
    is_fallback = False

    def __init__(self) -> None:
        self.api_url = getattr(settings, "FAOSTAT_API_URL", FAOSTAT_API_URL)
        self._last_sync: datetime | None = None
        self._next_sync: datetime | None = None

    def connect(self) -> bool:
        # FAOSTAT API is open to public developers
        return True

    def health_check(self) -> dict:
        try:
            with httpx.Client(timeout=6) as client:
                r = client.get("https://fenixservices.fao.org/faostat/api/v1/en/definitions/domain/QCL")
                status = "healthy" if r.status_code == 200 else "degraded"
        except Exception:
            status = "degraded"

        return {
            "provider": self.name,
            "country": self.country_scope,
            "data_type": self.data_type,
            "status": status,
            "auth_status": "open_access",
            "base_url": self.api_url,
            "message": "FAOSTAT open data portal reachable" if status == "healthy" else "FAOSTAT portal temporarily degraded",
        }

    def discover_capabilities(self) -> dict:
        return {
            "parameters": ["production", "area_harvested", "yield"],
            "domains": ["Crops and livestock products (QCL)"],
            "elements": ["Area harvested (ha)", "Production (tonnes)", "Yield (100 g/ha or kg/ha)"],
            "coverage": "245+ countries & territories, historical data 1961-present",
            "license": "Creative Commons Attribution-NonCommercial-ShareAlike 3.0 IGO (CC BY-NC-SA 3.0 IGO)",
            "terms_url": "https://www.fao.org/contact-us/terms/en/",
        }

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    def _query_faostat(self, country_code: str, element_code: str, year: int) -> dict:
        params = {
            "area": country_code,
            "element": element_code,
            "year": str(year),
            "show_codes": "true",
            "show_unit": "true",
        }
        with httpx.Client(timeout=settings.AI_REQUEST_TIMEOUT_SECONDS) as client:
            resp = client.get(self.api_url, params=params)
            resp.raise_for_status()
            return resp.json()

    def fetch(self, country: str, crop: str = "Rice", year: int = 2023, **kwargs) -> list[dict]:
        # FAOSTAT area code for India = 100, USA = 231, World = 5000
        country_code_map = {"india": "100", "usa": "231", "united states": "231", "global": "5000"}
        c_code = country_code_map.get(country.lower(), "100")
        try:
            data = self._query_faostat(c_code, "5419", year)  # 5419 = Yield
            items = data.get("data", [])
            return items
        except Exception as exc:
            logger.warning("faostat_fetch_failed", error=str(exc))
            raise ProviderUnavailableError(f"FAOSTAT API unreachable: {exc}") from exc

    def normalize(self, record: dict) -> CanonicalStatistic:
        country_name = record.get("Area", "Global")
        crop_name = record.get("Item", "Crop")
        year = int(record.get("Year", 2023))
        element = record.get("Element", "Yield")
        val = float(record.get("Value", 0.0))
        unit = record.get("Unit", "kg/ha")

        stat = CanonicalStatistic(
            country=country_name,
            region=record.get("Region"),
            crop=crop_name,
            year=year,
            element=element,
            value=val,
            unit=unit,
            source="FAOSTAT",
            observed_at=datetime(year, 12, 31, tzinfo=timezone.utc),
        )
        return stat

    def validate(self, data: CanonicalStatistic) -> tuple[bool, list[str]]:
        issues = []
        if data.value < 0:
            issues.append("Agricultural statistical metric cannot be negative")
            return False, issues
        return True, issues

    def store(self, db, data: CanonicalStatistic, farm_id=None) -> AgricultureStatistic:
        existing = (
            db.query(AgricultureStatistic)
            .filter(
                AgricultureStatistic.country == data.country,
                AgricultureStatistic.crop == data.crop,
                AgricultureStatistic.year == data.year,
                AgricultureStatistic.element == data.element,
            )
            .first()
        )
        if existing:
            existing.value = data.value
            db.commit()
            db.refresh(existing)
            return existing

        stat = AgricultureStatistic(
            country=data.country,
            region=data.region,
            crop=data.crop,
            year=data.year,
            element=data.element,
            value=data.value,
            unit=data.unit,
            source=data.source,
            observed_at=data.observed_at,
            ingested_at=datetime.now(timezone.utc),
        )
        db.add(stat)
        db.commit()
        db.refresh(stat)
        self._last_sync = datetime.now(timezone.utc)
        return stat

    def get_last_sync(self) -> datetime | None:
        return self._last_sync

    def get_next_sync(self) -> datetime | None:
        return self._next_sync

    def disconnect(self) -> None:
        pass
