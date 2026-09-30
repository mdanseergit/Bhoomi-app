import uuid
from app.models.cooperation import StateNode


def _register(client, email, role, state):
    unique_email = f"{email.split('@')[0]}.{uuid.uuid4().hex[:6]}@example.com"
    reg = client.post("/api/v1/auth/register", json={"full_name": unique_email, "email": unique_email, "password": "password123", "role": role, "state": state})
    assert reg.status_code == 200, reg.text
    login = client.post("/api/v1/auth/login", json={"email": unique_email, "password": "password123"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _ensure_state_node(db_session, state, node_id):
    node = db_session.query(StateNode).filter(StateNode.state == state).first()
    if node:
        return node
    node = StateNode(state=state, node_id=node_id, display_name=f"{state} Node", status="online", supported_crops=["rice"])
    db_session.add(node)
    db_session.commit()
    db_session.refresh(node)
    return node


def test_full_model_sharing_workflow(client, db_session):
    _ensure_state_node(db_session, "Karnataka", "ka-test-01")
    _ensure_state_node(db_session, "Tamil Nadu", "tn-test-01")

    ka_admin = _register(client, "ka.workflow.admin@example.com", "state_admin", "Karnataka")
    tn_admin = _register(client, "tn.workflow.admin@example.com", "state_admin", "Tamil Nadu")

    # State A (Karnataka) publishes a model -> goes to pending_review
    publish_resp = client.post(
        "/api/v1/models",
        json={"name": "Test Rice Disease Model", "model_type": "disease_classification", "crop": "rice", "version": "v1.0"},
        headers=ka_admin,
    )
    assert publish_resp.status_code == 200, publish_resp.text
    model = publish_resp.json()
    assert model["status"] == "pending_review"

    # Approve for publication -> shared/published
    approve_resp = client.post(f"/api/v1/models/{model['id']}/publish", headers=ka_admin)
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "published"
    assert approve_resp.json()["visibility"] == "shared"

    # State B (Tamil Nadu) requests the model
    request_resp = client.post(f"/api/v1/models/{model['id']}/request", json={"justification": "Need for pilot"}, headers=tn_admin)
    assert request_resp.status_code == 200
    request_id = request_resp.json()["id"]
    assert request_resp.json()["status"] == "requested"

    # Duplicate request should conflict
    dup_resp = client.post(f"/api/v1/models/{model['id']}/request", json={"justification": "dup"}, headers=tn_admin)
    assert dup_resp.status_code == 409

    # State A approves the request
    decide_resp = client.post(f"/api/v1/models/{model['id']}/approve", json={"request_id": request_id, "approve": True}, headers=ka_admin)
    assert decide_resp.status_code == 200
    assert decide_resp.json()["status"] == "approved"


def test_farmer_cannot_publish_models(client, auth_headers):
    resp = client.post("/api/v1/models", json={"name": "X", "model_type": "risk"}, headers=auth_headers)
    assert resp.status_code == 403


def test_cannot_request_unpublished_model(client, db_session):
    node = _ensure_state_node(db_session, "Kerala", "kl-test-01")
    kl_admin = _register(client, "kl.workflow.admin@example.com", "state_admin", "Kerala")
    publish_resp = client.post(
        "/api/v1/models", json={"name": "Draft Model", "model_type": "soil"}, headers=kl_admin
    )
    model_id = publish_resp.json()["id"]
    # still pending_review, not published/shared
    resp = client.post(f"/api/v1/models/{model_id}/request", json={"justification": "test"}, headers=kl_admin)
    assert resp.status_code == 422
