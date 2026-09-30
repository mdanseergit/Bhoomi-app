"""
ISRO / Bhoonidhi Earth Observation Provider Adapter (BHOOMI Data Network).
Connects to ISRO's Bhoonidhi & Bhuvan STAC / Open EO API for Indian agricultural remote sensing.
"""
from datetime import datetime, date, timezone
from typing import Optional, List
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.exceptions import ProviderUnavailableError
from app.core.logging import get_logger
from app.integrations.data_network.base import (
    CanonicalSatellite,
    DataProvider,
    FreshnessState,
    ProvenanceMetadata,
    QualityStatus,
)
from app.integrations.data_network.quality_service import DataQualityService
from app.models.satellite import SatelliteObservation

logger = get_logger("bhoomi.datanetwork.bhoonidhi")


class ISROBhoonidhiProvider(DataProvider):
    name = "ISRO Bhoonidhi"
    data_type = "satellite"
    country_scope = "India"
    region_scope = None
    is_fallback = False

    def __init__(self) -> None:
        self.base_url = getattr(settings, "BHOONIDHI_API_BASE_URL", None)
        self.api_key = getattr(settings, "BHOONIDHI_API_KEY", None)
        self._last_sync: datetime | None = None
        self._next_sync: datetime | None = None

    def connect(self) -> bool:
        return bool(self.base_url and self.api_key)

    def health_check(self) -> dict:
        configured = self.connect()
        return {
            "provider": self.name,
            "country": self.country_scope,
            "data_type": self.data_type,
            "status": "healthy" if configured else "authentication_required",
            "auth_status": "active" if configured else "authentication_required",
            "base_url": self.base_url or "https://bhoonidhi.nrsc.gov.in/api (unconfigured)",
            "message": "ISRO Bhoonidhi STAC API connected" if configured else "CONFIGURED BUT AUTHENTICATION REQUIRED: NRSC/ISRO Bhoonidhi programmatic credentials required",
        }

    def discover_capabilities(self) -> dict:
        return {
            "parameters": ["ndvi", "evi", "soil_moisture", "surface_water", "crop_condition"],
            "missions": ["Resourcesat-2/2A (AWiFS, LISS-III, LISS-IV)", "Cartosat", "Sentinel-2 Indian coverage"],
            "thematic_products": ["NDVI", "Soil Moisture", "Surface Water Dynamics", "Crop Condition Indices"],
            "format": "STAC 1.0.0 / GeoTIFF / Cloud Optimized GeoTIFF",
            "license": "ISRO / NRSC Data Dissemination Policy",
            "terms_url": "https://bhoonidhi.nrsc.gov.in/bhoonidhi/about.html",
        }

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    def _search_stac(self, bbox: list[float], start_date: date, end_date: date) -> dict:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "bbox": bbox,
            "datetime": f"{start_date.isoformat()}T00:00:00Z/{end_date.isoformat()}T23:59:59Z",
            "collections": ["resourcesat_ndvi", "sentinel2_l2a_india"],
            "limit": 10,
        }
        with httpx.Client(timeout=settings.AI_REQUEST_TIMEOUT_SECONDS) as client:
            resp = client.post(f"{self.base_url}/stac/search", json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()

    def fetch(self, latitude: float, longitude: float, start_date: date, end_date: date, **kwargs) -> list[dict]:
        if not self.connect():
            # Honest fail-closed: do NOT fabricate satellite data
            raise ProviderUnavailableError(
                "CONFIGURED BUT AUTHENTICATION REQUIRED: ISRO/Bhoonidhi API credentials (BHOONIDHI_API_KEY) are not configured."
            )
        delta = 0.01  # ~1km box
        bbox = [longitude - delta, latitude - delta, longitude + delta, latitude + delta]
        try:
            data = self._search_stac(bbox, start_date, end_date)
            return data.get("features", [])
        except httpx.HTTPError as exc:
            logger.warning("bhoonidhi_stac_search_failed", error=str(exc))
            raise ProviderUnavailableError(f"Bhoonidhi STAC endpoint unreachable: {exc}") from exc

    def normalize(self, feature: dict) -> CanonicalSatellite:
        props = feature.get("properties", {})
        obs_date_str = props.get("datetime", "")[:10]
        try:
            obs_date = date.fromisoformat(obs_date_str) if obs_date_str else date.today()
        except Exception:
            obs_date = date.today()

        ndvi = props.get("mean_ndvi") or props.get("ndvi")
        cloud = props.get("eo:cloud_cover", 0.0)

        # Health categorisation based on NDVI
        health = None
        if ndvi is not None:
            if ndvi >= 0.6:
                health = "excellent"
            elif ndvi >= 0.4:
                health = "good"
            elif ndvi >= 0.2:
                health = "fair"
            else:
                health = "poor"

        freshness, age_hours = DataQualityService.evaluate_freshness("satellite", obs_date)

        provenance = ProvenanceMetadata(
            provider_name=self.name,
            source_dataset=feature.get("collection", "ISRO_Bhoonidhi_EO"),
            external_id=feature.get("id"),
            observed_at=datetime.combine(obs_date, datetime.min.time(), tzinfo=timezone.utc),
            license="ISRO / NRSC Data Policy",
            terms_url="https://bhoonidhi.nrsc.gov.in/",
            attribution="National Remote Sensing Centre (NRSC), ISRO",
            quality_score=0.96,
            freshness=freshness,
            data_age_hours=age_hours,
        )

        obs = CanonicalSatellite(
            ndvi=round(float(ndvi), 4) if ndvi is not None else None,
            evi=round(float(props.get("evi")), 4) if props.get("evi") is not None else None,
            vegetation_health=health,
            cloud_cover_pct=round(float(cloud), 2) if cloud is not None else None,
            observation_date=obs_date,
            satellite_name=props.get("platform", "Resourcesat-2A"),
            source="bhoonidhi",
            is_dev_dataset=False,
            freshness=freshness,
            provenance=provenance,
        )
        quality, _ = DataQualityService.validate_satellite(obs)
        obs.quality = quality
        return obs

    def validate(self, data: CanonicalSatellite) -> tuple[bool, list[str]]:
        status, issues = DataQualityService.validate_satellite(data)
        return status != QualityStatus.INVALID, issues

    def store(self, db, data: CanonicalSatellite, farm_id=None) -> SatelliteObservation:
        if not farm_id:
            raise ValueError("farm_id required to store satellite observation")

        existing = (
            db.query(SatelliteObservation)
            .filter(
                SatelliteObservation.farm_id == farm_id,
                SatelliteObservation.observation_date == data.observation_date,
            )
            .first()
        )
        if existing:
            return existing

        obs = SatelliteObservation(
            farm_id=farm_id,
            observation_date=data.observation_date,
            ndvi=data.ndvi,
            evi=data.evi,
            vegetation_health=data.vegetation_health,
            cloud_cover_pct=data.cloud_cover_pct,
            source=data.source,
            is_dev_dataset=False,
            freshness_status=data.freshness.value,
            quality_status=data.quality.value,
            external_id=data.provenance.external_id if data.provenance else None,
            ingested_at=date.today(),
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
