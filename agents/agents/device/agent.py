import logging
from temporalio import activity

from agents.shared.mock_data import get_device_profile
from agents.shared.event_writer import append_event
from chronicle_shared.schema import EventEnvelope
from chronicle_shared.events import EventType

logger = logging.getLogger(__name__)


@activity.defn
async def run_device_agent(state: dict) -> dict:
    investigation_id = state["investigation_id"]
    alert = state["alert"]
    device_id = alert.get("device_id", "")
    correlation_id = state.get("correlation_id", investigation_id)
    causation_id = state.get("last_event_id")

    profile = await get_device_profile(device_id)

    evidence = {
        "device_id": device_id,
        "known": profile["known"],
        "device_age_days": profile["device_age_days"],
        "fraud_flags": profile["fraud_flags"],
        "risk_flags": [],
    }

    if not profile["known"]:
        evidence["risk_flags"].append("unknown_device")
    if profile["fraud_flags"] > 0:
        evidence["risk_flags"].append("prior_fraud_device")
    if profile["device_age_days"] < 7:
        evidence["risk_flags"].append("new_device")

    envelope = EventEnvelope(
        event_type=EventType.DEVICE_EVIDENCE_COLLECTED,
        aggregate_id=investigation_id,
        producer="device-agent",
        stream_version=2,
        workflow_id=state.get("workflow_id"),
        correlation_id=correlation_id,
        causation_id=causation_id,
        trace_id=state.get("trace_id"),
        payload={"investigation_id": investigation_id, "evidence": evidence},
    )
    stored_event_id = await append_event(envelope.to_dict())

    state["device_evidence"] = evidence
    state["last_event_id"] = stored_event_id  # the STORED id — may differ on activity retry
    logger.info("Device agent done for %s known=%s flags=%s",
                investigation_id, profile["known"], evidence["risk_flags"])
    return state
