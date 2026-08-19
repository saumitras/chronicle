import json
import os
from datetime import datetime

import asyncpg

DB_URL = os.getenv("CHRONICLE_DB_URL", "postgresql://chronicle:chronicle@postgres:5432/chronicle")

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        url = DB_URL.replace("postgresql+asyncpg://", "postgresql://")
        _pool = await asyncpg.create_pool(url, min_size=1, max_size=5)
    return _pool


async def append_event(envelope_dict: dict) -> None:
    """Append an event to the Postgres event store (idempotent on stream position).

    Kafka publication to chronicle.events is handled by the outbox relay.
    """
    pool = await get_pool()
    await pool.execute(
        """
        INSERT INTO events
          (event_id, aggregate_id, stream_version, event_type, timestamp,
           producer, correlation_id, causation_id, workflow_id, trace_id,
           schema_version, payload)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
        ON CONFLICT (aggregate_id, stream_version) DO NOTHING
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
