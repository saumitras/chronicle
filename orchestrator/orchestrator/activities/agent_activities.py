import json
import logging
from datetime import datetime

from temporalio import activity

from orchestrator.db import get_pool

logger = logging.getLogger(__name__)


@activity.defn
async def append_event(envelope_dict: dict) -> dict:
    """Append event to the Postgres event store.

    Returns the envelope with event_id set to the STORED row's id: a retried
    activity whose earlier attempt already appended this stream position
    loses the conflict, and downstream causation must chain from the id that
    actually exists in the store.

    Kafka publication is handled by the outbox relay, which tails committed
    rows in the events table — not here. Writing to the store and the bus
    from the same code path is a dual write: a publish failure would leave
    an event durable but never projected.
    """
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO events
          (event_id, aggregate_id, stream_version, event_type, timestamp,
           producer, correlation_id, causation_id, workflow_id, trace_id,
           schema_version, payload)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
        ON CONFLICT (aggregate_id, stream_version) DO NOTHING
        RETURNING event_id
        """,
        envelope_dict["event_id"],
        envelope_dict["aggregate_id"],
        envelope_dict["stream_version"],
        envelope_dict["event_type"],
        datetime.fromisoformat(envelope_dict["timestamp"]),
        envelope_dict["producer"],
        envelope_dict.get("correlation_id"),
        envelope_dict.get("causation_id"),
        envelope_dict.get("workflow_id"),
        envelope_dict.get("trace_id"),
        envelope_dict.get("schema_version", 1),
        json.dumps(envelope_dict["payload"]),
    )
    if row:
        stored_event_id = str(row["event_id"])
    else:
        stored_event_id = str(await pool.fetchval(
            "SELECT event_id FROM events WHERE aggregate_id=$1 AND stream_version=$2",
            envelope_dict["aggregate_id"], envelope_dict["stream_version"],
        ))
    envelope_dict["event_id"] = stored_event_id
    logger.info("Appended event %s type=%s", stored_event_id, envelope_dict["event_type"])
    return envelope_dict


@activity.defn
async def send_hitl_notification(investigation_id: str, risk_score: float, workflow_id: str) -> None:
    """Send HITL notification via configured channel (email or Slack)."""
    from orchestrator.notifier import notify_review_requested
    await notify_review_requested(investigation_id, risk_score, workflow_id)
