from dataclasses import dataclass, field, asdict
from typing import Any
import uuid
from datetime import datetime, timezone

# Bump when an event payload shape changes; register an upcaster in upcast.py
CURRENT_SCHEMA_VERSION = 1


@dataclass
class EventEnvelope:
    event_type: str
    aggregate_id: str
    payload: dict[str, Any]
    producer: str
    stream_version: int = 1
    # NOTE: these defaults are nondeterministic — never construct an envelope
    # inside Temporal workflow code without passing event_id/timestamp
    # explicitly (use workflow.uuid4() / workflow.now()).
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    correlation_id: str | None = None
    causation_id: str | None = None
    workflow_id: str | None = None
    trace_id: str | None = None
    schema_version: int = CURRENT_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "EventEnvelope":
        return cls(
            event_id=data["event_id"],
            event_type=data["event_type"],
            aggregate_id=data["aggregate_id"],
            stream_version=data["stream_version"],
            timestamp=data["timestamp"],
            producer=data["producer"],
            correlation_id=data.get("correlation_id"),
            causation_id=data.get("causation_id"),
            workflow_id=data.get("workflow_id"),
            trace_id=data.get("trace_id"),
            schema_version=data.get("schema_version", 1),
            payload=data.get("payload", {}),
        )
