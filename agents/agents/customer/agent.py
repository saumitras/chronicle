import logging
from temporalio import activity

from agents.shared.mock_data import get_customer_profile
from agents.shared.event_writer import append_event
from chronicle_shared.schema import EventEnvelope
from chronicle_shared.events import EventType

logger = logging.getLogger(__name__)


@activity.defn
async def run_customer_agent(state: dict) -> dict:
    investigation_id = state["investigation_id"]
    alert = state["alert"]
    customer_id = alert.get("customer_id", "")
    amount = alert.get("amount", 0)
    correlation_id = state.get("correlation_id", investigation_id)
    causation_id = state.get("last_event_id")

    profile = await get_customer_profile(customer_id)
    amount_ratio = amount / profile["transaction_avg"] if profile["transaction_avg"] > 0 else 1.0

    evidence = {
        "customer_id": customer_id,
        "account_age_days": profile["account_age_days"],
        "transaction_avg": profile["transaction_avg"],
        "transaction_amount": amount,
        "amount_ratio": round(amount_ratio, 2),
        "prior_alerts": profile["prior_alerts"],
        "prior_fraud": profile["prior_fraud"],
        "risk_flags": [],
    }

    if profile["prior_fraud"]:
        evidence["risk_flags"].append("prior_fraud_confirmed")
    if profile["prior_alerts"] >= 3:
        evidence["risk_flags"].append("multiple_prior_alerts")
    if amount_ratio > 5:
        evidence["risk_flags"].append("amount_far_above_average")
    elif amount_ratio > 2:
        evidence["risk_flags"].append("amount_above_average")
    if profile["account_age_days"] < 30:
        evidence["risk_flags"].append("new_account")

    envelope = EventEnvelope(
        event_type=EventType.CUSTOMER_EVIDENCE_COLLECTED,
        aggregate_id=investigation_id,
        producer="customer-agent",
        stream_version=4,
        workflow_id=state.get("workflow_id"),
        correlation_id=correlation_id,
        causation_id=causation_id,
        trace_id=state.get("trace_id"),
        payload={"investigation_id": investigation_id, "evidence": evidence},
    )
    stored_event_id = await append_event(envelope.to_dict())

    state["customer_evidence"] = evidence
    state["last_event_id"] = stored_event_id  # the STORED id — may differ on activity retry
    logger.info("Customer agent done for %s amount_ratio=%.2f flags=%s",
                investigation_id, amount_ratio, evidence["risk_flags"])
    return state
