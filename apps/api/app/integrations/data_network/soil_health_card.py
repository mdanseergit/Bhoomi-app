"""
Soil Health Card (SHC) Provider Adapter - Government of India.
Provides verified laboratory soil test observations across 12 macro/micro nutrient parameters.
"""
from datetime import datetime, date, timezone
from typing import Optional
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.exceptions import ProviderUnavailableError
from app.core.logging import get_logger
from app.integrations.data_network.base import (
    CanonicalSoil,
    DataProvider,
    FreshnessState,
    ProvenanceMetadata,
    QualityStatus,
)
from app.integrations.data_network.normalizer import UnitNormalizer
from app.integrations.data_network.quality_service import DataQualityService
from app.models.soil import SoilObservation, SoilProfile

logger = get_logger("bhoomi.datanetwork.shc")


class SoilHealthCardProvider(DataProvider):
    name = "Soil Health Card"
    data_type = "soil"
    country_scope = "India"
    region_scope = None
    is_fallback = False

    def __init__(self) -> None:
        self.base_url = getattr(settings, "SHC_API_BASE_URL", None)
        self.api_key = getattr(settings, "SHC_API_KEY", None)
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
            "base_url": self.base_url or "https://soilhealth.dac.gov.in/api (unconfigured)",
            "message": "Soil Health Card API operational" if configured else "SHC portal credentials required for live programmatic soil test synchronization",
        }

    def discover_capabilities(self) -> dict:
        return {
            "parameters": [
                "ph", "electrical_conductivity", "organic_carbon",
                "nitrogen", "phosphorus", "potassium",
                "sulfur", "zinc", "boron", "iron", "manganese", "copper"
            ],
            "measurement_type": "laboratory_soil_test",
            "update_frequency_days": 365,
            "license": "Government of India / Department of Agriculture & Farmers Welfare",
            "terms_url": "https://soilhealth.dac.gov.in/",
        }

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    def _request(self, endpoint: str, params: dict) -> dict:
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        with httpx.Client(timeout=settings.AI_REQUEST_TIMEOUT_SECONDS) as client:
            resp = client.get(f"{self.base_url}{endpoint}", params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()

    def fetch(self, farm_id: str, survey_number: Optional[str] = None, **kwargs) -> dict:
        if not self.connect():
            raise ProviderUnavailableError("Soil Health Card provider is not configured (missing SHC_API_KEY).")
        try:
            return self._request(f"/cards/by-farm/{farm_id}", {"survey_number": survey_number})
        except httpx.HTTPError as exc:
            logger.warning("shc_fetch_failed", error=str(exc))
            raise ProviderUnavailableError(f"Soil Health Card portal unreachable: {exc}") from exc

    def normalize(self, raw_data: dict) -> CanonicalSoil:
        conversions = []

        def _norm_nutr(field_name: str, canonical_name: str, default_unit: str):
            val = raw_data.get(field_name)
            if val is None:
                return None
            norm, conv = UnitNormalizer.normalize_soil_nutrient(float(val), canonical_name, raw_data.get(f"{field_name}_unit", default_unit))
            if conv:
                conversions.append(conv)
            return norm

        n_val = _norm_nutr("nitrogen", "nitrogen", "kg/ha")
        p_val = _norm_nutr("phosphorus", "phosphorus", "kg/ha")
        k_val = _norm_nutr("potassium", "potassium", "kg/ha")
        oc_val = _norm_nutr("organic_carbon", "organic_carbon", "%")
        ec_val = _norm_nutr("electrical_conductivity", "electrical_conductivity", "dS/m")
        s_val = _norm_nutr("sulfur", "sulfur", "ppm")
        zn_val = _norm_nutr("zinc", "zinc", "ppm")
        b_val = _norm_nutr("boron", "boron", "ppm")
        fe_val = _norm_nutr("iron", "iron", "ppm")
        mn_val = _norm_nutr("manganese", "manganese", "ppm")
        cu_val = _norm_nutr("copper", "copper", "ppm")

        sample_date = None
        sdate_raw = raw_data.get("sample_date")
        if sdate_raw:
            try:
                sample_date = date.fromisoformat(sdate_raw) if isinstance(sdate_raw, str) else sdate_raw
            except Exception:
                pass

        freshness, age_hours = DataQualityService.evaluate_freshness("soil", sample_date)

        provenance = ProvenanceMetadata(
            provider_name=self.name,
            source_dataset="National_Soil_Health_Card_Registry",
            external_id=raw_data.get("card_number") or raw_data.get("sample_id"),
            observed_at=datetime.combine(sample_date, datetime.min.time(), tzinfo=timezone.utc) if sample_date else None,
            license="Government of India / DA&FW",
            terms_url="https://soilhealth.dac.gov.in/",
            attribution="Soil Health Card Portal, Ministry of Agriculture & Farmers Welfare",
            quality_score=0.99,
            freshness=freshness,
            data_age_hours=age_hours,
        )

        sample = CanonicalSoil(
            ph=float(raw_data["ph"]) if raw_data.get("ph") is not None else None,
            nitrogen_kg_ha=n_val,
            phosphorus_kg_ha=p_val,
            potassium_kg_ha=k_val,
            organic_carbon_pct=oc_val,
            electrical_conductivity_ds_m=ec_val,
            sulfur_ppm=s_val,
            zinc_ppm=zn_val,
            boron_ppm=b_val,
            iron_ppm=fe_val,
            manganese_ppm=mn_val,
            copper_ppm=cu_val,
            moisture_pct=float(raw_data["moisture"]) if raw_data.get("moisture") is not None else None,
            moisture_source_type="lab",  # Strictly lab source
            sample_date=sample_date,
            source="soil_health_card",
            freshness=freshness,
            provenance=provenance,
            conversions=conversions,
        )

        quality_status, _ = DataQualityService.validate_soil(sample)
        sample.quality = quality_status
        return sample

    def validate(self, data: CanonicalSoil) -> tuple[bool, list[str]]:
        status, issues = DataQualityService.validate_soil(data)
        return status != QualityStatus.INVALID, issues

    def store(self, db, data: CanonicalSoil, farm_id=None) -> SoilObservation:
        if not farm_id:
            raise ValueError("farm_id required to store soil observation")

        # 1. Update/create SoilProfile (latest snapshot)
        profile = db.query(SoilProfile).filter(SoilProfile.farm_id == farm_id).first()
        if profile is None:
            profile = SoilProfile(farm_id=farm_id)
            db.add(profile)
        profile.ph = data.ph
        profile.nitrogen = data.nitrogen_kg_ha
        profile.phosphorus = data.phosphorus_kg_ha
        profile.potassium = data.potassium_kg_ha
        profile.organic_carbon = data.organic_carbon_pct
        profile.electrical_conductivity = data.electrical_conductivity_ds_m
        profile.sulfur = data.sulfur_ppm
        profile.zinc = data.zinc_ppm
        profile.boron = data.boron_ppm
        profile.iron = data.iron_ppm
        profile.manganese = data.manganese_ppm
        profile.copper = data.copper_ppm
        profile.moisture = data.moisture_pct
        profile.source = data.source
        profile.sample_date = data.sample_date

        # 2. Append to SoilObservation time-series log
        obs = SoilObservation(
            farm_id=farm_id,
            ph=data.ph,
            nitrogen=data.nitrogen_kg_ha,
            phosphorus=data.phosphorus_kg_ha,
            potassium=data.potassium_kg_ha,
            organic_carbon=data.organic_carbon_pct,
            electrical_conductivity=data.electrical_conductivity_ds_m,
            sulfur=data.sulfur_ppm,
            zinc=data.zinc_ppm,
            boron=data.boron_ppm,
            iron=data.iron_ppm,
            manganese=data.manganese_ppm,
            copper=data.copper_ppm,
            moisture=data.moisture_pct,
            source=data.source,
            freshness_status=data.freshness.value,
            quality_status=data.quality.value,
            external_id=data.provenance.external_id if data.provenance else None,
            sample_date=data.sample_date,
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
