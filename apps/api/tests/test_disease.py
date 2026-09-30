import io

import pytest
from PIL import Image

FARM_PAYLOAD = {
    "name": "Disease Test Farm",
    "state": "Tamil Nadu",
    "district": "Salem",
    "latitude": 11.6,
    "longitude": 78.1,
    "area_hectares": 1.5,
    "current_crop": "rice",
}


def _make_image_bytes(fmt="JPEG"):
    img = Image.new("RGB", (150, 150), color=(60, 130, 50))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def test_disease_analyze_end_to_end(client, auth_headers):
    farm_id = client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=auth_headers).json()["id"]
    files = {"image": ("leaf.jpg", _make_image_bytes(), "image/jpeg")}
    resp = client.post("/api/v1/disease/analyze", data={"farm_id": farm_id, "crop": "rice"}, files=files, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "possible_disease" in body
    assert 0 <= body["confidence"] <= 1
    assert body["is_dev_model"] is True
    assert len(body["limitations"]) > 0
    # Must never claim a confirmed diagnosis.
    assert "confirmed" not in body["possible_disease"].lower()


def test_disease_scan_is_persisted_in_history(client, auth_headers):
    farm_id = client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=auth_headers).json()["id"]
    files = {"image": ("leaf.jpg", _make_image_bytes(), "image/jpeg")}
    client.post("/api/v1/disease/analyze", data={"farm_id": farm_id}, files=files, headers=auth_headers)
    resp = client.get(f"/api/v1/disease/history/{farm_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_disease_rejects_unsupported_file_type(client, auth_headers):
    farm_id = client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=auth_headers).json()["id"]
    files = {"image": ("leaf.txt", b"not an image", "text/plain")}
    resp = client.post("/api/v1/disease/analyze", data={"farm_id": farm_id}, files=files, headers=auth_headers)
    assert resp.status_code == 422


def test_disease_rejects_corrupt_image_bytes(client, auth_headers):
    farm_id = client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=auth_headers).json()["id"]
    files = {"image": ("leaf.jpg", b"\xff\xd8\xff\xe0not-a-real-jpeg", "image/jpeg")}
    resp = client.post("/api/v1/disease/analyze", data={"farm_id": farm_id}, files=files, headers=auth_headers)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Production gate: an unvalidated classifier must never be served as a
# diagnosis, and a configuration string must not be able to bypass that.
# ---------------------------------------------------------------------------

def test_production_refuses_unvalidated_disease_model(monkeypatch):
    from app.core.config import settings
    from app.core.exceptions import ProviderUnavailableError
    from app.services.disease_service import DiseaseService

    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "DISEASE_MODEL_PROVIDER", "heuristic")
    with pytest.raises(ProviderUnavailableError):
        DiseaseService()._assert_model_available()


def test_production_gate_cannot_be_bypassed_by_provider_name(monkeypatch):
    """Naming a provider that does not exist must not unlock the feature.

    The old gate compared the configured string against a deny-list, so any
    unrecognised name fell through to the heuristic and was served in
    production as if it were a real model.
    """
    from app.core.config import settings
    from app.core.exceptions import ProviderUnavailableError
    from app.services.disease_service import DiseaseService

    for name in ("plantvillage", "validated-model", "nvidia-vision", "OPENAI"):
        monkeypatch.setattr(settings, "APP_ENV", "production")
        monkeypatch.setattr(settings, "DISEASE_MODEL_PROVIDER", name)
        with pytest.raises(ProviderUnavailableError):
            DiseaseService()._assert_model_available()


def test_production_startup_validation_rejects_unvalidated_model():
    from app.core.config import Settings

    base = {
        "APP_ENV": "production",
        "DEBUG": False,
        "JWT_SECRET_KEY": "x" * 40,
        "DATABASE_URL": "postgresql+psycopg://u:p@db:5432/bhoomi",
        "REDIS_URL": "redis://cache:6379/0",
        "CORS_ORIGINS": "https://bhoomi.example",
        "SATELLITE_PROVIDER": "none",
    }
    for name in ("heuristic", "plantvillage", "not-a-real-provider"):
        problems = Settings(**{**base, "DISEASE_MODEL_PROVIDER": name}).validate_for_startup()
        assert any("DISEASE_MODEL_PROVIDER" in p for p in problems), name

    # "none" means the feature is simply off, which is allowed.
    assert Settings(**{**base, "DISEASE_MODEL_PROVIDER": "none"}).validate_for_startup() == []


def test_unvalidated_model_never_claims_validation_in_limitations():
    from app.integrations.disease.heuristic_provider import HeuristicDiseaseModelProvider
    from app.services.disease_service import _limitations

    text = " ".join(_limitations(HeuristicDiseaseModelProvider()))
    assert "development-stage" in text
    assert HeuristicDiseaseModelProvider.is_validated is False
