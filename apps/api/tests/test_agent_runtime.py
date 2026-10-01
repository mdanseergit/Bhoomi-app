"""
Tests for the agent runtime.

The bar these set is not "the agent produced text" but "the agent could not
invent a fact, exceed a budget, or read another farmer's data".
"""
import uuid

import pytest

FARM_PAYLOAD = {
    "name": "Agent Test Farm",
    "state": "Tamil Nadu",
    "district": "Salem",
    "latitude": 11.6,
    "longitude": 78.1,
    "area_hectares": 2.5,
    "current_crop": "rice",
    "previous_crop": "rice",
    "irrigation_type": "rainfed",
}


@pytest.fixture()
def farm_id(client, auth_headers) -> str:
    return client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=auth_headers).json()["id"]


# --- registry & permissions ---------------------------------------------


def test_every_registered_tool_declares_scopes_and_schema():
    from app.services.agent import registry
    from app.services.agent.registry import ALL_SCOPES

    specs = registry.list_tools()
    assert specs, "no tools are registered"
    for spec in specs:
        assert spec.required_permissions, f"{spec.name} declares no permissions"
        assert set(spec.required_permissions).issubset(ALL_SCOPES)
        described = spec.describe()
        assert described["input_schema"]["type"] == "object"
        assert described["risk_level"]
        assert spec.summary


def test_farmer_gets_read_scopes_but_no_write_or_approval():
    from app.models.user import Role
    from app.services.agent.permissions import scopes_for_role
    from app.services.agent.registry import SCOPE_ADVISORY_WRITE, SCOPE_ACTION_APPROVE, SCOPE_FARM_READ

    granted = scopes_for_role(Role.FARMER)
    assert SCOPE_FARM_READ in granted
    assert SCOPE_ADVISORY_WRITE not in granted
    assert SCOPE_ACTION_APPROVE not in granted


def test_tool_catalogue_hides_tools_the_caller_cannot_run():
    from app.services.agent import registry
    from app.services.agent.permissions import scopes_for_role
    from app.models.user import Role

    granted = scopes_for_role(Role.FARMER)
    offered = {t["name"] for t in registry.catalogue_for_model(granted)}
    assert "weather_now" in offered
    for entry in registry.catalogue_for_model(granted):
        spec = registry.get(entry["name"])
        assert set(spec.required_permissions).issubset(granted)


def test_intent_classification_and_planning():
    from app.services.agent.loop_runner import classify_intent, plan_tools

    assert classify_intent("will it rain tomorrow?") == "weather"
    assert classify_intent("what is my soil pH") == "soil"
    assert classify_intent("any disease in my crop?") == "disease"
    assert classify_intent("tell me about my farm") == "farm"
    assert classify_intent("what should I do next") == "advisory"

    planned = plan_tools("soil", ["soil_profile", "weather_now"], max_calls=5)
    assert planned == ["soil_profile"]
    # A tool the caller cannot use is never planned, even if the intent wants it.
    assert plan_tools("soil", ["weather_now"], max_calls=5) == []


# --- tool executor -------------------------------------------------------


def test_executor_records_a_successful_call(client, auth_headers, farm_id):
    from app.models.agent import ToolExecution, ToolExecutionStatus
    from app.models.user import User
    from app.models.farm import Farm
    from app.services.agent.executor import ToolExecutor
    from app.services.agent.permissions import scopes_for_role
    from app.services.agent.task_manager import TaskManager
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == client.get("/api/v1/auth/me", headers=auth_headers).json()["email"]).first()
        farm = db.get(Farm, farm_id)
        tasks = TaskManager(db)
        session = tasks.get_or_create_session(user, session_id=None, farm_id=farm_id, language="en")
        task = tasks.create_task(session=session, user=user, query="soil?", language="en")

        executor = ToolExecutor(
            db=db, task=task, user_id=str(user.id), role=user.role.value,
            granted_scopes=scopes_for_role(user.role),
        )
        outcome = executor.run("farm_snapshot", {}, farm=farm)
        assert outcome.ok
        assert outcome.result is not None
        assert outcome.result.available

        db.expire_all()
        rows = db.query(ToolExecution).filter(ToolExecution.task_id == task.id).all()
        assert len(rows) == 1
        assert rows[0].status == ToolExecutionStatus.SUCCEEDED
        assert rows[0].tool_name == "farm_snapshot"
        assert rows[0].duration_ms is not None
        assert rows[0].output_payload["summary"]


def test_executor_denies_a_tool_the_role_lacks(client, auth_headers, farm_id):
    """A tool whose scopes exceed the caller's grants is refused before the
    handler runs, and the refusal is recorded rather than hidden."""
    from app.models.agent import ToolExecution, ToolExecutionStatus
    from app.models.user import User
    from app.models.farm import Farm
    from app.services.agent.executor import ToolExecutor
    from app.services.agent.task_manager import TaskManager
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == client.get("/api/v1/auth/me", headers=auth_headers).json()["email"]).first()
        farm = db.get(Farm, farm_id)
        tasks = TaskManager(db)
        session = tasks.get_or_create_session(user, session_id=None, farm_id=farm_id, language="en")
        task = tasks.create_task(session=session, user=user, query="soil?", language="en")

        # Only the farm read scope is granted, so any tool needing more is denied.
        executor = ToolExecutor(
            db=db, task=task, user_id=str(user.id), role=user.role.value,
            granted_scopes={"farm:read"},
        )
        outcome = executor.run("soil_profile", {}, farm=farm)
        assert not outcome.ok
        assert outcome.status == ToolExecutionStatus.DENIED
        assert "soil:read" in (outcome.reason or "")

        db.expire_all()
        row = db.query(ToolExecution).filter(ToolExecution.task_id == task.id).first()
        assert row.status == ToolExecutionStatus.DENIED
        assert row.error_message


def test_executor_rejects_unknown_tool_and_bad_arguments(client, auth_headers, farm_id):
    from app.models.agent import ToolExecutionStatus
    from app.models.user import User
    from app.models.farm import Farm
    from app.services.agent.executor import ToolExecutor
    from app.services.agent.permissions import scopes_for_role
    from app.services.agent.task_manager import TaskManager
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == client.get("/api/v1/auth/me", headers=auth_headers).json()["email"]).first()
        farm = db.get(Farm, farm_id)
        tasks = TaskManager(db)
        session = tasks.get_or_create_session(user, session_id=None, farm_id=farm_id, language="en")
        task = tasks.create_task(session=session, user=user, query="q", language="en")
        executor = ToolExecutor(
            db=db, task=task, user_id=str(user.id), role=user.role.value,
            granted_scopes=scopes_for_role(user.role),
        )

        unknown = executor.run("definitely_not_a_tool", {})
        assert unknown.status == ToolExecutionStatus.FAILED
        assert "registered" in (unknown.reason or "")

        bad = executor.run("list_advisories", {"limit": 9999})
        assert bad.status == ToolExecutionStatus.FAILED


def test_tool_call_budget_is_enforced(client, auth_headers, farm_id):
    from app.models.user import User
    from app.models.farm import Farm
    from app.services.agent.executor import ToolBudgetExhausted, ToolExecutor
    from app.services.agent.permissions import scopes_for_role
    from app.services.agent.task_manager import TaskManager
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == client.get("/api/v1/auth/me", headers=auth_headers).json()["email"]).first()
        farm = db.get(Farm, farm_id)
        tasks = TaskManager(db)
        session = tasks.get_or_create_session(user, session_id=None, farm_id=farm_id, language="en")
        task = tasks.create_task(session=session, user=user, query="q", language="en")
        task.max_tool_calls = 1
        db.commit()

        executor = ToolExecutor(
            db=db, task=task, user_id=str(user.id), role=user.role.value,
            granted_scopes=scopes_for_role(user.role),
        )
        assert executor.run("farm_snapshot", {}, farm=farm).ok
        with pytest.raises(ToolBudgetExhausted):
            executor.run("farm_snapshot", {}, farm=farm)


def test_repetition_guard_catches_a_loop():
    from app.services.agent.task_manager import RepetitionGuard

    guard = RepetitionGuard(limit=3)
    assert guard.observe("weather_now") == 1
    assert guard.observe("weather_now") == 2
    assert guard.observe("weather_now") == 3
    # A different call resets the consecutive count.
    assert guard.observe("soil_profile") == 1


# --- task lifecycle ------------------------------------------------------


def test_task_lifecycle_and_budget_report(client, auth_headers, farm_id):
    from app.models.agent import AgentPhase, AgentStepStatus, AgentTaskStatus
    from app.models.user import User
    from app.services.agent.task_manager import BudgetExceeded, TaskManager
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == client.get("/api/v1/auth/me", headers=auth_headers).json()["email"]).first()
        tasks = TaskManager(db)
        session = tasks.get_or_create_session(user, session_id=None, farm_id=farm_id, language="en")
        task = tasks.create_task(session=session, user=user, query="how is my farm?", language="en")
        assert task.status == AgentTaskStatus.QUEUED

        tasks.start_task(task)
        assert task.status == AgentTaskStatus.RUNNING

        step = tasks.open_step(task, AgentPhase.OBSERVE, goal="look")
        assert step.step_number == 1
        tasks.close_step(step, summary="observed", status=AgentStepStatus.COMPLETED)

        report = tasks.budget(task)
        assert report.steps_used == 1
        assert report.max_steps >= 1

        # A budget of zero steps must be refused rather than silently allowed.
        task.max_steps = 0
        db.commit()
        with pytest.raises(BudgetExceeded):
            tasks.ensure_can_step(task)
        task.max_steps = 8
        db.commit()

        tasks.complete_task(task, response="answered", confidence=0.7)
        assert task.status == AgentTaskStatus.COMPLETED
        assert task.current_phase == AgentPhase.NOTIFY
        assert task.completed_at is not None

        tasks.fail_task(task, "boom")
        assert task.status == AgentTaskStatus.FAILED
        assert "boom" in task.error_message


def test_session_of_another_user_is_not_reused(client, auth_headers, farm_id):
    from app.models.user import User
    from app.services.agent.task_manager import TaskManager
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == client.get("/api/v1/auth/me", headers=auth_headers).json()["email"]).first()
        tasks = TaskManager(db)
        mine = tasks.get_or_create_session(user, session_id=None, farm_id=farm_id, language="en")
        # Claiming an unknown/foreign id yields a fresh session, never someone
        # else's conversation.
        fresh = tasks.get_or_create_session(user, session_id=str(uuid.uuid4()), farm_id=farm_id, language="en")
        assert str(fresh.id) != str(mine.id)
        again = tasks.get_or_create_session(user, session_id=str(mine.id), farm_id=farm_id, language="en")
        assert str(again.id) == str(mine.id)


def test_memory_is_upserted_per_key(client, auth_headers, farm_id):
    from app.models.agent import AgentMemory
    from app.models.user import User
    from app.services.agent.task_manager import TaskManager
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == client.get("/api/v1/auth/me", headers=auth_headers).json()["email"]).first()
        tasks = TaskManager(db)
        tasks.remember(
            user_id=user.id, farm_id=None, task_id=None, key="pref:crop",
            content={"crop": "rice"}, source="user_statement", confidence=0.9,
        )
        tasks.remember(
            user_id=user.id, farm_id=None, task_id=None, key="pref:crop",
            content={"crop": "millets"}, source="user_correction", confidence=0.95,
        )
        rows = db.query(AgentMemory).filter(AgentMemory.user_id == user.id).all()
        assert len(rows) == 1
        assert rows[0].content == {"crop": "millets"}
        assert rows[0].source == "user_correction"


# --- chat endpoint -------------------------------------------------------


def test_chat_requires_authentication(client):
    assert client.post("/api/v1/agent/chat", json={"message": "hello"}).status_code == 401


def test_chat_answers_from_real_observations(client, auth_headers, farm_id):
    resp = client.post(
        "/api/v1/agent/chat",
        json={"message": "How is my farm doing?", "farm_id": farm_id},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["answer"]
    assert body["task_id"]
    assert body["session_id"]
    assert body["status"] in ("completed", "waiting_for_approval")
    assert 0 <= body["confidence"] <= 1
    # Every phase of the loop is recorded, in order.
    phases = [p["phase"] for p in body["phases"]]
    assert phases[0] == "observe"
    assert "use_tools" in phases
    assert phases[-1] == "notify"
    assert body["tool_calls"], "no tool was called for a farm question"
    called = {c["tool"] for c in body["tool_calls"]}
    assert "farm_snapshot" in called
    assert body["budget"]["max_steps"] >= 1


def test_chat_reports_missing_data_instead_of_inventing_it(client, auth_headers):
    """A farm with no observations must produce an answer that says so, and
    must not contain a fabricated measurement."""
    bare = client.post(
        "/api/v1/farms",
        json={**FARM_PAYLOAD, "name": "Bare Agent Field", "current_crop": None, "previous_crop": None},
        headers=auth_headers,
    ).json()["id"]

    resp = client.post(
        "/api/v1/agent/chat",
        json={"message": "What is the soil pH and current weather?", "farm_id": bare},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["missing_data"], "missing inputs were not reported"
    lowered = body["answer"].lower()
    assert "not" in lowered or "missing" in lowered or "could not" in lowered


def test_chat_rejects_unknown_disabled_tool(client, auth_headers, farm_id):
    resp = client.post(
        "/api/v1/agent/chat",
        json={"message": "hi", "farm_id": farm_id, "disabled_tools": ["drop_database"]},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_chat_honours_disabled_tools(client, auth_headers, farm_id):
    resp = client.post(
        "/api/v1/agent/chat",
        json={
            "message": "How is my farm?",
            "farm_id": farm_id,
            "disabled_tools": ["farm_snapshot", "farm_health"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    called = {c["tool"] for c in resp.json()["tool_calls"]}
    assert "farm_snapshot" not in called
    assert "farm_health" not in called


def test_chat_cannot_read_another_farmers_farm(client, auth_headers, farm_id):
    other = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Other Farmer",
            "email": f"other.{uuid.uuid4().hex[:8]}@example.com",
            "password": "password123",
            "role": "farmer",
        },
    ).json()
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}

    # Reported as not found rather than forbidden, so the endpoint cannot be
    # used to discover that another farmer's farm exists.
    resp = client.post(
        "/api/v1/agent/chat",
        json={"message": "tell me about this farm", "farm_id": farm_id},
        headers=other_headers,
    )
    assert resp.status_code == 404


def test_write_intent_is_flagged_for_approval_not_executed(client, auth_headers, farm_id):
    resp = client.post(
        "/api/v1/agent/chat",
        json={"message": "Please update my irrigation schedule to every 3 days", "farm_id": farm_id},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["requires_approval"] is True
    assert body["status"] == "waiting_for_approval"
    # Nothing was changed on the farm.
    farm = client.get(f"/api/v1/farms/{farm_id}", headers=auth_headers).json()
    assert farm["irrigation_type"] == "rainfed"


def test_task_activity_is_auditable_and_scoped(client, auth_headers, farm_id):
    task = client.post(
        "/api/v1/agent/chat",
        json={"message": "How is my farm?", "farm_id": farm_id},
        headers=auth_headers,
    ).json()

    activity = client.get(f"/api/v1/agent/tasks/{task['task_id']}/activity", headers=auth_headers)
    assert activity.status_code == 200
    body = activity.json()
    assert body["task_id"] == task["task_id"]
    assert len(body["steps"]) >= 5
    assert body["tool_executions"], "no tool execution was recorded"
    for step in body["steps"]:
        assert step["phase"]
        assert step["status"] in ("completed", "failed", "skipped", "started")
        # No hidden reasoning is exposed.
        assert "chain_of_thought" not in step
        assert "reasoning" not in step

    other = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Nosy",
            "email": f"nosy.{uuid.uuid4().hex[:8]}@example.com",
            "password": "password123",
            "role": "farmer",
        },
    ).json()
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    assert client.get(f"/api/v1/agent/tasks/{task['task_id']}/activity", headers=other_headers).status_code == 404


def test_tasks_listing_and_detail(client, auth_headers, farm_id):
    created = client.post(
        "/api/v1/agent/chat",
        json={"message": "soil status?", "farm_id": farm_id},
        headers=auth_headers,
    ).json()

    listed = client.get("/api/v1/agent/tasks", headers=auth_headers)
    assert listed.status_code == 200
    assert any(t["id"] == created["task_id"] for t in listed.json())

    detail = client.get(f"/api/v1/agent/tasks/{created['task_id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["query"] == "soil status?"


def test_tools_endpoint_lists_only_permitted_tools(client, auth_headers):
    resp = client.get("/api/v1/agent/tools", headers=auth_headers)
    assert resp.status_code == 200
    tools = resp.json()
    assert tools
    for tool in tools:
        assert tool["risk_level"] == "read_only"
        assert tool["required_permissions"]


def test_memory_endpoints(client, auth_headers, farm_id):
    # Memory is written from observations, so the farm needs at least one real
    # reading. A farm with no data must leave memory empty rather than record
    # a summary of nothing.
    client.put(
        f"/api/v1/soil/{farm_id}",
        json={"ph": 5.4, "organic_carbon": 0.42, "moisture": 22},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/agent/chat",
        json={"message": "How is my farm?", "farm_id": farm_id},
        headers=auth_headers,
    )
    listed = client.get("/api/v1/agent/memory", headers=auth_headers)
    assert listed.status_code == 200
    memories = listed.json()
    assert memories, "the loop did not remember what it observed"
    assert memories[0]["key"].startswith("farm:")

    deleted = client.delete(f"/api/v1/agent/memory/{memories[0]['id']}", headers=auth_headers)
    assert deleted.status_code == 204
    assert client.get("/api/v1/agent/memory", headers=auth_headers).json() == []


def test_monitor_lifecycle(client, auth_headers, farm_id):
    created = client.post(
        "/api/v1/agent/monitors",
        json={
            "farm_id": farm_id,
            "name": "Rain before irrigation",
            "monitor_type": "weather",
            "condition": {"rain_probability_pct_above": 70},
        },
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    monitor = created.json()
    assert monitor["enabled"] is True
    assert monitor["status"] == "active"

    listed = client.get("/api/v1/agent/monitors", headers=auth_headers)
    assert len(listed.json()) == 1

    toggled = client.patch(f"/api/v1/agent/monitors/{monitor['id']}?enabled=false", headers=auth_headers)
    assert toggled.status_code == 200
    assert toggled.json()["enabled"] is False
    assert toggled.json()["status"] == "paused"


def test_monitor_cannot_be_created_for_another_farmers_farm(client, auth_headers, farm_id):
    other = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Other Monitor",
            "email": f"mon.{uuid.uuid4().hex[:8]}@example.com",
            "password": "password123",
            "role": "farmer",
        },
    ).json()
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    resp = client.post(
        "/api/v1/agent/monitors",
        json={"farm_id": farm_id, "name": "sneaky", "monitor_type": "weather"},
        headers=other_headers,
    )
    assert resp.status_code == 404


def test_alerts_endpoint_is_scoped_to_caller(client, auth_headers):
    resp = client.get("/api/v1/agent/alerts", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_farmer_cannot_decide_approvals(client, auth_headers, farm_id):
    resp = client.post(
        "/api/v1/agent/approvals/00000000-0000-0000-0000-000000000000/decide",
        json={"approve": True},
        headers=auth_headers,
    )
    assert resp.status_code == 403


def test_disabling_every_tool_opts_out_rather_than_re_enabling_all(client, auth_headers, farm_id):
    """A caller who disables all tools asked for no tools, which is different
    from omitting the field (meaning every permitted tool)."""
    permitted = {t["name"] for t in client.get("/api/v1/agent/tools", headers=auth_headers).json()}
    assert permitted

    resp = client.post(
        "/api/v1/agent/chat",
        json={"message": "How is my farm?", "farm_id": farm_id, "disabled_tools": sorted(permitted)},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["tool_calls"] == []
    # The farm record the caller explicitly named is still context, so it stays
    # cited; nothing a tool would have fetched may appear.
    assert {s["domain"] for s in body["sources"]} <= {"Farm profile"}
    # It still answers, but from context only: with no tools permitted it must
    # disclose that it observed nothing rather than invent a reading.
    assert "could not collect" in body["answer"].lower()


def test_session_follows_a_farm_switch(client, auth_headers):
    farms = client.post(
        "/api/v1/farms",
        json={
            "name": "Session Farm A",
            "state": "Tamil Nadu",
            "district": "Salem",
            "latitude": 11.66,
            "longitude": 78.14,
            "area_hectares": 2.0,
        },
        headers=auth_headers,
    ).json()
    other = client.post(
        "/api/v1/farms",
        json={
            "name": "Session Farm B",
            "state": "Karnataka",
            "district": "Mysuru",
            "latitude": 12.3,
            "longitude": 76.6,
            "area_hectares": 3.0,
        },
        headers=auth_headers,
    ).json()

    first = client.post(
        "/api/v1/agent/chat",
        json={"message": "What is my current crop?", "farm_id": farms["id"]},
        headers=auth_headers,
    ).json()

    switched = client.post(
        "/api/v1/agent/chat",
        json={
            "message": "What is my current crop?",
            "farm_id": other["id"],
            "session_id": first["session_id"],
        },
        headers=auth_headers,
    ).json()

    assert switched["session_id"] == first["session_id"]
    task = client.get(f"/api/v1/agent/tasks/{switched['task_id']}", headers=auth_headers).json()
    assert task["farm_id"] == other["id"]


def test_no_farm_selected_is_reported_not_guessed(client, auth_headers):
    """A farm-scoped question with no farm named must say so, not silently read
    whichever farm happened to be first."""
    resp = client.post(
        "/api/v1/agent/chat",
        json={"message": "How is my farm?"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["tool_calls"]
    assert all(call["status"] == "failed" for call in body["tool_calls"])
    assert "farm" in body["answer"].lower()