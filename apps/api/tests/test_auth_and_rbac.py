def test_register_and_login(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Jane Farmer", "email": "jane@example.com", "password": "password123", "role": "farmer"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()

    resp2 = client.post("/api/v1/auth/login", json={"email": "jane@example.com", "password": "password123"})
    assert resp2.status_code == 200

    resp3 = client.post("/api/v1/auth/login", json={"email": "jane@example.com", "password": "wrong-password"})
    assert resp3.status_code == 401


def test_duplicate_registration_conflicts(client):
    payload = {"full_name": "Dup User", "email": "dup@example.com", "password": "password123", "role": "farmer"}
    r1 = client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 200
    r2 = client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409


def test_me_requires_auth(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user(client, auth_headers):
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    # The fixture registers a unique email per test to stay collision-free.
    assert body["email"].startswith("test.farmer.")
    assert body["email"].endswith("@example.com")
    assert body["role"] == "farmer"


def test_farmer_cannot_access_admin_endpoints(client, auth_headers):
    resp = client.get("/api/v1/admin/overview", headers=auth_headers)
    assert resp.status_code == 403


def test_platform_admin_can_access_admin_endpoints(client):
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Admin", "email": "admin.rbac@example.com", "password": "password123", "role": "platform_admin"},
    )
    login = client.post("/api/v1/auth/login", json={"email": "admin.rbac@example.com", "password": "password123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = client.get("/api/v1/admin/overview", headers=headers)
    assert resp.status_code == 200
    assert "users" in resp.json()


def test_invalid_password_too_short_rejected(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Short Pw", "email": "shortpw@example.com", "password": "123", "role": "farmer"},
    )
    assert resp.status_code == 422
