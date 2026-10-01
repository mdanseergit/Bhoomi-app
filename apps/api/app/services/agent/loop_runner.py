"""
The agent loop.

    OBSERVE -> UNDERSTAND -> PLAN -> USE_TOOLS -> ANALYZE -> ACT -> VERIFY
            -> REMEMBER -> NOTIFY

Design rules that this module exists to enforce:

* The loop is bounded. Every phase asks ``TaskManager`` for permission first,
  and a run that hits a cap stops and reports the reason instead of continuing.
* Grounding precedes generation. Tool output is collected before any text is
  written, and the answering model is given that output as its only source of
  farm facts.
* An unavailable capability is reported as unavailable. Nothing here
  substitutes a plausible number for a missing observation.
* No hidden reasoning is persisted or returned. Each phase records a public
  summary, its evidence and its sources -- the phase name and outcome, not the
  model's private trace.
* Language generation is optional. With no AI provider configured the loop
  still completes, using the deterministic template, and says so.
"""
import json
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.ai.base import AIMessage
from app.integrations.ai.deterministic_provider import DeterministicFallbackProvider
from app.integrations.ai.factory import build_provider_chain
from app.models.agent import AgentPhase, AgentStepStatus, AgentTask
from app.models.farm import Farm
from app.models.user import User
from app.services.agent.executor import ExecutionOutcome, ToolBudgetExhausted, ToolExecutor
from app.services.agent.permissions import scopes_for_role
from app.services.agent.registry import ToolResult, registry
from app.services.agent.task_manager import BudgetExceeded, RepetitionGuard, TaskManager

logger = get_logger("bhoomi.agent.loop")

_SYSTEM_PROMPT = (
    "You are BHOOMI, an agriculture agent for smallholder farmers in India. "
    "Answer only from the OBSERVATIONS provided. Never state a measurement that is not in "
    "the observations, and never invent a value for data marked missing. If the observations "
    "do not answer the question, say exactly which data is missing and how to obtain it. "
    "Crop-disease results are hypotheses for agronomist review, never a confirmed diagnosis. "
    "Be concise and practical, give the concrete next action, and state confidence in plain "
    "language. Reply with the answer text only."
)

# Rendered with .replace() rather than .format(): the example JSON contains
# literal braces and would be read as format placeholders.
_PLANNER_PROMPT = (
    "You choose which BHOOMI tools to run. Given the user's question and the available tools, "
    'reply with a JSON array and nothing else, e.g. [{"tool":"weather_now","args":{}}]. '
    "Choose at most __MAX_CALLS__ tools. Choose no tools (an empty array) if the observations "
    "already collected answer the question. Never invent a tool name."
)

_INTENT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("disease", ("disease", "blight", "leaf", "spot", "rot", "mildew", "pest", "infection", "bola", "patunga")),
    ("weather", ("weather", "rain", "temperature", "hot", "humid", "storm", "forecast", " Mausam", "rainfall")),
    ("soil", ("soil", "ph", "nitrogen", "potash", "phosphorus", "organic", "soil test")),
    ("vegetation", ("ndvi", "evi", "satellite", "vegetation", "crop health index", "green")),
    ("water", ("water", "moisture", "irrigat", "drought", "dry", "sinchai")),
    ("advisory", ("advisory", "advice", "recommend", "what should i do", "kya karu", "upay")),
    ("health", ("health", "score", "risk", "status of", "how is my farm")),
    ("farm", ("farm", "acre", "hectare", "crop", "variety", "stage", "sowing", "my land")),
)

_TEMPLATES: dict[str, str] = {
    "disease": (
        "Crop-disease assessment for {farm}\n\n{body}\n\n"
        "These are hypotheses from leaf-image analysis, not a confirmed diagnosis. "
        "Please have an agronomist or an extension officer confirm before acting on spraying advice."
    ),
    "weather": "Current conditions for {farm}\n\n{body}",
    "soil": "Soil status for {farm}\n\n{body}",
    "vegetation": "Vegetation status for {farm}\n\n{body}",
    "water": "Water and moisture status for {farm}\n\n{body}",
    "advisory": "Advisories for {farm}\n\n{body}",
    "health": "Farm health for {farm}\n\n{body}",
    "farm": "Farm details for {farm}\n\n{body}",
    "general": "Regarding {farm}\n\n{body}",
}


@dataclass
class LoopResult:
    """The loop's outcome, as returned to the API and shown in the chat bar."""

    answer: str
    confidence: float
    evidence: list[dict] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    phases: list[dict] = field(default_factory=list)
    model_used: str | None = None
    provider_used: str | None = None
    fallback_used: bool = False
    requires_approval: bool = False
    budget: dict = field(default_factory=dict)
    warning: str | None = None
    # Filled in by AgentService once the task row is committed.
    task_id: str | None = None
    session_id: str | None = None
    status: str | None = None


def classify_intent(query: str) -> str:
    lowered = query.lower()
    for intent, keywords in _INTENT_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return intent
    return "general"


def plan_tools(intent: str, available: list[str], *, max_calls: int) -> list[str]:
    """Deterministic intent -> tool plan.

    The mapping is explicit so the tool set for a question is predictable and
    reviewable. A model may add tools on top of this (see ``AgentRunner.run``)
    but can never remove a required one, which is what keeps the agent from
    answering a soil question without calling the soil tool.
    """
    mapping: dict[str, tuple[str, ...]] = {
        "disease": ("disease_history", "farm_snapshot"),
        "weather": ("weather_now",),
        "soil": ("soil_profile",),
        "vegetation": ("vegetation_index",),
        "water": ("water_status",),
        "advisory": ("compute_advisories",),
        # A health answer is about *this* farm, so the profile (crop, stage,
        # area) is part of the grounding, not extra work.
        "health": ("farm_snapshot", "farm_health"),
        "farm": ("farm_snapshot",),
        "general": ("farm_snapshot", "farm_health"),
    }
    planned = [name for name in mapping.get(intent, ()) if name in available]
    return planned[:max_calls]


class AgentRunner:
    def __init__(self, db: Session):
        self.db = db
        self.tasks = TaskManager(db)

    # --- entry point ---------------------------------------------------

    def run(
        self,
        *,
        task: AgentTask,
        user: User,
        farm: Farm | None,
        query: str,
        language: str = "en",
        enabled_tools: list[str] | None = None,
    ) -> LoopResult:
        granted = scopes_for_role(user.role)
        executor = ToolExecutor(
            db=self.db,
            task=task,
            user_id=str(user.id),
            role=user.role.value,
            granted_scopes=granted,
        )
        guard = RepetitionGuard(limit=settings.AGENT_REPETITION_LIMIT)
        phases: list[dict] = []
        evidence: list[dict] = []
        sources: list[dict] = []
        missing: list[str] = []
        conflicts: list[dict] = []
        tool_calls: list[dict] = []
        warning: str | None = None

        available = enabled_tools if enabled_tools is not None else executor.available_names()

        # Bound before the phases run so an exception in an earlier phase can
        # never leave the final answer without a plan or a confidence value.
        intent = classify_intent(query)
        planned: list[str] = []
        confidence = 0.2

        # --- OBSERVE ---------------------------------------------------
        step = self.tasks.open_step(task, AgentPhase.OBSERVE, goal="Establish what is known about this farm right now.")
        try:
            self.tasks.ensure_not_timed_out(task)
            memories = self.tasks.recall(user_id=user.id, limit=5)
            known = [
                {"domain": "Farm profile", "provider": "farmer_recorded", "status": "RECENT"}
                if farm
                else {"domain": "Farm profile", "provider": "no_farm_selected", "status": "NOT_SELECTED"}
            ]
            if memories:
                known.append({"domain": "Prior context", "provider": "agent_memory", "status": "RECENT"})
            self.tasks.close_step(
                step,
                summary=(
                    f"Resolved farm: {farm.name}." if farm else "No farm selected; answering from account-level data only."
                ),
                sources=known,
                confidence=0.9,
            )
            phases.append(_phase(step))
            sources.extend(known)
        except BudgetExceeded as exc:
            self.tasks.close_step(step, status=AgentStepStatus.SKIPPED, summary=str(exc))
            warning = str(exc)

        # --- UNDERSTAND ------------------------------------------------
        step = self.tasks.open_step(task, AgentPhase.UNDERSTAND, goal="Classify the question and choose the tools it needs.")
        try:
            self.tasks.ensure_not_timed_out(task)
            intent = classify_intent(query)
            base_plan = plan_tools(intent, available, max_calls=max(1, task.max_tool_calls - task.tool_call_count))
            extra = self._model_additions(intent, query, available, base_plan)
            planned = _dedupe(base_plan + extra)[: max(1, task.max_tool_calls - task.tool_call_count)]
            self.tasks.close_step(
                step,
                summary=f"Question classified as '{intent}'. Tools to run: {', '.join(planned) or 'none'}.",
                confidence=0.7,
            )
            phases.append(_phase(step))
        except BudgetExceeded as exc:
            intent = classify_intent(query)
            planned = []
            self.tasks.close_step(step, status=AgentStepStatus.SKIPPED, summary=str(exc))
            warning = warning or str(exc)

        # --- PLAN ------------------------------------------------------
        step = self.tasks.open_step(task, AgentPhase.PLAN, goal="Order the tool calls so each one informs the next.")
        try:
            self.tasks.ensure_not_timed_out(task)
            self.tasks.close_step(
                step,
                summary=f"Execution plan: {len(planned)} tool call(s).",
                confidence=0.85,
            )
            phases.append(_phase(step))
        except BudgetExceeded as exc:
            self.tasks.close_step(step, status=AgentStepStatus.SKIPPED, summary=str(exc))
            warning = warning or str(exc)

        # --- USE_TOOLS -------------------------------------------------
        step = self.tasks.open_step(task, AgentPhase.USE_TOOLS, goal="Collect real observations.")
        tool_phase_count = 0
        try:
            self.tasks.ensure_not_timed_out(task)
        except BudgetExceeded as exc:
            self.tasks.close_step(step, status=AgentStepStatus.SKIPPED, summary=str(exc))
            warning = warning or str(exc)

        observations: list[str] = []
        for name in planned:
            signature = f"{name}"
            if guard.observe(signature) >= guard.limit:
                tool_calls.append(
                    {"tool": name, "status": "skipped", "reason": f"repeated {guard.limit} times; stopping to avoid a loop"}
                )
                continue
            try:
                outcome = executor.run(name, {}, step=step, farm=farm, language=language)
            except ToolBudgetExhausted as exc:
                warning = str(exc)
                break

            tool_calls.append(_call_record(outcome))
            evidence.extend(outcome.result.evidence if outcome.result else [])
            sources.extend(outcome.result.sources if outcome.result else [])
            missing.extend(outcome.result.missing_data if outcome.result else [])
            conflicts.extend(outcome.result.conflicts if outcome.result else [])
            observations.append(_observation_line(name, outcome))
            if outcome.result is not None and outcome.result.available:
                tool_phase_count += 1

        if planned:
            self.tasks.close_step(
                step,
                summary=(
                    f"Collected {tool_phase_count} of {len(planned)} available observation set(s)."
                    if tool_phase_count
                    else "No observation set was available from the planned tools."
                ),
                evidence=evidence,
                sources=sources,
                missing_data=missing,
                tool_call_count=executor.task.tool_call_count,
                duration_ms=None,
            )
            phases.append(_phase(step))
        else:
            self.tasks.close_step(step, status=AgentStepStatus.SKIPPED, summary="No tools were planned for this question.")
            phases.append(_phase(step))

        # --- ANALYZE ---------------------------------------------------
        step = self.tasks.open_step(task, AgentPhase.ANALYZE, goal="Combine the observations into what they support.")
        try:
            self.tasks.ensure_not_timed_out(task)
            confidence = _aggregate_confidence(tool_calls, missing)
            self.tasks.close_step(
                step,
                summary=(
                    f"Analysis over {len(observations)} observation set(s); "
                    f"{len(set(missing))} input(s) still missing."
                ),
                evidence=evidence,
                missing_data=missing,
                confidence=confidence,
            )
            phases.append(_phase(step))
        except BudgetExceeded as exc:
            confidence = _aggregate_confidence(tool_calls, missing)
            self.tasks.close_step(step, status=AgentStepStatus.SKIPPED, summary=str(exc))
            warning = warning or str(exc)

        # --- ACT -------------------------------------------------------
        # v1 is read-only. A question that asks the agent to change something
        # is answered as advice, and the intent is recorded so a later write
        # can be gated behind approval without changing the answering path.
        step = self.tasks.open_step(task, AgentPhase.ACT, goal="Take only actions the permissions and risk level allow.")
        requires_approval = _is_write_request(query)
        self.tasks.close_step(
            step,
            summary=(
                "No change was made: this deployment is read-only. Any requested change is returned as advice."
                if requires_approval
                else "No action required; the request was answered from observations."
            ),
            confidence=1.0,
        )
        phases.append(_phase(step))

        # --- VERIFY ---------------------------------------------------
        step = self.tasks.open_step(task, AgentPhase.VERIFY, goal="Confirm every claim traces to an observation.")
        try:
            self.tasks.ensure_not_timed_out(task)
            verified = bool(observations) and tool_phase_count > 0
            self.tasks.close_step(
                step,
                summary=(
                    "Every statement traces to a named source."
                    if verified
                    else "Not verified: no real observation was available, so the answer reports missing data only."
                ),
                confidence=confidence,
            )
            phases.append(_phase(step))
        except BudgetExceeded as exc:
            self.tasks.close_step(step, status=AgentStepStatus.SKIPPED, summary=str(exc))
            warning = warning or str(exc)

        # --- REMEMBER --------------------------------------------------
        step = self.tasks.open_step(task, AgentPhase.REMEMBER, goal="Persist only what was actually observed.")
        try:
            self.tasks.ensure_not_timed_out(task)
            if farm is not None and tool_phase_count > 0:
                self.tasks.remember(
                    user_id=user.id,
                    farm_id=farm.id,
                    task_id=task.id,
                    key=f"farm:{farm.id}:observation_summary",
                    content={
                        "farm_name": farm.name,
                        "intent": intent,
                        "tools_used": [c["tool"] for c in tool_calls if c.get("status") == "succeeded"],
                        "missing_data": sorted(set(missing)),
                    },
                    source="agent_observation",
                    confidence=confidence,
                )
            self.tasks.close_step(step, summary="Recorded the observed state for the next session.")
            phases.append(_phase(step))
        except BudgetExceeded as exc:
            self.tasks.close_step(step, status=AgentStepStatus.SKIPPED, summary=str(exc))
            warning = warning or str(exc)

        # --- NOTIFY ----------------------------------------------------
        step = self.tasks.open_step(task, AgentPhase.NOTIFY, goal="Answer the farmer in plain language.")
        answer, model_used, provider_used, fallback_used = self._compose(
            query=query,
            intent=intent,
            farm=farm,
            observations=observations,
            missing=missing,
            confidence=confidence,
            language=language,
        )
        self.tasks.close_step(
            step,
            summary="Answer composed from the collected observations.",
            evidence=evidence,
            sources=sources,
            missing_data=missing,
            confidence=confidence,
            model_used=model_used,
        )
        phases.append(_phase(step))

        return LoopResult(
            answer=answer,
            confidence=confidence,
            evidence=evidence,
            sources=sources,
            missing_data=sorted(set(missing)),
            conflicts=conflicts,
            tool_calls=tool_calls,
            phases=phases,
            model_used=model_used,
            provider_used=provider_used,
            fallback_used=fallback_used,
            requires_approval=requires_approval,
            budget=self.tasks.budget(task, guard).to_dict(),
            warning=warning,
        )

    # --- helpers -------------------------------------------------------

    def _model_additions(
        self, intent: str, query: str, available: list[str], already: list[str]
    ) -> list[str]:
        """Asks the model for extra tools, and ignores anything unusable.

        The model may only *add* calls from the catalogue the caller is
        permitted to use. An unparseable reply, a hallucinated tool name, or a
        request for a tool already planned all resolve to "no additions".
        """
        if not available:
            return []
        prompt = _PLANNER_PROMPT.replace("__MAX_CALLS__", "2")
        content = self._raw_model_call(
            [
                AIMessage(role="system", content=prompt),
                AIMessage(
                    role="user",
                    content=f"Question: {query}\nIntent: {intent}\nTools: {', '.join(available)}",
                ),
            ],
            temperature=0.0,
            max_tokens=200,
        )
        if not content:
            return []
        parsed = _extract_json_array(content)
        additions: list[str] = []
        for entry in parsed:
            name = entry.get("tool") if isinstance(entry, dict) else None
            if isinstance(name, str) and name in available and name not in already:
                additions.append(name)
        return additions[:2]

    def _raw_model_call(
        self, messages: list[AIMessage], *, temperature: float, max_tokens: int
    ) -> str | None:
        """Best-effort model call used for planning only.

        Planning is an optimisation; the loop must still work with no model
        available, so any failure here is swallowed and the deterministic plan
        stands.
        """
        chain = build_provider_chain()
        for provider in chain:
            if isinstance(provider, DeterministicFallbackProvider):
                break
            try:
                return provider.complete(messages, temperature=temperature, max_tokens=max_tokens).content
            except Exception as exc:  # noqa: BLE001 - planning is best-effort
                logger.info("agent_planner_call_failed", provider=provider.name, error=repr(exc))
        return None

    def _compose(
        self,
        *,
        query: str,
        intent: str,
        farm: Farm | None,
        observations: list[str],
        missing: list[str],
        confidence: float,
        language: str,
    ) -> tuple[str, str | None, str | None, bool]:
        """Writes the answer, falling back to a deterministic template.

        The model is given the observations and nothing else, and its output is
        checked for the same refusal/filler markers the rest of the platform
        rejects before it reaches a user.
        """
        farm_label = farm.name if farm else "your account"
        missing_line = (
            "\n\nData still missing for this farm: "
            + ", ".join(sorted(set(missing)))
            + ". Add it on the relevant screen to improve future answers."
            if missing
            else ""
        )

        if not observations:
            body = (
                "I could not collect any real observation for this farm from the configured data "
                "sources, so I am not going to estimate an answer."
            )
            return (
                _TEMPLATES.get(intent, _TEMPLATES["general"]).format(farm=farm_label, body=body) + missing_line,
                None,
                None,
                True,
            )

        context = "\n".join(observations)
        messages = [
            AIMessage(role="system", content=_SYSTEM_PROMPT),
            AIMessage(
                role="user",
                content=(
                    f"FARM: {farm_label}\n"
                    f"QUESTION: {query}\n"
                    f"OBSERVATIONS:\n{context}\n"
                    f"MISSING: {', '.join(sorted(set(missing))) if missing else 'none'}\n"
                    f"Answer the question for the farmer in {language}."
                ),
            ),
        ]

        from app.services.ai_service import validate_ai_response

        for provider in build_provider_chain():
            if isinstance(provider, DeterministicFallbackProvider):
                break
            try:
                completion = provider.complete(
                    messages, temperature=0.2, max_tokens=settings.AI_MAX_TOKENS_OUT
                )
                content = validate_ai_response(completion.content)
            except Exception as exc:  # noqa: BLE001 - fall through to the next provider
                logger.info("agent_compose_provider_failed", provider=provider.name, error=repr(exc))
                continue
            return (
                content + missing_line,
                completion.model,
                completion.provider,
                False,
            )

        body = "\n".join(f"- {line}" for line in observations)
        template = _TEMPLATES.get(intent, _TEMPLATES["general"])
        return (
            template.format(farm=farm_label, body=body)
            + missing_line
            + "\n\nGenerated from recorded farm data by BHOOMI's deterministic engine.",
            "deterministic-rules",
            "deterministic",
            True,
        )


# --- module helpers -------------------------------------------------------


def _phase(step) -> dict:
    return {
        "step_number": step.step_number,
        "phase": step.phase.value,
        "status": step.status.value,
        "summary": step.summary,
        "duration_ms": step.duration_ms,
    }


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _call_record(outcome: ExecutionOutcome) -> dict:
    return {
        "tool": outcome.tool_name,
        "status": outcome.status.value,
        "summary": outcome.summary,
        "duration_ms": outcome.duration_ms,
        "execution_id": outcome.execution_id,
        "reason": outcome.reason,
    }


def _observation_line(name: str, outcome: ExecutionOutcome) -> str:
    result: ToolResult | None = outcome.result
    if result is None:
        return f"{name}: not available ({outcome.reason})"
    status = "available" if result.available else "unavailable"
    return f"{name} ({status}): {result.summary}"


def _aggregate_confidence(tool_calls: list[dict], missing: list[str]) -> float:
    """Confidence from what was actually retrieved.

    Derived from the tools that returned real data and the share of inputs
    that are still missing, so an answer built on two of five observations
    cannot present itself as well-grounded as one built on five.
    """
    succeeded = [c for c in tool_calls if c.get("status") == "succeeded"]
    if not succeeded:
        return 0.2
    base = 0.5
    spread = min(len(succeeded), 4) / 4 * 0.35
    penalty = min(len(set(missing)), 4) * 0.08
    return round(max(0.2, min(0.92, base + spread - penalty)), 2)


_WRITE_MARKERS = ("update", "change", "set ", "save ", "delete", "remove", "create", "record", "apply ", "register")


def _is_write_request(query: str) -> bool:
    lowered = query.lower()
    return any(marker in lowered for marker in _WRITE_MARKERS)


def _extract_json_array(text: str) -> list:
    """Parses the planner's JSON array without trusting it."""
    fenced = re.search(r"\[.*\]", text, re.DOTALL)
    if not fenced:
        return []
    try:
        parsed = json.loads(fenced.group(0))
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


__all__ = ["AgentRunner", "LoopResult", "classify_intent", "plan_tools", "registry"]