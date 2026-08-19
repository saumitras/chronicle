import json
import logging
from datetime import datetime

from agents.shared.db import get_pool

logger = logging.getLogger(__name__)


async def append_event(envelope_dict: dict) -> str:
    """Append event to the Postgres event store; return the STORED event_id.

    The write is idempotent: (aggregate_id, stream_version) is unique and a
    retried append lands as a no-op. An activity may re-execute after a
    previous attempt already appended this position (worker crashed before
    Temporal recorded completion) — in that case the retry generates a fresh
    envelope whose event_id loses the conflict. Callers must chain causation
    from the id returned here, never from the id they generated, or the
    causation chain can point at an event that was never stored.

    Kafka publication is NOT done here — the outbox relay tails the events
    table and publishes committed rows (no dual write).
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
        return str(row["event_id"])
    # Conflict: an earlier attempt owns this stream position — return its id.
    stored = await pool.fetchval(
        "SELECT event_id FROM events WHERE aggregate_id=$1 AND stream_version=$2",
        envelope_dict["aggregate_id"], envelope_dict["stream_version"],
    )
    return str(stored)
