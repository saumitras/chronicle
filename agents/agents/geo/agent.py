import logging
from temporalio import activity

from agents.shared.mock_data import get_country_risk
from agents.shared.event_writer import append_event
from chronicle_shared.schema import EventEnvelope
from chronicle_shared.events import EventType

logger = logging.getLogger(__name__)

HOME_COUNTRIES = {"US", "GB", "DE", "AU", "CA", "FR", "JP", "IN", "SG"}


@activity.defn
async def run_geo_agent(state: dict) -> dict:
    investigation_id = state["investigation_id"]
    alert = state["alert"]
    country = alert.get("country", "US")
    vpn_detected = alert.get("vpn_detected", False)
    merchant_country = alert.get("merchant_country", "US")
    correlation_id = state.get("correlation_id", investigation_id)
    causation_id = state.get("last_event_id")

    country_risk = get_country_risk(country)
    merchant_risk = get_country_risk(merchant_country)
    is_foreign = country not in HOME_COUNTRIES

    evidence = {
        "country": country,
        "country_risk": country_risk,
        "vpn_detected": vpn_detected,
        "merchant_country": merchant_country,
        "merchant_country_risk": merchant_risk,
        "is_foreign_transaction": is_foreign,
        "risk_flags": [],
    }

    if vpn_detected:
        evidence["risk_flags"].append("vpn_detected")
    if country_risk == "high":
        evidence["risk_flags"].append("high_risk_country")
    elif country_risk == "medium":
        evidence["risk_flags"].append("medium_risk_country")
    if is_foreign:
        evidence["risk_flags"].append("foreign_transaction")
    if merchant_risk == "high":
        evidence["risk_flags"].append("high_risk_merchant_country")

    envelope = EventEnvelope(
        event_type=EventType.GEO_EVIDENCE_COLLECTED,
        aggregate_id=investigation_id,
        producer="geo-agent",
        stream_version=3,
        workflow_id=state.get("workflow_id"),
        correlation_id=correlation_id,
        causation_id=causation_id,
        trace_id=state.get("trace_id"),
        payload={"investigation_id": investigation_id, "evidence": evidence},
    )
    stored_event_id = await append_event(envelope.to_dict())

    state["geo_evidence"] = evidence
    state["last_event_id"] = stored_event_id  # the STORED id — may differ on activity retry
    logger.info("Geo agent done for %s country=%s vpn=%s flags=%s",
                investigation_id, country, vpn_detected, evidence["risk_flags"])
    return state
