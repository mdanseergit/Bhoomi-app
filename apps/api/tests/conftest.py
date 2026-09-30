import os
import sys
import time
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://bhoomi:bhoomi_dev_pw@localhost:5432/bhoomi_test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("SATELLITE_PROVIDER", "none")
# The bundled disease backend is the development heuristic, which makes no
# network calls and is what the Crop Doctor tests exercise. Production refuses
# it (see DiseaseService._assert_model_available); "none" here would disable
# Crop Doctor entirely and the pipeline tests could not run.
os.environ.setdefault("DISEASE_MODEL_PROVIDER", "heuristic")
os.environ.setdefault("APP_ENV", "development")
os.environ["WEATHER_FALLBACK_PROVIDER"] = "none"
os.environ["REGISTRATION_ALLOWED_ROLES"] = "farmer,agronomist,platform_admin,state_admin,analyst"

# The suite must not depend on a third-party model endpoint: network latency
# and provider outages would make it slow and flaky, and the deterministic
# engine is the path that must stay correct. Set BHOOMI_TEST_LIVE_AI=1 to
# exercise the real provider chain locally.
if os.environ.get("BHOOMI_TEST_LIVE_AI") != "1":
    os.environ["NVIDIA_API_KEY"] = ""

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError

import app.core.config
from app.core.config import get_settings
get_settings.cache_clear()
app.core.config.settings = get_settings()
from app.core.database import Base, SessionLocal, engine
import app.models  # ensure all ORM models are registered
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_redis():
    from app.core.redis_client import get_redis

    get_redis().flushdb()
    yield


def _clean_all_tables() -> None:
    """Remove every application row.

    Rows are deleted child-first and FK triggers are suspended, so this works
    regardless of insertion order. A lock timeout plus retry keeps a
    connection that is still finishing a request from turning cleanup into a
    permanent hang.
    """
    for attempt in range(5):
        try:
            with engine.begin() as conn:
                conn.execute(text("SET LOCAL lock_timeout = '5s'"))
                conn.execute(text("SET LOCAL statement_timeout = '15s'"))
                conn.execute(text("SET LOCAL session_replication_role = 'replica'"))
                for t in reversed(Base.metadata.sorted_tables):
                    if t.name != "spatial_ref_sys":
                        conn.execute(text(f'DELETE FROM "{t.name}"'))
            return
        except (OperationalError, DBAPIError):
            if attempt == 4:
                raise
            time.sleep(0.5 * (attempt + 1))


@pytest.fixture(autouse=True)
def _clean_database():
    """Cleans all application tables before every test."""
    _clean_all_tables()
    yield



@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        # Roll back anything the test left pending so the cleanup fixture does
        # not have to wait on this session's locks.
        session.rollback()
        session.close()


@pytest.fixture(scope="session")
def client():
    # One TestClient (and therefore one ASGI portal) for the whole session.
    # Creating and tearing one down per test leaves request work in flight
    # while the next test's row cleanup runs, which corrupts isolation.
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def registered_farmer(client):
    import uuid
    email = f"test.farmer.{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Test Farmer", "email": email, "password": "password123", "role": "farmer", "state": "Tamil Nadu"},
    )
    assert resp.status_code == 200, resp.text
    tokens = resp.json()
    return tokens


@pytest.fixture()
def auth_headers(registered_farmer):
    return {"Authorization": f"Bearer {registered_farmer['access_token']}"}
