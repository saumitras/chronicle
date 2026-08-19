"""Schema-version upcasting for stored events.

Old events are immutable and keep the shape they were written with. When a
payload shape changes, bump CURRENT_SCHEMA_VERSION in schema.py and register
an upcaster here that translates (event_type, old_version) -> old_version + 1.
Consumers call upcast() before handling, so read models always see the
current shape without ever rewriting history.
"""

import logging
from typing import Callable

from chronicle_shared.schema import CURRENT_SCHEMA_VERSION

logger = logging.getLogger(__name__)

# (event_type, from_version) -> function(envelope_dict) -> envelope_dict
# Each upcaster must set schema_version = from_version + 1 on its result.
UPCASTERS: dict[tuple[str, int], Callable[[dict], dict]] = {}


def register(event_type: str, from_version: int):
    """Decorator: register an upcaster for one event type and version step."""
    def wrap(fn: Callable[[dict], dict]):
        UPCASTERS[(event_type, from_version)] = fn
        return fn
    return wrap


def upcast(envelope: dict) -> dict:
    """Translate a stored envelope to the current schema version at read time."""
    version = envelope.get("schema_version", 1)
    envelope["schema_version"] = version  # normalize pre-versioning events
    while version < CURRENT_SCHEMA_VERSION:
        fn = UPCASTERS.get((envelope["event_type"], version))
        if fn is None:
            # No shape change for this event type at this step
            version += 1
            envelope["schema_version"] = version
            continue
        envelope = fn(envelope)
        new_version = envelope.get("schema_version", version)
        if new_version <= version:
            raise ValueError(
                f"Upcaster for ({envelope['event_type']}, {version}) "
                f"did not advance schema_version"
            )
        version = new_version
    return envelope


# Example (kept as documentation until the first real migration):
#
# @register("DeviceEvidenceCollected", 1)
# def _device_evidence_v1_to_v2(env: dict) -> dict:
#     env["payload"]["device"] = {"id": env["payload"].pop("device_id")}
#     env["schema_version"] = 2
#     return env
