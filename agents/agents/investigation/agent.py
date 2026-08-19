import asyncio
import json
import logging
import os

from temporalio import activity

from agents.shared import mock_data
from agents.shared.event_writer import append_event
from chronicle_shared.schema import EventEnvelope
from chronicle_shared.events import EventType

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna")
# Bounded reasoning: a hard budget, not a prompt wish. This is LangGraph's
# recursion_limit, which counts graph SUPERSTEPS (model turn or tool batch),
# not "ReAct turns" — 8 supersteps ≈ 3-4 rounds of tool use. Exhaustion
# raises GraphRecursionError, handled below as a degraded (not fake) result.
MAX_AGENT_STEPS = int(os.getenv("INVESTIGATION_AGENT_MAX_STEPS", "8"))

# Versioned reasoning provenance, recorded on every event this agent emits:
# "would we decide the same way again?" must account for prompt and agent
# code changes, not just the model name.
PROMPT_VERSION = 1
AGENT_VERSION = 2  # v1: bare chat completion; v2: LangGraph ReAct with tools

SYSTEM_PROMPT = (
    "You are a fraud investigation assistant. You receive evidence collected by "
    "other agents about one flagged transaction. Use your tools to verify facts "
    "or dig deeper when the evidence is ambiguous — for example, confirm a "
    "customer's history before calling a spend 'unusual'. Then summarise the key "
    "risk factors and your overall assessment in 2-3 sentences. Be concise and "
    "factual; you provide analysis, not the decision."
)

# The whole LangGraph agent lives inside this Temporal activity. Once the
# activity completes, its returned evidence becomes the durable fact the
# workflow consumes: workflow REPLAY reuses that completion result and never
# re-runs the graph. Retries BEFORE completion may re-execute it, so every
# external effect in here must be idempotent (tools are read-only; the event
# append dedups on stream position and returns the stored id).
_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        from langchain.agents import create_agent
        from langchain_core.tools import tool
        from langchain_openai import ChatOpenAI

        @tool
        async def customer_history(customer_id: str) -> str:
            """Look up a customer's account age, average transaction amount, prior alerts and confirmed fraud."""
            profile = await mock_data.get_customer_profile(customer_id)
            return json.dumps(profile)

        @tool
        async def device_record(device_id: str) -> str:
            """Look up whether a device is known, its age in days, and prior fraud flags."""
            profile = await mock_data.get_device_profile(device_id)
            return json.dumps(profile)

        @tool
        def country_risk(country_code: str) -> str:
            """Return the risk level (low, medium or high) for an ISO country code."""
            return mock_data.get_country_risk(country_code)

        model = ChatOpenAI(model=OPENAI_MODEL, api_key=OPENAI_API_KEY, temperature=0.3)
        _agent = create_agent(
            model,
            tools=[customer_history, device_record, country_risk],
            system_prompt=SYSTEM_PROMPT,
        )
    return _agent


def _build_prompt(alert: dict, device: dict, geo: dict, customer: dict) -> str:
    all_flags = (
        device.get("risk_flags", []) +
        geo.get("risk_flags", []) +
        customer.get("risk_flags", [])
    )
    return f"""Analyse the following transaction evidence.

Transaction:
- Amount: ${alert.get('amount')} {alert.get('currency', 'USD')}
- Merchant: {alert.get('merchant')} ({alert.get('merchant_country')})
- Country: {geo.get('country')} (risk: {geo.get('country_risk')})
- VPN detected: {geo.get('vpn_detected')}
- Customer id: {alert.get('customer_id')}
- Device id: {alert.get('device_id')}

Device evidence:
- Known device: {device.get('known')}
- Device age: {device.get('device_age_days')} days
- Prior fraud flags: {device.get('fraud_flags')}

Customer evidence:
- Account age: {customer.get('account_age_days')} days
- Avg transaction: ${customer.get('transaction_avg')}
- This amount is {customer.get('amount_ratio')}x their average
- Prior alerts: {customer.get('prior_alerts')}
- Prior confirmed fraud: {customer.get('prior_fraud')}

Risk flags identified by evidence agents: {', '.join(all_flags) if all_flags else 'none'}"""


def _message_text(message) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            part.get("text", "") for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return str(content)


def _extract_tool_trace(messages) -> list[dict]:
    """Pair each tool call the agent made with the result it got back."""
    calls: dict[str, dict] = {}
    for m in messages:
        for tc in getattr(m, "tool_calls", None) or []:
            calls[tc["id"]] = {"tool": tc["name"], "args": tc["args"], "result": None}
        if type(m).__name__ == "ToolMessage" and getattr(m, "tool_call_id", None) in calls:
            result = m.content if isinstance(m.content, str) else str(m.content)
            calls[m.tool_call_id]["result"] = result[:300]
    return list(calls.values())


async def _run_langgraph(prompt: str) -> tuple[str, list[dict]]:
    agent = _get_agent()
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config={"recursion_limit": MAX_AGENT_STEPS},
    )
    messages = result["messages"]
    reasoning = _message_text(messages[-1]).strip()
    return reasoning or _mock_reasoning(), _extract_tool_trace(messages)


def _mock_reasoning() -> str:
    return ("Transaction shows elevated risk indicators including unusual device, "
            "geographic anomalies, or spending pattern deviations. "
            "Recommend policy review for final determination.")


def _budget_exhausted_reasoning() -> str:
    return ("Reasoning step budget exhausted before the agent reached a "
            "conclusion. Evidence flags stand on their own; treat the "
            "narrative as unavailable for this case.")


async def _heartbeat_forever():
    """Signal liveness while the graph runs, so a dead worker is detected in
    seconds (heartbeat_timeout) instead of waiting out start_to_close."""
    while True:
        activity.heartbeat()
        await asyncio.sleep(10)


@activity.defn
async def run_investigation_agent(state: dict) -> dict:
    investigation_id = state["investigation_id"]
    alert = state["alert"]
    device = state.get("device_evidence", {})
    geo = state.get("geo_evidence", {})
    customer = state.get("customer_evidence", {})
    correlation_id = state.get("correlation_id", investigation_id)
    causation_id = state.get("last_event_id")

    prompt = _build_prompt(alert, device, geo, customer)

    tool_calls: list[dict] = []
    framework = "mock"
    degraded_reason = None
    if OPENAI_API_KEY:
        from langgraph.errors import GraphRecursionError
        heartbeat_task = asyncio.create_task(_heartbeat_forever())
        try:
            reasoning, tool_calls = await _run_langgraph(prompt)
            framework = "langgraph"
        except GraphRecursionError:
            logger.warning("Investigation agent hit step budget (%d supersteps) for %s",
                           MAX_AGENT_STEPS, investigation_id)
            reasoning = _budget_exhausted_reasoning()
            degraded_reason = "step_budget_exhausted"
        except Exception as e:
            logger.warning("LangGraph agent failed, using mock reasoning: %s", e)
            reasoning = _mock_reasoning()
            degraded_reason = "llm_error"
        finally:
            heartbeat_task.cancel()
    else:
        reasoning = _mock_reasoning()
        degraded_reason = "no_api_key"

    all_flags = (
        device.get("risk_flags", []) +
        geo.get("risk_flags", []) +
        customer.get("risk_flags", [])
    )

    envelope = EventEnvelope(
        event_type=EventType.LLM_REASONING_GENERATED,
        aggregate_id=investigation_id,
        producer="investigation-agent",
        stream_version=5,
        workflow_id=state.get("workflow_id"),
        correlation_id=correlation_id,
        causation_id=causation_id,
        trace_id=state.get("trace_id"),
        payload={
            "investigation_id": investigation_id,
            "reasoning": reasoning,
            "risk_flags": all_flags,
            "model": OPENAI_MODEL,
            "prompt_version": PROMPT_VERSION,
            "agent_version": AGENT_VERSION,
            # Which path actually produced this reasoning, and whether it is
            # degraded. The policy gate never consumes the narrative — only
            # evidence flags — so a degraded narrative can't sway a decision;
            # these fields make the degradation visible, not survivable.
            "framework": framework,
            "degraded": degraded_reason is not None,
            "degraded_reason": degraded_reason,
            # The audit trail of the reasoning itself: which tools the agent
            # called, with what arguments, and what came back.
            "tool_calls": tool_calls,
        },
    )
    stored_event_id = await append_event(envelope.to_dict())

    state["llm_reasoning"] = reasoning
    state["all_risk_flags"] = all_flags
    state["last_event_id"] = stored_event_id  # the STORED id — may differ on activity retry
    logger.info("Investigation agent done for %s tools_used=%d flags=%s",
                investigation_id, len(tool_calls), all_flags)
    return state
