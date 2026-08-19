"""
Chronicle Demo Smoke Tests
Run: pytest tests/smoke/ -v --timeout=180
Or:  make smoke
"""
import asyncio
import os

import pytest
import httpx

GATEWAY = os.getenv("SMOKE_GATEWAY_URL", "http://localhost:8000")
ALERT_GEN = os.getenv("SMOKE_ALERT_GEN_URL", "http://localhost:8001")
POLL = 3


async def get(path, timeout=30):
    async with httpx.AsyncClient(base_url=GATEWAY, timeout=timeout) as c:
        return (await c.get(path)).json()


async def post(path, json=None, base=GATEWAY, timeout=30):
    async with httpx.AsyncClient(base_url=base, timeout=timeout) as c:
        return (await c.post(path, json=json)).json()


async def wait_for_status(inv_id, target_statuses, timeout=90):
    """Poll investigation until status is one of target_statuses."""
    for _ in range(timeout // POLL):
        inv = await get(f"/investigations/{inv_id}")
        if inv.get("status") in target_statuses:
            return inv
        await asyncio.sleep(POLL)
    raise TimeoutError(f"Investigation {inv_id} did not reach {target_statuses} within {timeout}s")


# ── Scenario 1: Happy Path ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scenario1_happy_path():
    # Generate alerts until we get one that auto-completes (no manual review)
    alert_id = None
    for _ in range(8):
        r = await post("/alerts/generate?risk_profile=low", base=ALERT_GEN)
        candidate = r["alert_id"]
        try:
            inv = await wait_for_status(candidate, ["completed", "pending_review"], timeout=60)
            if inv["status"] == "completed":
                alert_id = candidate
                break
            # Got pending_review on a low-risk alert - possible with deterministic hashes
            # Auto-approve it and try another
        except TimeoutError:
            continue

    assert alert_id, "Could not get a completed investigation after 8 attempts"
    inv = await get(f"/investigations/{alert_id}")
    assert inv["status"] == "completed"
    assert inv["decision"] in ("APPROVE", "DENY")
    assert inv["risk_score"] is not None

    events = await get(f"/events/{alert_id}")
    event_types = [e["event_type"] for e in events]
    for expected in [
        "InvestigationStarted", "DeviceEvidenceCollected", "GeoEvidenceCollected",
        "CustomerEvidenceCollected", "LLMReasoningGenerated", "RiskAssessed",
        "InvestigationCompleted",
    ]:
        assert expected in event_types, f"Missing event: {expected}"
    assert "ManualReviewRequested" not in event_types


# ── Scenario 2: Projection Replay ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scenario2_projection_replay():
    stats_before = await get("/dashboard/stats")
    inv_count_before = stats_before["total_investigations"]
    assert inv_count_before > 0

    invs = await get("/investigations?status=completed&limit=1")
    assert invs
    sample_id = invs[0]["investigation_id"]
    sample_before = await get(f"/investigations/{sample_id}")

    # Replay can take a while with many events — give it 120s
    r = await post("/admin/replay", timeout=120)
    assert r["status"] == "done"
    assert r["events_replayed"] > 0

    # The alert generator keeps producing during replay, so new
    # investigations may appear — replay must never LOSE any.
    stats_after = await get("/dashboard/stats")
    assert stats_after["total_investigations"] >= inv_count_before

    sample_after = await get(f"/investigations/{sample_id}")
    assert sample_after["status"] == sample_before["status"]
    assert sample_after["decision"] == sample_before["decision"]


# ── Scenario 3: HITL ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scenario3_hitl():
    # Use medium risk profile which has ~0.35-0.70 score → REVIEW
    # Try up to 15 times to get a REVIEW outcome
    alert_id = None
    for _ in range(15):
        r = await post("/alerts/generate?risk_profile=medium", base=ALERT_GEN)
        candidate = r["alert_id"]
        try:
            inv = await wait_for_status(candidate, ["completed", "pending_review"], timeout=60)
            if inv["status"] == "pending_review":
                alert_id = candidate
                break
        except TimeoutError:
            continue

    assert alert_id, "Could not trigger a REVIEW-path investigation after 15 attempts"

    # Workflow is parked
    pending = await get(f"/investigations/{alert_id}/pending")
    assert pending["waiting"] is True

    # ManualReviewRequested event exists
    events = await get(f"/events/{alert_id}")
    assert "ManualReviewRequested" in [e["event_type"] for e in events]

    # Clarify — workflow stays parked
    clarify_r = await post(f"/investigations/{alert_id}/clarify",
                           json={"reviewer_id": "smoke-test", "question": "Why was this flagged?"})
    assert "answer" in clarify_r
    assert len(clarify_r["answer"]) > 0

    pending2 = await get(f"/investigations/{alert_id}/pending")
    assert pending2["waiting"] is True

    # Approve
    approve_r = await post(f"/investigations/{alert_id}/approve",
                           json={"reviewer_id": "smoke-test", "decision": "approve", "comment": "Smoke test"})
    assert approve_r["status"] == "signalled"

    # Wait for completion
    inv = await wait_for_status(alert_id, ["completed"], timeout=30)
    assert inv["status"] == "completed"
    assert inv["decision"] == "APPROVE"
    assert inv["reviewer_id"] == "smoke-test"

    events_final = await get(f"/events/{alert_id}")
    final_types = [e["event_type"] for e in events_final]
    assert "ManualReviewCompleted" in final_types
    assert "InvestigationCompleted" in final_types
