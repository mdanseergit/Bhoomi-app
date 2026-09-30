import io

FARM_PAYLOAD = {
    "name": "Soil Test Farm",
    "state": "Tamil Nadu",
    "district": "Salem",
    "latitude": 11.6,
    "longitude": 78.1,
    "area_hectares": 2.0,
}


def _create_farm(client, headers):
    resp = client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=headers)
    return resp.json()["id"]


def test_soil_upsert_and_get(client, auth_headers):
    farm_id = _create_farm(client, auth_headers)
    resp = client.put(f"/api/v1/soil/{farm_id}", json={"ph": 6.5, "organic_carbon": 0.6, "source": "manual"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["ph"] == 6.5

    get_resp = client.get(f"/api/v1/soil/{farm_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["organic_carbon"] == 0.6


def test_soil_csv_import(client, auth_headers):
    farm_id = _create_farm(client, auth_headers)
    csv_content = "ph,nitrogen,phosphorus,potassium,organic_carbon\n6.8,180,22,140,0.55\n"
    files = {"file": ("soil.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    resp = client.post(f"/api/v1/soil/{farm_id}/import", files=files, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ph"] == 6.8
    assert body["source"] == "csv_import"


def test_soil_csv_import_missing_columns_rejected(client, auth_headers):
    farm_id = _create_farm(client, auth_headers)
    csv_content = "foo,bar\n1,2\n"
    files = {"file": ("bad.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    resp = client.post(f"/api/v1/soil/{farm_id}/import", files=files, headers=auth_headers)
    assert resp.status_code == 422


def test_weather_reports_unavailable_instead_of_fabricating(client, auth_headers):
    farm_id = _create_farm(client, auth_headers)
    resp = client.get(f"/api/v1/weather/{farm_id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    # No IMD credentials are configured, so the service must degrade to an
    # explicit "no observation" state rather than inventing a baseline.
    assert body["source"] == "unavailable"
    assert body["temperature_c"] is None
    assert body["humidity_pct"] is None
    assert body["rain_probability_pct"] is None
    assert body["observed_at"] is None


def test_satellite_reports_no_observation_when_provider_unconfigured(client, auth_headers):
    farm_id = _create_farm(client, auth_headers)
    resp = client.get(f"/api/v1/satellite/{farm_id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    # No Earth-observation provider is configured, so there is no NDVI to show.
    # A development dataset must never be presented as a satellite reading.
    assert body["latest"] is None
    assert body["history"] == []
