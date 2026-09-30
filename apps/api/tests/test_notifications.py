from app.models.cooperation import StateNode

FARM_PAYLOAD = {
    "name": "Notification Test Farm",
    "state": "Tamil Nadu",
    "district": "Salem",
    "latitude": 11.6,
    "longitude": 78.1,
    "area_hectares": 3.0,
    "current_crop": "rice",
    "previous_crop": "rice",
}


import uuid

def _register(client, email, role, state):
    unique_email = f"{email.split('@')[0]}.{uuid.uuid4().hex[:6]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"full_name": unique_email, "email": unique_email, "password": "password123", "role": role, "state": state},
    )
    assert reg.status_code == 200, reg.text
    login = client.post("/api/v1/auth/login", json={"email": unique_email, "password": "password123"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _ensure_state_node(db_session, state, node_id):
    node = db_session.query(StateNode).filter(StateNode.state == state).first()
    if node:
        return node
    node = StateNode(
        state=state,
        node_id=node_id,
        display_name=f"{state} Node",
        status="online",
        supported_crops=["rice"],
    )
    db_session.add(node)
    db_session.commit()
    db_session.refresh(node)
    return node


def test_advisory_review_notifies_farm_owner(client, registered_farmer):
    farmer_headers = {"Authorization": f"Bearer {registered_farmer['access_token']}"}
    agronomist_headers = _register(client, "agron.notifications@example.com", "agronomist", "Tamil Nadu")

    farm_id = client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=farmer_headers).json()["id"]
    advisories = client.get(f"/api/v1/farms/{farm_id}/intelligence", headers=farmer_headers).json()["advisories"]
    advisory_id = advisories[0]["id"]

    before = client.get("/api/v1/notifications", headers=farmer_headers).json()
    assert before == []

    review = client.post(f"/api/v1/advisories/{advisory_id}/review?approve=true", headers=agronomist_headers)
    assert review.status_code == 200, review.text

    after = client.get("/api/v1/notifications", headers=farmer_headers).json()
    assert len(after) == 1
    note = after[0]
    assert note["type"] == "advisory_review"
    assert note["severity"] == "info"
    assert advisories[0]["title"] in note["title"]
    assert note["read_at"] is None

    read = client.post(f"/api/v1/notifications/{note['id']}/read", headers=farmer_headers)
    assert read.status_code == 200, read.text
    assert read.json()["read_at"] is not None


def test_rejected_advisory_uses_warning_severity(client, registered_farmer):
    farmer_headers = {"Authorization": f"Bearer {registered_farmer['access_token']}"}
    agronomist_headers = _register(client, "agron.reject@example.com", "agronomist", "Tamil Nadu")

    farm_id = client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=farmer_headers).json()["id"]
    advisory_id = client.get(f"/api/v1/farms/{farm_id}/intelligence", headers=farmer_headers).json()["advisories"][0]["id"]

    review = client.post(f"/api/v1/advisories/{advisory_id}/review?approve=false", headers=agronomist_headers)
    assert review.status_code == 200, review.text
    assert review.json()["review_status"] == "rejected"

    note = client.get("/api/v1/notifications", headers=farmer_headers).json()[0]
    assert note["severity"] == "warning"


def test_reviewer_does_not_notify_self(client, registered_farmer):
    """The agronomist acting on their own farm's advisory should not be notified."""
    agronomist_headers = _register(client, "agron.self@example.com", "agronomist", "Tamil Nadu")
    profile = client.get("/api/v1/auth/me", headers=agronomist_headers).json()

    farm_id = client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=agronomist_headers).json()["id"]
    advisory_id = client.get(f"/api/v1/farms/{farm_id}/intelligence", headers=agronomist_headers).json()["advisories"][0]["id"]

    client.post(f"/api/v1/advisories/{advisory_id}/review?approve=true", headers=agronomist_headers)

    assert client.get("/api/v1/notifications", headers=agronomist_headers).json() == []
    assert profile["id"]


def test_notifications_are_scoped_to_the_owner(client, registered_farmer):
    farmer_headers = {"Authorization": f"Bearer {registered_farmer['access_token']}"}
    other_headers = _register(client, "other.notifications@example.com", "farmer", "Kerala")
    agronomist_headers = _register(client, "agron.scope@example.com", "agronomist", "Tamil Nadu")

    farm_id = client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=farmer_headers).json()["id"]
    advisory_id = client.get(f"/api/v1/farms/{farm_id}/intelligence", headers=farmer_headers).json()["advisories"][0]["id"]
    client.post(f"/api/v1/advisories/{advisory_id}/review?approve=true", headers=agronomist_headers)

    assert len(client.get("/api/v1/notifications", headers=farmer_headers).json()) == 1
    assert client.get("/api/v1/notifications", headers=other_headers).json() == []


def test_cannot_mark_another_users_notification_read(client, registered_farmer):
    farmer_headers = {"Authorization": f"Bearer {registered_farmer['access_token']}"}
    other_headers = _register(client, "other.read@example.com", "farmer", "Kerala")
    agronomist_headers = _register(client, "agron.read@example.com", "agronomist", "Tamil Nadu")

    farm_id = client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=farmer_headers).json()["id"]
    advisory_id = client.get(f"/api/v1/farms/{farm_id}/intelligence", headers=farmer_headers).json()["advisories"][0]["id"]
    client.post(f"/api/v1/advisories/{advisory_id}/review?approve=true", headers=agronomist_headers)

    note = client.get("/api/v1/notifications", headers=farmer_headers).json()[0]
    resp = client.post(f"/api/v1/notifications/{note['id']}/read", headers=other_headers)
    assert resp.status_code == 403
    # ...and the owner's notification is left untouched.
    still_unread = client.get("/api/v1/notifications", headers=farmer_headers).json()[0]
    assert still_unread["read_at"] is None


def test_model_request_decision_notifies_requesting_state(client, db_session):
    _ensure_state_node(db_session, "Karnataka", "ka-notif-01")
    _ensure_state_node(db_session, "Tamil Nadu", "tn-notif-01")

    ka_admin = _register(client, "ka.notif.admin@example.com", "state_admin", "Karnataka")
    tn_admin = _register(client, "tn.notif.admin@example.com", "state_admin", "Tamil Nadu")

    model = client.post(
        "/api/v1/models",
        json={"name": "Notification Model", "model_type": "risk", "crop": "rice", "version": "v1.0"},
        headers=ka_admin,
    ).json()
    client.post(f"/api/v1/models/{model['id']}/publish", headers=ka_admin)

    request_id = client.post(
        f"/api/v1/models/{model['id']}/request",
        json={"justification": "Notification test"},
        headers=tn_admin,
    ).json()["id"]

    assert client.get("/api/v1/notifications", headers=tn_admin).json() == []

    decide = client.post(
        f"/api/v1/models/{model['id']}/approve",
        json={"request_id": request_id, "approve": True},
        headers=ka_admin,
    )
    assert decide.status_code == 200, decide.text

    notes = client.get("/api/v1/notifications", headers=tn_admin).json()
    assert len(notes) == 1
    assert notes[0]["type"] == "model_request"
    assert "Notification Model" in notes[0]["title"]
    # The deciding Karnataka admin is not the requesting state, so is not notified.
    assert client.get("/api/v1/notifications", headers=ka_admin).json() == []
