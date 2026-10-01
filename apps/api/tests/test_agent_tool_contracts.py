"""
Contract tests for the agent's read tools.

The bar these set is not "the tool returned something" but "every registered
read tool can actually be executed, and its payload matches the output schema
it advertises".

That distinction matters because a payload that violates its own declared
schema does not raise at the call site: the executor records the call as
FAILED and the loop moves on. A silently-failing tool looks exactly like a
provider outage from the outside, so every tool is executed here and its
status asserted, rather than trusting that registration alone implies a working
handler.
"""
import pytest

FARM_PAYLOAD = {
    "name": "Contract Test Farm",
    "state": "Tamil Nadu",
    "district": "Salem",
    "latitude": 11.6,
    "longitude": 78.1,
    "area_hectares": 2.5,
    "current_crop": "rice",
    "crop_variety": "Basmati",
    "crop_stage": "vegetative",
    "previous_crop": "rice",
    "irrigation_type": "rainfed",
    "soil_type": "alluvial",
    "water_source": "borewell",
}

# Arguments for the tools that accept any. Every other tool is called with an
# empty object so its own defaults apply.
TOOL_ARGS: dict[str, dict] = {
    "get_soil_health": {},
    "get_crop_health": {},
    "calculate_farm_health": {},
    "analyze_farm": {},
    "search_agricultural_knowledge": {"query": "blight management in rice"},
    "get_model_details": {"model_id": "00000000-0000-0000-0000-000000000000"},
}

# Tools that cannot report anything useful against a farm with no rows to read.
# None are expected to fail any more: a lookup miss is an answer, so each of
# these must return an honest empty state rather than raising.
EXPECTED_EMPTY: dict[str, str] = {
    "get_model_details": "cooperation.shared_model",
}


@pytest.fixture()
def farm(client, auth_headers) -> str:
    return client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=auth_headers).json()["id"]


@pytest.fixture()
def executor_factory(client, auth_headers, farm):
    """Builds a real executor bound to a real task and farm.

    Uses the platform_admin grant so every read tool is reachable: the point of
    these tests is each tool's own contract, not the role matrix (which has its
    own tests).
    """
    from app.core.database import SessionLocal
    from app.models.farm import Farm
    from app.models.user import User
    from app.services.agent.executor import ToolExecutor
    from app.services.agent.permissions import scopes_for_role
    from app.services.agent.registry import ALL_SCOPES
    from app.services.agent.task_manager import TaskManager

    email = client.get("/api/v1/auth/me", headers=auth_headers).json()["email"]

    def _make():
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == email).first()
            tasks = TaskManager(db)
            session = tasks.get_or_create_session(user, session_id=None, farm_id=farm, language="en")
            task = tasks.create_task(session=session, user=user, query="contract check", language="en")
            return (
                ToolExecutor(
                    db=db,
                    task=task,
                    user_id=str(user.id),
                    role=user.role.value,
                    granted_scopes=set(ALL_SCOPES),
                ),
                db.get(Farm, farm),
            )
        except Exception:
            db.close()
            raise

    return _make


def test_irrigation_history_reports_missing_volume_as_unknown_not_zero(client, auth_headers):
    """An unreported applied depth must stay unknown, never read as 0 mm.

    The difference is decision-relevant: "no water applied" and "volume not
    measured" lead to opposite irrigation advice, so the row is kept (it still
    carries moisture) while the total is reported as a floor.
    """
    from datetime import datetime, timedelta, timezone

    from app.core.database import SessionLocal
    from app.models.data_network import WaterObservation

    farm_id = client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=auth_headers).json()["id"]
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        db.add_all(
            [
                WaterObservation(
                    farm_id=farm_id,
                    irrigation_applied_mm=12.0,
                    soil_moisture_pct=41.0,
                    moisture_source_type="sensor",
                    source="test",
                    observed_at=now - timedelta(days=1),
                ),
                # Same window, applied depth unknown.
                WaterObservation(
                    farm_id=farm_id,
                    irrigation_applied_mm=None,
                    soil_moisture_pct=38.0,
                    moisture_source_type="estimated",
                    source="test",
                    observed_at=now - timedelta(days=2),
                ),
            ]
        )
        db.commit()

    from app.core.database import SessionLocal as _S
    from app.models.farm import Farm
    from app.models.user import User
    from app.services.agent.executor import ToolExecutor
    from app.services.agent.registry import ALL_SCOPES
    from app.services.agent.task_manager import TaskManager

    email = client.get("/api/v1/auth/me", headers=auth_headers).json()["email"]
    db = _S()
    try:
        user = db.query(User).filter(User.email == email).first()
        tasks = TaskManager(db)
        session = tasks.get_or_create_session(user, session_id=None, farm_id=farm_id, language="en")
        task = tasks.create_task(session=session, user=user, query="irrigation history", language="en")
        outcome = ToolExecutor(
            db=db,
            task=task,
            user_id=str(user.id),
            role=user.role.value,
            granted_scopes=set(ALL_SCOPES),
        ).run("get_irrigation_history", {"days": 30}, farm=db.get(Farm, farm_id))
    finally:
        db.close()

    assert outcome.ok, outcome.reason
    data = outcome.result.data
    assert data["event_count"] == 2
    assert data["total_applied_mm"] == 12.0, "unknown volume must not be added as 0"
    assert data["mean_soil_moisture_pct"] == 39.5
    # The row with no recorded depth is still reported, with the gap explicit.
    unknown = [i for i in data["items"] if i["applied_mm"] is None]
    assert len(unknown) == 1
    assert "not reported for the rest" in outcome.result.summary


def test_every_read_tool_executes_and_matches_its_declared_schema(executor_factory):
    """Runs all registered read tools and checks each one's real payload.

    No read tool is allowed to fail. A tool with nothing to report must say so
    through ``available=False`` and name what is missing, so a registered tool
    that raises is a defect and not something this test tolerates.
    """
    from app.services.agent.registry import registry

    specs = sorted(registry.list_tools(enabled_only=True), key=lambda s: s.name)
    read_tools = [s for s in specs if not s.is_write]
    assert read_tools, "no read tools are registered"

    failures: list[str] = []
    for spec in read_tools:
        executor, farm = executor_factory()
        try:
            args = TOOL_ARGS.get(spec.name, {})
            outcome = executor.run(spec.name, args, farm=farm)

            if not outcome.ok:
                failures.append(f"{spec.name}: status={outcome.status.value} reason={outcome.reason}")
                continue

            assert outcome.result is not None, f"{spec.name}: ok=True but no result"
            if spec.output_model is not None:
                spec.output_model.model_validate(outcome.result.data)

            expected_missing = EXPECTED_EMPTY.get(spec.name)
            if expected_missing and not outcome.result.available:
                assert expected_missing in (outcome.result.missing_data or ())
        finally:
            executor.db.close()

    assert not failures, "read tools failed:\n" + "\n".join(failures)


def test_canonical_aliases_reach_the_same_handler(executor_factory):
    """A canonical name and its alias produce identical data and one audit row.

    Aliases exist so the agent surface can be renamed without breaking older
    prompts or saved sessions; if the two ever diverged, the audit trail would
    depend on which name the caller happened to use.
    """
    from app.core.database import SessionLocal
    from app.models.agent import ToolExecution
    from app.services.agent.registry import registry

    assert registry.get("get_farm").name == registry.get("farm_snapshot").name

    executor, farm = executor_factory()
    try:
        canonical = executor.run("get_farm", {}, farm=farm)
        canonical_task = executor.task.id
    finally:
        executor.db.close()

    executor, farm = executor_factory()
    try:
        alias = executor.run("farm_snapshot", {}, farm=farm)
        alias_task = executor.task.id
    finally:
        executor.db.close()

    assert canonical.ok and alias.ok
    assert canonical.result.data == alias.result.data

    with SessionLocal() as db:
        rows = (
            db.query(ToolExecution)
            .filter(ToolExecution.task_id.in_([canonical_task, alias_task]))
            .all()
        )
    assert len(rows) == 2
    assert all(r.tool_name == "farm_snapshot" for r in rows)
    assert all(r.required_permissions == ["farm:read"] for r in rows)


def test_unavailable_tool_reports_missing_data_instead_of_inventing_it(executor_factory):
    """A farm with no observations must produce an honest empty state.

    After output normalisation the declared fields are present but None, which
    is the point: there is no measurement to confuse with a real one.
    """
    executor, farm = executor_factory()
    try:
        for name in ("get_latest_soil_profile", "get_current_weather", "get_ndvi"):
            outcome = executor.run(name, {}, farm=farm)
            assert outcome.ok, f"{name} raised instead of reporting unavailability: {outcome.reason}"
            assert outcome.result is not None
            if outcome.result.available:
                # A configured provider may legitimately answer; only the
                # unavailable branch is asserted here.
                continue
            assert outcome.result.data["available"] is False
            assert outcome.result.missing_data, f"{name} reported unavailable without naming what is missing"
            assert outcome.result.confidence is None
            # No numeric measurement may be present on an unavailable result.
            for key, value in outcome.result.data.items():
                if key == "available" or value is None or isinstance(value, bool):
                    continue
                assert not isinstance(value, (int, float)), f"{name} invented {key}={value}"
    finally:
        executor.db.close()


def test_output_schema_rejects_a_mismatched_payload():
    """The schema is a real check, not a rubber stamp.

    Guards against someone loosening the models (or dropping ``output_model``)
    to make a drifting handler pass.
    """
    from pydantic import BaseModel

    from app.services.agent.registry import ToolOutputError, ToolSpec
    from app.services.agent.output_schemas import WeatherOutput

    class _In(BaseModel):
        pass

    spec = ToolSpec(
        name="contract_probe",
        version="1",
        summary="probe",
        input_model=_In,
        output_model=WeatherOutput,
        handler=lambda ctx, args: None,
    )

    assert spec.validate_output({"temperature_c": 31.5})["temperature_c"] == 31.5

    with pytest.raises(ToolOutputError):
        spec.validate_output({"temperature_c": "warm"})


def test_only_transient_faults_are_retried(executor_factory):
    """A timeout is retried; a handler that raises is not.

    Retrying a handler bug cannot change the answer, so it only burns
    wall-clock and inflates ``retry_count`` on the audit row.
    """
    from app.models.agent import ToolExecution, ToolExecutionStatus
    from pydantic import BaseModel

    from app.services.agent.registry import ToolResult, ToolSpec, registry

    class _In(BaseModel):
        pass

    calls: dict[str, int] = {"transient": 0, "broken": 0}

    def transient(ctx, args):
        calls["transient"] += 1
        if calls["transient"] < 3:
            raise TimeoutError("upstream provider hiccup")
        return ToolResult(data={"available": True}, summary="recovered")

    def broken(ctx, args):
        calls["broken"] += 1
        raise ValueError("handler bug")

    probes = {
        "probe_transient": ToolSpec(
            name="probe_transient",
            version="1",
            summary="probe",
            input_model=_In,
            handler=transient,
            max_retries=2,
        ),
        "probe_broken": ToolSpec(
            name="probe_broken",
            version="1",
            summary="probe",
            input_model=_In,
            handler=broken,
            max_retries=2,
        ),
    }
    for spec in probes.values():
        registry.register(spec, replace=True)

    try:
        executor, farm = executor_factory()
        try:
            recovered = executor.run("probe_transient", {}, farm=farm)
            transient_row = executor.db.query(ToolExecution).filter_by(tool_name="probe_transient").one()
        finally:
            executor.db.close()

        executor, farm = executor_factory()
        try:
            failed = executor.run("probe_broken", {}, farm=farm)
            broken_row = executor.db.query(ToolExecution).filter_by(tool_name="probe_broken").one()
        finally:
            executor.db.close()
    finally:
        for name in probes:
            registry._tools.pop(name, None)

    assert recovered.status == ToolExecutionStatus.SUCCEEDED
    assert calls["transient"] == 3
    assert transient_row.retry_count == 2

    assert failed.status == ToolExecutionStatus.FAILED
    assert calls["broken"] == 1, "a raising handler must not be retried"
    assert broken_row.retry_count == 0


def test_registry_rejects_alias_collisions_and_duplicate_registration():
    """Two tools cannot claim the same name, and re-registering is explicit."""
    from pydantic import BaseModel

    from app.services.agent.registry import ToolRegistry, ToolSpec

    class _In(BaseModel):
        pass

    def _spec(name: str, **kwargs) -> ToolSpec:
        return ToolSpec(
            name=name,
            version="1",
            summary="probe",
            input_model=_In,
            handler=lambda ctx, args: None,
            **kwargs,
        )

    reg = ToolRegistry()
    reg.register(_spec("a"))
    with pytest.raises(ValueError, match="already registered"):
        reg.register(_spec("a"))
    reg.register(_spec("a"), replace=True)

    reg.register(_spec("b", aliases=("shared_name",)))
    with pytest.raises(ValueError, match="aliases already in use"):
        reg.register(_spec("c", aliases=("shared_name",)))

    with pytest.raises(ValueError, match="unknown scopes"):
        reg.register(_spec("d", required_permissions=("nope:read",)))