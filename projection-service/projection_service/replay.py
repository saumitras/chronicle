import json
import logging

from projection_service.db import get_pool
from projection_service.handlers.event_handlers import handle_event
from projection_service import consumer as kafka_consumer

logger = logging.getLogger(__name__)

_replay_status = "idle"
BATCH_SIZE = 500


def get_replay_status() -> str:
    return _replay_status


def _row_to_event(row) -> dict:
    payload = row["payload"]
    return {
        "event_id": str(row["event_id"]),
        "aggregate_id": str(row["aggregate_id"]),
        "stream_version": row["stream_version"],
        "event_type": row["event_type"],
        "timestamp": row["timestamp"].isoformat(),
        "producer": row["producer"],
        "correlation_id": str(row["correlation_id"]) if row["correlation_id"] else None,
        "causation_id": str(row["causation_id"]) if row["causation_id"] else None,
        "workflow_id": row["workflow_id"],
        "trace_id": row["trace_id"],
        "schema_version": row["schema_version"],
        "payload": payload if isinstance(payload, dict) else json.loads(payload),
    }


async def replay_all() -> dict:
    """Rebuild all read models from the event store.

    Reads the store directly in insertion order (id), paging through the
    whole history — no size cap, no HTTP round-trip through the gateway.
    Replay only folds events into read-model tables; it never causes
    external side effects (no Kafka, no agents, no notifications).
    """
    global _replay_status
    _replay_status = "replaying"

    # Pause the live Kafka consumer during replay
    kafka_consumer.pause()

    try:
        pool = await get_pool()
        await pool.execute("TRUNCATE TABLE investigations, alerts RESTART IDENTITY")
        logger.info("Read models truncated")

        count = 0
        last_id = 0
        while True:
            rows = await pool.fetch(
                """
                SELECT id, event_id, aggregate_id, stream_version, event_type,
                       timestamp, producer, correlation_id, causation_id,
                       workflow_id, trace_id, schema_version, payload
                FROM events
                WHERE id > $1
                ORDER BY id
                LIMIT $2
                """,
                last_id, BATCH_SIZE,
            )
            if not rows:
                break
            for row in rows:
                try:
                    await handle_event(_row_to_event(row))
                    count += 1
                except Exception as e:
                    logger.error("Replay error on event %s: %s", row["event_id"], e)
            last_id = rows[-1]["id"]

        logger.info("Replay complete: %d events replayed", count)
        _replay_status = "done"
        return {"status": "done", "events_replayed": count}

    except Exception as e:
        _replay_status = "error"
        logger.error("Replay failed: %s", e)
        raise
    finally:
        kafka_consumer.resume()
        _replay_status = "idle"
