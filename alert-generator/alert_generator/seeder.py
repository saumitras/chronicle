import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
import random

import asyncpg

from alert_generator.seed_data import CUSTOMERS, DEVICES, MERCHANTS, COUNTRY_RISK, build_alert
from chronicle_shared.schema import EventEnvelope
from chronicle_shared.events import EventType

logger = logging.getLogger(__name__)

DB_URL = os.getenv("CHRONICLE_DB_URL", "postgresql://chronicle:chronicle@postgres:5432/chronicle")
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")


async def _conn():
    url = DB_URL.replace("postgresql+asyncpg://", "postgresql://")
    return await asyncpg.connect(url)


async def is_seeded() -> bool:
    conn = await _conn()
    try:
        count = await conn.fetchval("SELECT COUNT(*) FROM seed_customers")
        return count > 0
    finally:
        await conn.close()


async def seed_reference_data() -> None:
    conn = await _conn()
    try:
        # Customers
        await conn.executemany(
            """INSERT INTO seed_customers (customer_id, name, account_age_days, transaction_avg, prior_alerts, risk_profile)
               VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT DO NOTHING""",
            [(c["customer_id"], c["name"], c["account_age_days"],
              c["transaction_avg"], c["prior_alerts"], c["risk_profile"]) for c in CUSTOMERS]
        )

        # Devices
        await conn.executemany(
            """INSERT INTO seed_devices (device_id, customer_id, device_type, known, fraud_flags)
               VALUES ($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING""",
            [(d["device_id"], d["customer_id"], d["device_type"], d["known"], d["fraud_flags"]) for d in DEVICES]
        )

        # Merchants
        await conn.executemany(
            """INSERT INTO seed_merchants (name, category, country, risk_level)
               VALUES ($1,$2,$3,$4) ON CONFLICT DO NOTHING""",
            [(m["name"], m["category"], m["country"], m["risk_level"]) for m in MERCHANTS]
        )

        # Countries
        await conn.executemany(
            """INSERT INTO seed_countries (country_code, country_name, risk_level)
               VALUES ($1,$2,$3) ON CONFLICT DO NOTHING""",
            [(code, code, risk) for code, risk in COUNTRY_RISK.items()]
        )

        logger.info("Reference data seeded: %d customers, %d devices, %d merchants",
                    len(CUSTOMERS), len(DEVICES), len(MERCHANTS))
    finally:
        await conn.close()


def _policy_score(risk_flags: list[str]) -> tuple[float, str]:
    """Same deterministic scoring as agents/policy/agent.py"""
    weights = {
        "prior_fraud_confirmed": 0.40, "unknown_device": 0.15, "prior_fraud_device": 0.20,
        "new_device": 0.10, "vpn_detected": 0.15, "high_risk_country": 0.20,
        "medium_risk_country": 0.08, "foreign_transaction": 0.05,
        "high_risk_merchant_country": 0.15, "multiple_prior_alerts": 0.15,
        "amount_far_above_average": 0.20, "amount_above_average": 0.08, "new_account": 0.10,
    }
    score = min(sum(weights.get(f, 0.05) for f in risk_flags), 1.0)
    if score < 0.35:
        return round(score, 3), "APPROVE"
    if score >= 0.70:
        return round(score, 3), "DENY"
    return round(score, 3), "REVIEW"


async def generate_historical_investigations(n: int = 15) -> int:
    """Write completed investigation event sequences directly to event store.
    No agents run — pure event injection for demo pre-warm."""
    conn = await _conn()

    # Target distribution: ~60% APPROVE, ~20% DENY, ~20% REVIEW (already completed)
    profiles = (
        ["low"] * 9 + ["high"] * 3 + ["medium"] * 3
    )[:n]
    random.shuffle(profiles)

    # Spread timestamps over last 24 hours
    now = datetime.now(timezone.utc)
    interval = timedelta(hours=24) / n

    written = 0
    try:
        for i, risk_profile in enumerate(profiles):
            alert = build_alert(risk_profile)
            inv_id = alert["alert_id"]
            wf_id = f"inv-{inv_id}"
            base_ts = now - timedelta(hours=24) + interval * i

            # Compute synthetic evidence flags
            device_flags = []
            if not alert.get("vpn_detected") is False:
                pass
            geo_flags = []
            if alert.get("vpn_detected"):
                geo_flags.append("vpn_detected")
            country = alert.get("country", "US")
            if country in {"RU", "NG", "KP", "PA", "MT", "BY", "IR", "SY"}:
                geo_flags += ["high_risk_country", "foreign_transaction"]
            customer_flags = []
            amount = alert.get("amount", 0)
            avg = 200.0
            ratio = amount / avg if avg > 0 else 1.0
            if ratio > 5:
                customer_flags.append("amount_far_above_average")
            elif ratio > 2:
                customer_flags.append("amount_above_average")

            all_flags = device_flags + geo_flags + customer_flags
            risk_score, decision = _policy_score(all_flags)

            events = [
                EventEnvelope(event_type=EventType.INVESTIGATION_STARTED, aggregate_id=inv_id,
                              producer="orchestrator", stream_version=1, workflow_id=wf_id,
                              timestamp=(base_ts + timedelta(seconds=0)).isoformat(),
                              payload={"investigation_id": inv_id, "alert_id": inv_id}),
                EventEnvelope(event_type=EventType.DEVICE_EVIDENCE_COLLECTED, aggregate_id=inv_id,
                              producer="device-agent", stream_version=2, workflow_id=wf_id,
                              timestamp=(base_ts + timedelta(seconds=2)).isoformat(),
                              payload={"investigation_id": inv_id, "evidence": {"risk_flags": device_flags}}),
                EventEnvelope(event_type=EventType.GEO_EVIDENCE_COLLECTED, aggregate_id=inv_id,
                              producer="geo-agent", stream_version=3, workflow_id=wf_id,
                              timestamp=(base_ts + timedelta(seconds=4)).isoformat(),
                              payload={"investigation_id": inv_id, "evidence": {"risk_flags": geo_flags, "country": country, "vpn_detected": alert.get("vpn_detected", False)}}),
                EventEnvelope(event_type=EventType.CUSTOMER_EVIDENCE_COLLECTED, aggregate_id=inv_id,
                              producer="customer-agent", stream_version=4, workflow_id=wf_id,
                              timestamp=(base_ts + timedelta(seconds=6)).isoformat(),
                              payload={"investigation_id": inv_id, "evidence": {"risk_flags": customer_flags, "amount_ratio": round(ratio, 2)}}),
                EventEnvelope(event_type=EventType.LLM_REASONING_GENERATED, aggregate_id=inv_id,
                              producer="investigation-agent", stream_version=5, workflow_id=wf_id,
                              timestamp=(base_ts + timedelta(seconds=10)).isoformat(),
                              payload={"investigation_id": inv_id, "reasoning": f"Historical investigation. Risk profile: {risk_profile}. Flags: {all_flags or ['none']}.", "risk_flags": all_flags, "model": "historical"}),
                EventEnvelope(event_type=EventType.RISK_ASSESSED, aggregate_id=inv_id,
                              producer="policy-agent", stream_version=6, workflow_id=wf_id,
                              timestamp=(base_ts + timedelta(seconds=12)).isoformat(),
                              payload={"investigation_id": inv_id, "risk_score": risk_score, "decision": decision, "risk_flags": all_flags}),
                EventEnvelope(event_type=EventType.INVESTIGATION_COMPLETED, aggregate_id=inv_id,
                              producer="orchestrator", stream_version=7, workflow_id=wf_id,
                              timestamp=(base_ts + timedelta(seconds=14)).isoformat(),
                              payload={"investigation_id": inv_id, "decision": decision, "risk_score": risk_score}),
            ]

            # Also write the AlertCreated event so projection picks up alert
            alert_env = EventEnvelope(
                event_type=EventType.ALERT_CREATED, aggregate_id=inv_id,
                producer="alert-generator", stream_version=0,
                timestamp=(base_ts - timedelta(seconds=5)).isoformat(),
                payload=alert,
            )

            for env in [alert_env] + events:
                d = env.to_dict()
                await conn.execute(
                    """INSERT INTO events
                         (event_id, aggregate_id, stream_version, event_type, timestamp,
                          producer, correlation_id, causation_id, workflow_id, trace_id,
                          schema_version, payload)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                       ON CONFLICT (aggregate_id, stream_version) DO NOTHING""",
                    d["event_id"], d["aggregate_id"], d["stream_version"], d["event_type"],
                    datetime.fromisoformat(d["timestamp"]), d["producer"],
                    d.get("correlation_id"), d.get("causation_id"),
                    d.get("workflow_id"), d.get("trace_id"),
                    d.get("schema_version", 1),
                    json.dumps(d["payload"]),
                )

            written += 1

        logger.info("Generated %d historical investigations", written)
        return written
    finally:
        await conn.close()


async def run_seed():
    if await is_seeded():
        logger.info("Already seeded, skipping")
        return {"seeded": False, "reason": "already seeded"}

    await seed_reference_data()
    count = await generate_historical_investigations(15)

    # Trigger projection replay so read models reflect injected events
    try:
        import httpx
        gateway_url = os.getenv("GATEWAY_URL", "http://gateway:8000")
        async with httpx.AsyncClient(timeout=60) as client:
            await client.post(f"{gateway_url}/admin/replay")
        logger.info("Projection replay triggered after seeding")
    except Exception as e:
        logger.warning("Could not trigger replay: %s", e)

    return {"seeded": True, "investigations": count}
