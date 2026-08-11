from collections.abc import Mapping

from app.chronicle.models import MillRepaired


class EventCodecError(ValueError):
    """Stored event data cannot be safely encoded or decoded."""


def encode_event(event: MillRepaired) -> dict[str, object]:
    """Convert a domain event into stable, JSON-compatible data."""
    return {
        "event_type": "mill_repaired",
        "schema_version": 1,
        "payload": {
            "actor_id": event.actor_id,
        },
    }

def decode_event(data: Mapping[str, object]) -> MillRepaired:
    """Reconstruct a domain event from stored versioned data."""
    event_type = data.get("event_type")

    if event_type != "mill_repaired":
        raise EventCodecError("unsupported_event_type")

    schema_version = data.get("schema_version")

    if type(schema_version) is not int or schema_version != 1:
        raise EventCodecError("unsupported_schema_version")

    payload = data.get("payload")

    if not isinstance(payload, Mapping):
        raise EventCodecError("invalid_event_payload")

    actor_id = payload.get("actor_id")

    if not isinstance(actor_id, str):
        raise EventCodecError("invalid_actor_id")

    return MillRepaired(actor_id=actor_id)