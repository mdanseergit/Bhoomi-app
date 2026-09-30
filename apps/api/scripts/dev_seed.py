"""
Development-only database seed script. NOT part of the application package.

This module creates FICTIONAL data (sample users, farms, soil, weather,
satellite, advisories, disease scans, state nodes and cooperation models) that
exists purely to make local development convenient. None of it is real. It is
therefore **refused outright when APP_ENV=production**, so it can never
contaminate a production database, and it is never invoked on application
startup or by any test.

For local use only:

    APP_ENV=development python -m scripts.dev_seed

Production databases are created purely by Alembic migrations, which build
schema/indexes/extensions only and insert no rows.
"""
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Allow running as `python -m scripts.dev_seed` from the API root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.advisory import Advisory, AdvisoryType, ReviewStatus, Severity
from app.models.cooperation import ModelRegistryEntry, StateDataset, StateNode
from app.models.crop import CropVariety
from app.models.disease import DiseaseModel, DiseaseScan
from app.models.farm import Farm
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.satellite import SatelliteObservation
from app.models.soil import SoilProfile
from app.models.user import Role, User
from app.models.weather import WeatherObservation
from app.services.embedding_service import EmbeddingService

logger = get_logger("bhoomi.seed")
random.seed(7)


def assert_not_production() -> None:
    """Hard stop so fictional demo data can never be written to production."""
    if settings.is_production:
        raise SystemExit(
            "Refusing to run the development seed script with APP_ENV=production. "
            "This module creates fictional sample data and must never touch a "
            "production database."
        )


def _get_or_create_user(db, *, full_name, email, password, role, state=None) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user:
        return user
    user = User(full_name=full_name, email=email, password_hash=hash_password(password), role=role, state=state)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _get_or_create_state_node(db, *, state, node_id, display_name, crops, status="online") -> StateNode:
    node = db.query(StateNode).filter(StateNode.state == state).first()
    if node:
        return node
    node = StateNode(
        state=state,
        node_id=node_id,
        display_name=display_name,
        status=status,
        supported_crops=crops,
        is_demo=True,
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


def seed() -> None:
    assert_not_production()
    db = SessionLocal()
    try:
        logger.info("seed_started")

        # ---- Users -------------------------------------------------------
        farmer = _get_or_create_user(db, full_name="Mohammed Iqbal", email="farmer@bhoomi.dev", password="password123", role=Role.FARMER, state="Tamil Nadu")
        agronomist = _get_or_create_user(db, full_name="Dr. Kavitha Rao", email="agronomist@bhoomi.dev", password="password123", role=Role.AGRONOMIST, state="Tamil Nadu")
        tn_admin = _get_or_create_user(db, full_name="Tamil Nadu State Admin", email="tnadmin@bhoomi.dev", password="password123", role=Role.STATE_ADMIN, state="Tamil Nadu")
        ka_admin = _get_or_create_user(db, full_name="Karnataka State Admin", email="kaadmin@bhoomi.dev", password="password123", role=Role.STATE_ADMIN, state="Karnataka")
        kl_admin = _get_or_create_user(db, full_name="Kerala State Admin", email="kladmin@bhoomi.dev", password="password123", role=Role.STATE_ADMIN, state="Kerala")
        platform_admin = _get_or_create_user(db, full_name="BHOOMI Platform Admin", email="admin@bhoomi.dev", password="password123", role=Role.PLATFORM_ADMIN)

        # ---- State cooperation nodes (3 states, section 63/27) -----------
        tn_node = _get_or_create_state_node(db, state="Tamil Nadu", node_id="tn-node-01", display_name="Tamil Nadu Agriculture Node", crops=["rice", "sugarcane", "cotton"])
        ka_node = _get_or_create_state_node(db, state="Karnataka", node_id="ka-node-01", display_name="Karnataka Agriculture Node", crops=["ragi", "maize", "cotton"])
        kl_node = _get_or_create_state_node(db, state="Kerala", node_id="kl-node-01", display_name="Kerala Agriculture Node", crops=["rice", "banana", "pepper"], status="offline")

        # ---- Crop varieties (3 crops) -------------------------------------
        if db.query(CropVariety).count() == 0:
            db.add_all([
                CropVariety(crop="rice", variety_name="ADT-45", duration_days=135, recommended_states="Tamil Nadu,Kerala"),
                CropVariety(crop="ragi", variety_name="GPU-28", duration_days=110, recommended_states="Karnataka"),
                CropVariety(crop="rice", variety_name="Jyothi", duration_days=125, recommended_states="Kerala"),
            ])
            db.commit()

        # ---- Farms (3 farms across 3 states) ------------------------------
        farms_spec = [
            dict(user_id=farmer.id, name="Salem Farm 01", state="Tamil Nadu", district="Salem", taluk="Salem", village="Kondalampatti",
                 latitude=11.6643, longitude=78.1460, area_hectares=5.02, soil_type="red_loam", irrigation_type="drip",
                 water_source="borewell", current_crop="rice", crop_variety="ADT-45", crop_stage="vegetative", previous_crop="groundnut"),
            dict(user_id=farmer.id, name="Mysuru Millet Farm", state="Karnataka", district="Mysuru", taluk="Mysuru", village="Varuna",
                 latitude=12.2958, longitude=76.6394, area_hectares=3.4, soil_type="red_sandy", irrigation_type="rainfed",
                 water_source="rain", current_crop="ragi", crop_variety="GPU-28", crop_stage="tillering", previous_crop="maize"),
            dict(user_id=farmer.id, name="Palakkad Paddy Farm", state="Kerala", district="Palakkad", taluk="Palakkad", village="Kollengode",
                 latitude=10.7867, longitude=76.6548, area_hectares=2.1, soil_type="alluvial", irrigation_type="canal",
                 water_source="canal", current_crop="rice", crop_variety="Jyothi", crop_stage="flowering", previous_crop="rice"),
        ]
        farms: list[Farm] = []
        for spec in farms_spec:
            existing = db.query(Farm).filter(Farm.name == spec["name"], Farm.user_id == spec["user_id"]).first()
            if existing:
                farms.append(existing)
                continue
            from geoalchemy2.shape import from_shape
            from shapely.geometry import Point

            farm = Farm(**spec)
            farm.location = from_shape(Point(spec["longitude"], spec["latitude"]), srid=4326)
            db.add(farm)
            db.commit()
            db.refresh(farm)
            farms.append(farm)

        # ---- Soil profiles --------------------------------------------------
        soil_specs = [
            dict(ph=6.8, nitrogen=180, phosphorus=22, potassium=140, organic_carbon=0.42, moisture=38),
            dict(ph=5.9, nitrogen=140, phosphorus=15, potassium=110, organic_carbon=0.58, moisture=18),
            dict(ph=6.2, nitrogen=200, phosphorus=28, potassium=160, organic_carbon=0.81, moisture=52),
        ]
        for farm, spec in zip(farms, soil_specs):
            if db.query(SoilProfile).filter(SoilProfile.farm_id == farm.id).first():
                continue
            db.add(SoilProfile(farm_id=farm.id, source="seed", sample_date=date.today() - timedelta(days=20), **spec))
        db.commit()

        # ---- Historical weather observations (14 days per farm) ------------
        for farm in farms:
            if db.query(WeatherObservation).filter(WeatherObservation.farm_id == farm.id).count() > 0:
                continue
            for i in range(14, 0, -1):
                db.add(WeatherObservation(
                    farm_id=farm.id,
                    temperature=round(27 + random.uniform(-3, 6), 1),
                    humidity=round(55 + random.uniform(-10, 20), 1),
                    rainfall=round(max(0, random.uniform(-2, 12)), 1),
                    wind_speed=round(6 + random.uniform(0, 10), 1),
                    weather_condition=random.choice(["Clear", "Partly cloudy", "Cloudy", "Light rain"]),
                    warning_level="none",
                    source="seed",
                    observed_at=datetime.now(timezone.utc) - timedelta(days=i),
                ))
        db.commit()

        # ---- Satellite observations handled by SatelliteService.sync_farm ----
        from app.services.satellite_service import SatelliteService

        sat_service = SatelliteService()
        for farm in farms:
            sat_service.sync_farm(db, farm, days=30)

        # ---- Disease models + example scans ---------------------------------
        if db.query(DiseaseModel).count() == 0:
            db.add(DiseaseModel(name="BHOOMI Crop Doctor Heuristic Baseline", version="0.1", architecture="heuristic-baseline",
                                 crop_scope="general", is_dev_model=True, accuracy_estimate=None, status="active"))
            db.commit()

        if db.query(DiseaseScan).count() == 0:
            examples = [
                dict(farm=farms[0], crop="rice", possible_disease="leaf_spot", confidence=0.81, severity="moderate"),
                dict(farm=farms[1], crop="ragi", possible_disease="rust", confidence=0.63, severity="moderate"),
                dict(farm=farms[2], crop="rice", possible_disease="healthy", confidence=0.7, severity="none"),
            ]
            for ex in examples:
                db.add(DiseaseScan(
                    farm_id=ex["farm"].id, user_id=farmer.id, image_path="seed/placeholder.jpg", crop=ex["crop"],
                    possible_disease=ex["possible_disease"], confidence=ex["confidence"], severity=ex["severity"],
                    top_k=[{"class": ex["possible_disease"], "confidence": ex["confidence"]}],
                    recommended_actions=["Monitor closely.", "Consult an agricultural officer if symptoms spread."],
                    limitations=["Seeded development example record."],
                ))
            db.commit()

        # ---- Advisories (>=5) -------------------------------------------------
        if db.query(Advisory).count() == 0:
            adv_specs = [
                dict(farm=farms[0], type=AdvisoryType.IRRIGATION, severity=Severity.MODERATE, title="Delay irrigation for 1-2 days",
                     summary="Rain is likely soon, so you can delay irrigation and avoid overwatering."),
                dict(farm=farms[0], type=AdvisoryType.WEATHER, severity=Severity.LOW, title="Monitor drainage after rainfall",
                     summary="Check field drainage paths so water does not pool around root zones."),
                dict(farm=farms[1], type=AdvisoryType.SOIL, severity=Severity.MODERATE, title="Organic carbon is below target",
                     summary="Consider green manure or compost application ahead of the next sowing cycle."),
                dict(farm=farms[1], type=AdvisoryType.CROP, severity=Severity.LOW, title="Vegetation is stable",
                     summary="NDVI trend is flat; no unusual vegetation stress detected this week."),
                dict(farm=farms[2], type=AdvisoryType.CLIMATE, severity=Severity.HIGH, title="Heat stress risk is elevated",
                     summary="Temperatures are high enough to stress paddy at flowering stage; irrigate during cooler hours."),
            ]
            for spec in adv_specs:
                db.add(Advisory(
                    farm_id=spec["farm"].id, type=spec["type"], severity=spec["severity"], title=spec["title"],
                    summary=spec["summary"], actions=[{"title": spec["title"], "priority": "medium", "reason": "Seeded development example."}],
                    evidence=[{"source": "seed", "value": "n/a", "timestamp": datetime.now(timezone.utc).isoformat()}],
                    source_references=[{"source": "seed_data", "authority": "BHOOMI development seed"}],
                    confidence=0.6, generated_by="rule_engine", review_status=ReviewStatus.AUTO_APPROVED,
                ))
            db.commit()

        # ---- Cooperation: model registry (5 demo models) ---------------------
        if db.query(ModelRegistryEntry).count() == 0:
            model_specs = [
                dict(name="Rice Disease Model", publisher=ka_node, version="v2.1", model_type="disease_classification", crop="rice", status="published", visibility="shared", accuracy=0.86),
                dict(name="Drought Risk Model", publisher=tn_node, version="v1.4", model_type="risk", crop="general", status="published", visibility="shared", accuracy=0.79),
                dict(name="Soil Stress Model", publisher=kl_node, version="v1.0", model_type="soil", crop="general", status="pending_review", visibility="state_only", accuracy=0.71),
                dict(name="Ragi Yield Estimator", publisher=ka_node, version="v1.2", model_type="yield", crop="ragi", status="published", visibility="shared", accuracy=0.74),
                dict(name="Cotton Pest Alert Model", publisher=tn_node, version="v0.9", model_type="disease_classification", crop="cotton", status="draft", visibility="state_only", accuracy=None),
            ]
            for spec in model_specs:
                db.add(ModelRegistryEntry(
                    name=spec["name"], description=f"BHOOMI cooperative demo model published by {spec['publisher'].display_name}.",
                    publisher_state_node_id=spec["publisher"].id, version=spec["version"], model_type=spec["model_type"],
                    crop=spec["crop"], supported_regions=[spec["publisher"].state], accuracy=spec["accuracy"],
                    training_dataset_description="Synthetic/development dataset for demonstration purposes only.",
                    visibility=spec["visibility"], status=spec["status"], is_demo=True,
                ))
            db.commit()

        if db.query(StateDataset).count() == 0:
            db.add_all([
                StateDataset(state_node_id=tn_node.id, name="TN Soil Nutrient Samples (demo)", record_count=1200, visibility="shared"),
                StateDataset(state_node_id=ka_node.id, name="Karnataka Millet Yield Records (demo)", record_count=860, visibility="shared"),
                StateDataset(state_node_id=kl_node.id, name="Kerala Rainfall Archive (demo)", record_count=430, visibility="state_only"),
            ])
            db.commit()

        # ---- Knowledge base (RAG) ---------------------------------------------
        if db.query(KnowledgeDocument).count() == 0:
            embedder = EmbeddingService()
            docs = [
                dict(title="General Rice Crop Management Guide (demo)", authority="BHOOMI Reference Library", crop="rice", state=None,
                     content="Rice grows best with consistent water management during the vegetative stage. Avoid water stress during flowering. Organic carbon above 0.75% generally supports better soil resilience."),
                dict(title="Ragi (Finger Millet) Cultivation Notes (demo)", authority="BHOOMI Reference Library", crop="ragi", state="Karnataka",
                     content="Ragi is drought tolerant and suited to rainfed conditions common in parts of Karnataka. Crop rotation with legumes can improve soil nitrogen over time."),
                dict(title="Soil Organic Carbon and Long-Term Resilience (demo)", authority="BHOOMI Reference Library", crop=None, state=None,
                     content="Soil organic carbon is a key indicator of long-term soil health. Maintaining organic matter through crop residues, compost, or green manure helps buffer against climate variability."),
            ]
            for doc in docs:
                document = KnowledgeDocument(title=doc["title"], source="BHOOMI seeded reference (development)", authority=doc["authority"],
                                              state=doc["state"], crop=doc["crop"], language="en", version="v1")
                db.add(document)
                db.commit()
                db.refresh(document)
                vector = embedder.embed([doc["content"]])[0]
                db.add(KnowledgeChunk(document_id=document.id, chunk_index=0, content=doc["content"], embedding=vector))
            db.commit()

        logger.info("seed_completed", farms=len(farms))
        print("BHOOMI development seed completed.")
        print("Login as farmer:      farmer@bhoomi.dev / password123")
        print("Login as agronomist:  agronomist@bhoomi.dev / password123")
        print("Login as TN state admin: tnadmin@bhoomi.dev / password123")
        print("Login as platform admin: admin@bhoomi.dev / password123")
    finally:
        db.close()


if __name__ == "__main__":
    assert_not_production()
    seed()
