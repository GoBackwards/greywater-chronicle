import json
import sqlite3
from dataclasses import dataclass

from app.chronicle.codec import decode_event, encode_event
from app.chronicle.models import MillRepaired


@dataclass(frozen=True)
class StoredEvent:
    revision: int
    event: MillRepaired


@dataclass(frozen=True)
class ProcessedCommand:
    command_id: str
    command_type: str
    actor_id: str
    expected_revision: int
    result_revision: int


def append_processed_command(
    connection: sqlite3.Connection,
    command: ProcessedCommand,
) -> None:
    """Record the event produced by one successfully processed command."""
    connection.execute(
        """
        INSERT INTO processed_commands (
            command_id,
            command_type,
            actor_id,
            expected_revision,
            result_revision
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            command.command_id,
            command.command_type,
            command.actor_id,
            command.expected_revision,
            command.result_revision,
        ),
    )


def load_processed_command(
    connection: sqlite3.Connection,
    command_id: str,
) -> ProcessedCommand | None:
    """Load a previously processed command by its idempotency key."""
    row = connection.execute(
        """
        SELECT
            command_id,
            command_type,
            actor_id,
            expected_revision,
            result_revision
        FROM processed_commands
        WHERE command_id = ?
        """,
        (command_id,),
    ).fetchone()

    if row is None:
        return None

    return ProcessedCommand(
        command_id=row[0],
        command_type=row[1],
        actor_id=row[2],
        expected_revision=row[3],
        result_revision=row[4],
    )


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


def _stored_event_from_row(
    row: tuple[int, str, int, str],
) -> StoredEvent:
    revision, event_type, schema_version, payload_json = row

    payload = json.loads(payload_json)

    event = decode_event(
        {
            "event_type": event_type,
            "schema_version": schema_version,
            "payload": payload,
        }
    )

    return StoredEvent(
        revision=revision,
        event=event,
    )


def load_event(
    connection: sqlite3.Connection,
    revision: int,
) -> StoredEvent | None:
    """Load one Chronicle event by its exact revision."""
    row = connection.execute(
        """
        SELECT
            revision,
            event_type,
            schema_version,
            payload_json
        FROM chronicle_events
        WHERE revision = ?
        """,
        (revision,),
    ).fetchone()

    if row is None:
        return None

    return _stored_event_from_row(row)


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

    return [_stored_event_from_row(row) for row in rows]
