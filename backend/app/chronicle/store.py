import json
import sqlite3
from dataclasses import dataclass

from app.chronicle.codec import decode_event, encode_event
from app.chronicle.models import MillRepaired


@dataclass(frozen=True)
class StoredEvent:
    revision: int
    event: MillRepaired


def append_event(
    connection: sqlite3.Connection,
    revision: int,
    event: MillRepaired,
) -> None:
    """Insert one accepted event at an explicit Chronicle revision."""
    encoded = encode_event(event)

    payload_json = json.dumps(
        encoded["payload"],
        sort_keys=True,
        separators=(",", ":"),
    )

    connection.execute(
        """
        INSERT INTO chronicle_events (
            revision,
            event_type,
            schema_version,
            payload_json
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            revision,
            encoded["event_type"],
            encoded["schema_version"],
            payload_json,
        ),
    )


def load_events(
    connection: sqlite3.Connection,
) -> list[StoredEvent]:
    """Load Chronicle events in revision order."""
    rows = connection.execute(
        """
        SELECT
            revision,
            event_type,
            schema_version,
            payload_json
        FROM chronicle_events
        ORDER BY revision ASC
        """
    ).fetchall()

    stored_events: list[StoredEvent] = []

    for revision, event_type, schema_version, payload_json in rows:
        payload = json.loads(payload_json)

        encoded_event = {
            "event_type": event_type,
            "schema_version": schema_version,
            "payload": payload,
        }

        event = decode_event(encoded_event)

        stored_events.append(
            StoredEvent(
                revision=revision,
                event=event,
            )
        )

    return stored_events
