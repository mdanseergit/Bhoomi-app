FARM_PAYLOAD = {
    "name": "Test Farm 01",
    "state": "Tamil Nadu",
    "district": "Salem",
    "latitude": 11.66,
    "longitude": 78.14,
    "area_hectares": 4.5,
    "irrigation_type": "drip",
    "current_crop": "rice",
    "previous_crop": "groundnut",
}


def test_create_and_get_farm(client, auth_headers):
    resp = client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    farm = resp.json()
    assert farm["name"] == "Test Farm 01"
    assert farm["latitude"] == 11.66

    get_resp = client.get(f"/api/v1/farms/{farm['id']}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == farm["id"]


def test_list_farms_scoped_to_owner(client, auth_headers):
    client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=auth_headers)
    resp = client.get("/api/v1/farms", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_update_farm(client, auth_headers):
    create = client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=auth_headers)
    farm_id = create.json()["id"]
    resp = client.patch(f"/api/v1/farms/{farm_id}", json={"crop_stage": "flowering"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["crop_stage"] == "flowering"


def test_delete_farm_soft_deletes(client, auth_headers):
    create = client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=auth_headers)
    farm_id = create.json()["id"]
    resp = client.delete(f"/api/v1/farms/{farm_id}", headers=auth_headers)
    assert resp.status_code == 204
    get_resp = client.get(f"/api/v1/farms/{farm_id}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_other_farmer_cannot_access_farm(client, auth_headers):
    create = client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=auth_headers)
    farm_id = create.json()["id"]

    from app.main import app  # noqa
    import app.core.database as dbmod  # noqa

    other = client_module_login(client)
    resp = client.get(f"/api/v1/farms/{farm_id}", headers=other)
    assert resp.status_code == 403


import uuid

def client_module_login(client):
    unique_email = f"other.farmer.{uuid.uuid4().hex[:6]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Other Farmer", "email": unique_email, "password": "password123", "role": "farmer"},
    )
    assert reg.status_code == 200, reg.text
    login = client.post("/api/v1/auth/login", json={"email": unique_email, "password": "password123"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_invalid_farm_payload_rejected(client, auth_headers):
    bad_payload = {**FARM_PAYLOAD, "latitude": 200}  # out of range
    resp = client.post("/api/v1/farms", json=bad_payload, headers=auth_headers)
    assert resp.status_code == 422
