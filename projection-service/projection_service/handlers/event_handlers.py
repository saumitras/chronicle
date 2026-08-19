import json
import logging
from datetime import datetime, timezone

from chronicle_shared.events import EventType
from chronicle_shared.upcast import upcast

from projection_service.db import get_pool

logger = logging.getLogger(__name__)


async def handle_event(event: dict) -> None:
    # Translate old stored shapes to the current schema before folding
    event = upcast(dict(event))
    event_type = event.get("event_type")
    payload = event.get("payload", {})
    if isinstance(payload, str):
        payload = json.loads(payload)

    try:
        if event_type == EventType.ALERT_CREATED:
            await _handle_alert_created(payload, event)
        elif event_type == EventType.INVESTIGATION_STARTED:
            await _handle_investigation_started(payload, event)
        elif event_type == EventType.RISK_ASSESSED:
            await _handle_risk_assessed(payload)
        elif event_type == EventType.MANUAL_REVIEW_REQUESTED:
            await _handle_manual_review_requested(payload)
        elif event_type == EventType.MANUAL_REVIEW_COMPLETED:
            await _handle_manual_review_completed(payload)
        elif event_type == EventType.INVESTIGATION_COMPLETED:
            await _handle_investigation_completed(payload)
    except Exception as e:
        logger.error("Handler error for %s: %s", event_type, e)
        raise


async def _handle_alert_created(payload: dict, event: dict) -> None:
    pool = await get_pool()
    await pool.execute(
        """
        INSERT INTO alerts
          (alert_id, customer_id, account_id, device_id, merchant, amount,
           currency, country, vpn_detected, status, payload, created_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'pending',$10,$11)
        ON CONFLICT (alert_id) DO NOTHING
        """,
        payload["alert_id"], payload["customer_id"],
        payload.get("account_id"), payload.get("device_id"),
        payload.get("merchant"), payload.get("amount"),
        payload.get("currency", "USD"), payload.get("country"),
        payload.get("vpn_detected", False),
        json.dumps(payload),
        datetime.fromisoformat(event["timestamp"]) if "timestamp" in event else datetime.now(timezone.utc),
    )


async def _handle_investigation_started(payload: dict, event: dict) -> None:
    now = datetime.now(timezone.utc)
    pool = await get_pool()
    await pool.execute(
        """
        INSERT INTO investigations
          (investigation_id, alert_id, workflow_id, status, payload, created_at, updated_at)
        VALUES ($1,$2,$3,'running',$4,$5,$5)
        ON CONFLICT (investigation_id) DO NOTHING
        """,
        payload["investigation_id"], payload["alert_id"],
        event.get("workflow_id"), json.dumps(payload), now,
    )


async def _handle_risk_assessed(payload: dict) -> None:
    pool = await get_pool()
    await pool.execute(
        """
        UPDATE investigations
        SET risk_score=$1, decision=$2, updated_at=$3
        WHERE investigation_id=$4
        """,
        payload.get("risk_score"), payload.get("decision"),
        datetime.now(timezone.utc), payload["investigation_id"],
    )


async def _handle_manual_review_requested(payload: dict) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE investigations SET status='pending_review', updated_at=$1 WHERE investigation_id=$2",
        datetime.now(timezone.utc), payload["investigation_id"],
    )


async def _handle_manual_review_completed(payload: dict) -> None:
    pool = await get_pool()
    await pool.execute(
        """
        UPDATE investigations
        SET reviewer_id=$1, reviewer_comment=$2, decision=$3, updated_at=$4
        WHERE investigation_id=$5
        """,
        payload.get("reviewer_id"), payload.get("comment"),
        payload.get("decision"), datetime.now(timezone.utc),
        payload["investigation_id"],
    )


async def _handle_investigation_completed(payload: dict) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE investigations
            SET status='completed', decision=$1, risk_score=$2, updated_at=$3
            WHERE investigation_id=$4
            """,
            payload.get("decision"), payload.get("risk_score"),
            datetime.now(timezone.utc), payload["investigation_id"],
        )
        # Mark alert as processed
        row = await conn.fetchrow(
            "SELECT alert_id FROM investigations WHERE investigation_id=$1",
            payload["investigation_id"],
        )
        if row:
            await conn.execute(
                "UPDATE alerts SET status='processed' WHERE alert_id=$1",
                row["alert_id"],
            )
