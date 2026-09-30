FARM_PAYLOAD = {
    "name": "Intelligence Test Farm",
    "state": "Tamil Nadu",
    "district": "Salem",
    "latitude": 11.6,
    "longitude": 78.1,
    "area_hectares": 3.0,
    "current_crop": "rice",
    "previous_crop": "rice",
    "irrigation_type": "rainfed",
}


def test_intelligence_pipeline_end_to_end(client, auth_headers):
    farm_id = client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=auth_headers).json()["id"]
    client.put(f"/api/v1/soil/{farm_id}", json={"ph": 5.2, "organic_carbon": 0.3, "moisture": 10}, headers=auth_headers)

    resp = client.get(f"/api/v1/farms/{farm_id}/intelligence", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()

    health = body["health"]
    assert health["has_data"] is True
    assert 0 <= health["score"] <= 100
    assert len(health["factors"]) > 0
    # No weather provider is configured, so climate risk must be reported as
    # unknown rather than guessed, and it must not be counted as coverage.
    assert health["climate_risk"] == "unknown"
    assert "climate" in health["missing_inputs"]
    assert health["data_coverage"] < 1.0
    assert body["ai_interpretation"] is not None
    assert len(body["advisories"]) > 0


def test_farm_without_any_observations_reports_no_score(client, auth_headers):
    """A brand-new farm has no measurements. BHOOMI must say so instead of
    publishing a score derived from nothing."""
    farm_id = client.post(
        "/api/v1/farms",
        json={**FARM_PAYLOAD, "name": "Bare Field", "current_crop": None, "previous_crop": None},
        headers=auth_headers,
    ).json()["id"]

    resp = client.get(f"/api/v1/farms/{farm_id}/intelligence", headers=auth_headers)
    assert resp.status_code == 200
    health = resp.json()["health"]

    assert health["has_data"] is False
    assert health["score"] is None
    assert health["data_coverage"] == 0.0
    assert set(health["missing_inputs"]) == {"vegetation", "soil", "water", "climate", "crop"}
    assert all(v["score"] is None for v in health["breakdown"].values())


def test_advisories_are_persisted_and_listable(client, auth_headers):
    farm_id = client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=auth_headers).json()["id"]
    client.get(f"/api/v1/farms/{farm_id}/intelligence", headers=auth_headers)
    resp = client.get(f"/api/v1/advisories?farm_id={farm_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) > 0
    for advisory in resp.json():
        assert "summary" in advisory
        assert "evidence" in advisory


def test_repeated_crop_triggers_regenerative_advisory(client, auth_headers):
    """Same crop repeated in consecutive cycles should trigger a rotation
    recommendation per PRODUCT SPEC section 18/75."""
    farm_id = client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=auth_headers).json()["id"]
    resp = client.get(f"/api/v1/farms/{farm_id}/intelligence", headers=auth_headers)
    advisories = resp.json()["advisories"]
    assert any(a["type"] == "regenerative" for a in advisories)
