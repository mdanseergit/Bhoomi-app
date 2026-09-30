"""
Copernicus Data Space Ecosystem (CDSE) Satellite Provider Adapter.
Queries European Space Agency (ESA) Sentinel-2 Level-2A STAC APIs for vegetation monitoring.
"""
from datetime import datetime, date, timedelta, timezone
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

logger = get_logger("bhoomi.datanetwork.copernicus")

COPERNICUS_STAC_URL = "https://catalogue.dataspace.copernicus.eu/stac"


class CopernicusSatelliteProvider(DataProvider):
    name = "Copernicus Data Space"
    data_type = "satellite"
    country_scope = "Global"
    region_scope = None
    is_fallback = False

    def __init__(self) -> None:
        self.stac_url = getattr(settings, "COPERNICUS_STAC_URL", COPERNICUS_STAC_URL)
        self.client_id = getattr(settings, "COPERNICUS_CLIENT_ID", None)
        self.client_secret = getattr(settings, "COPERNICUS_CLIENT_SECRET", None)
        self._last_sync: datetime | None = None
        self._next_sync: datetime | None = None

    def connect(self) -> bool:
        if getattr(settings, "SATELLITE_PROVIDER", None) == "none":
            return False
        # Copernicus STAC catalogue allows open search without auth, downloads/processing need OAuth2
        return True

    def health_check(self) -> dict:
        try:
            with httpx.Client(timeout=5) as client:
                r = client.get(f"{self.stac_url}")
                status = "healthy" if r.status_code == 200 else "degraded"
        except Exception:
            status = "degraded"

        return {
            "provider": self.name,
            "country": self.country_scope,
            "data_type": self.data_type,
            "status": status,
            "auth_status": "active" if (self.client_id and self.client_secret) else "open_catalogue_only",
            "base_url": self.stac_url,
            "message": "Copernicus STAC catalogue accessible" if status == "healthy" else "Copernicus service temporarily degraded",
        }

    def discover_capabilities(self) -> dict:
        return {
            "parameters": ["ndvi", "evi", "ndre", "ndwi"],
            "constellations": ["Sentinel-2 (MSI Level-2A / Level-1C)", "Sentinel-1 (SAR GRD)"],
            "indices": ["NDVI", "EVI", "NDRE", "NDWI"],
            "revisit_time_days": 5,
            "spatial_resolution_meters": 10,
            "cloud_filtering": "Supported (eo:cloud_cover property)",
            "license": "Copernicus Open Access / EU Regulation No 1159/2013",
            "terms_url": "https://dataspace.copernicus.eu/terms-and-conditions",
        }

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    def _search_scenes(self, bbox: list[float], start_date: date, end_date: date, max_cloud: float = 30.0) -> list[dict]:
        payload = {
            "collections": ["SENTINEL-2"],
            "bbox": bbox,
            "datetime": f"{start_date.isoformat()}T00:00:00Z/{end_date.isoformat()}T23:59:59Z",
            "query": {
                "eo:cloud_cover": {"lte": max_cloud}
            },
            "limit": 5,
        }
        with httpx.Client(timeout=settings.AI_REQUEST_TIMEOUT_SECONDS) as client:
            resp = client.post(f"{self.stac_url}/search", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("features", [])
            elif resp.status_code in (401, 403):
                raise ProviderUnavailableError("Copernicus credentials required for this product query.")
            return []

    def fetch(self, latitude: float, longitude: float, start_date: Optional[date] = None, end_date: Optional[date] = None, **kwargs) -> list[dict]:
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        delta = 0.005  # ~500m bounding box around farm center
        bbox = [longitude - delta, latitude - delta, longitude + delta, latitude + delta]

        try:
            features = self._search_scenes(bbox, start_date, end_date)
            return features
        except Exception as exc:
            logger.warning("copernicus_stac_fetch_failed", error=str(exc))
            raise ProviderUnavailableError(f"Copernicus STAC catalogue unreachable: {exc}") from exc

    def normalize(self, scene: dict) -> CanonicalSatellite:
        props = scene.get("properties", {})
        dt_str = props.get("datetime") or props.get("start_datetime") or ""
        obs_date = date.fromisoformat(dt_str[:10]) if len(dt_str) >= 10 else date.today()

        # In STAC L2A, vegetation properties or spectral band indices:
        cloud = props.get("eo:cloud_cover", 0.0)
        ndvi = props.get("s2:vegetation_index") or props.get("ndvi")

        # If NDVI is not pre-computed in STAC metadata, check for band reflectance
        if ndvi is None:
            # We derive representative NDVI from scene statistics or band values if present
            ndvi = props.get("s2:mean_ndvi")

        health = None
        if ndvi is not None:
            if ndvi >= 0.65:
                health = "excellent"
            elif ndvi >= 0.45:
                health = "good"
            elif ndvi >= 0.25:
                health = "fair"
            else:
                health = "poor"

        freshness, age_hours = DataQualityService.evaluate_freshness("satellite", obs_date)

        provenance = ProvenanceMetadata(
            provider_name=self.name,
            source_dataset="Sentinel-2_MSI_Level-2A",
            external_id=scene.get("id"),
            observed_at=datetime.combine(obs_date, datetime.min.time(), tzinfo=timezone.utc),
            license="Copernicus Legal Notice / EU Open Access",
            terms_url="https://dataspace.copernicus.eu/terms-and-conditions",
            attribution="Contains modified Copernicus Sentinel data (ESA)",
            quality_score=0.98,
            freshness=freshness,
            data_age_hours=age_hours,
        )

        obs = CanonicalSatellite(
            ndvi=round(float(ndvi), 4) if ndvi is not None else None,
            evi=round(float(props.get("evi")), 4) if props.get("evi") is not None else None,
            vegetation_health=health,
            cloud_cover_pct=round(float(cloud), 2) if cloud is not None else None,
            observation_date=obs_date,
            satellite_name="Sentinel-2",
            source="copernicus",
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
