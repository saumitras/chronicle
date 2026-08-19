import logging
from temporalio import activity

from agents.shared.event_writer import append_event
from chronicle_shared.schema import EventEnvelope
from chronicle_shared.events import EventType

logger = logging.getLogger(__name__)

FLAG_WEIGHTS = {
    "prior_fraud_confirmed":        0.40,
    "unknown_device":               0.15,
    "prior_fraud_device":           0.20,
    "new_device":                   0.10,
    "vpn_detected":                 0.15,
    "high_risk_country":            0.20,
    "medium_risk_country":          0.08,
    "foreign_transaction":          0.05,
    "high_risk_merchant_country":   0.15,
    "multiple_prior_alerts":        0.15,
    "amount_far_above_average":     0.20,
    "amount_above_average":         0.08,
    "new_account":                  0.10,
}

APPROVE_THRESHOLD = 0.35
DENY_THRESHOLD = 0.70

# Evidence sources the decision assumes it has seen. Scoring is additive and
# monotonic — every flag can only raise the score — so a missing source can
# only ever UNDERSTATE risk. That asymmetry drives the rule below: DENY and
# REVIEW stay sound on partial evidence, APPROVE does not.
REQUIRED_EVIDENCE = ("device", "geo", "customer")


def _coverage(state: dict) -> tuple[list[str], list[str]]:
    """Which required evidence sources actually reported for this case."""
    present = [s for s in REQUIRED_EVIDENCE if state.get(f"{s}_evidence")]
    missing = [s for s in REQUIRED_EVIDENCE if s not in present]
    return present, missing


def _calculate_score(risk_flags: list[str]) -> float:
    unknown = [f for f in risk_flags if f not in FLAG_WEIGHTS]
    if unknown:
        # An unrecognized flag must never silently contribute to the score —
        # the weight table is the complete, auditable decision surface.
        logger.warning("Ignoring unknown risk flags (no weight defined): %s", unknown)
    return min(round(sum(FLAG_WEIGHTS.get(f, 0.0) for f in risk_flags), 3), 1.0)


@activity.defn
async def run_policy_agent(state: dict) -> dict:
    investigation_id = state["investigation_id"]
    all_flags = state.get("all_risk_flags", [])
    correlation_id = state.get("correlation_id", investigation_id)
    causation_id = state.get("last_event_id")

    risk_score = _calculate_score(all_flags)
    present, missing = _coverage(state)
    coverage_complete = not missing
    coverage_forced_review = False

    if risk_score >= DENY_THRESHOLD:
        # Sound on partial evidence: the score can only go up from here.
        decision = "DENY"
        requires_review = False
    elif risk_score < APPROVE_THRESHOLD and coverage_complete:
        decision = "APPROVE"
        requires_review = False
    else:
        decision = "REVIEW"
        requires_review = True
        # A low score reached without full coverage is not a clean bill of
        # health — absent evidence is not exonerating evidence.
        coverage_forced_review = risk_score < APPROVE_THRESHOLD

    envelope = EventEnvelope(
        event_type=EventType.RISK_ASSESSED,
        aggregate_id=investigation_id,
        producer="policy-agent",
        stream_version=6,
        workflow_id=state.get("workflow_id"),
        correlation_id=correlation_id,
        causation_id=causation_id,
        trace_id=state.get("trace_id"),
        payload={
            "investigation_id": investigation_id,
            "risk_score": risk_score,
            "decision": decision,
            "risk_flags": all_flags,
            "approve_threshold": APPROVE_THRESHOLD,
            "deny_threshold": DENY_THRESHOLD,
            # What the decision was actually based on — a verdict is only as
            # defensible as the evidence coverage behind it.
            "evidence_coverage": {
                "complete": coverage_complete,
                "present": present,
                "missing": missing,
            },
            "coverage_forced_review": coverage_forced_review,
        },
    )
    stored_event_id = await append_event(envelope.to_dict())

    state["risk_score"] = risk_score
    state["decision"] = decision
    state["requires_review"] = requires_review
    state["last_event_id"] = stored_event_id  # the STORED id — may differ on activity retry

    logger.info("Policy agent done for %s score=%.3f decision=%s coverage=%s%s",
                investigation_id, risk_score, decision,
                "complete" if coverage_complete else f"missing={missing}",
                " (coverage forced review)" if coverage_forced_review else "")
    return state
