import sqlite3

from app.chronicle.handlers import handle_repair_mill
from app.chronicle.models import RepairMill
from app.chronicle.reducer import replay
from app.chronicle.store import (
    ProcessedCommand,
    StoredEvent,
    append_event,
    append_processed_command,
    load_event,
    load_events,
    load_processed_command,
)


class RevisionConflict(Exception):
    def __init__(
        self,
        *,
        expected_revision: int,
        actual_revision: int,
    ) -> None:
        self.expected_revision = expected_revision
        self.actual_revision = actual_revision
        super().__init__("world_revision_conflict")


class IdempotencyConflict(Exception):
    def __init__(self, *, command_id: str) -> None:
        self.command_id = command_id
        super().__init__("idempotency_key_reused")


def execute_repair_mill(
    connection: sqlite3.Connection,
    *,
    command_id: str,
    command: RepairMill,
    actor_id: str,
    expected_revision: int,
) -> StoredEvent:
    connection.execute("BEGIN IMMEDIATE")

    try:
        processed_command = load_processed_command(
            connection=connection,
            command_id=command_id,
        )

        if processed_command is not None:
            same_fingerprint = (
                processed_command.command_type == "repair_mill"
                and processed_command.actor_id == actor_id
                and processed_command.expected_revision == expected_revision
            )

            if not same_fingerprint:
                raise IdempotencyConflict(command_id=command_id)

            result = load_event(
                connection=connection,
                revision=processed_command.result_revision,
            )

            if result is None:
                raise RuntimeError("processed_command_result_missing")

            connection.commit()
            return result

        stored_events = load_events(connection)

        actual_revision = (
            stored_events[-1].revision if stored_events else 0
        )

        if expected_revision != actual_revision:
            raise RevisionConflict(
                expected_revision=expected_revision,
                actual_revision=actual_revision,
            )

        state = replay(
            [stored_event.event for stored_event in stored_events]
        )

        event = handle_repair_mill(
            state=state,
            command=command,
            actor_id=actor_id,
        )

        next_revision = actual_revision + 1

        append_event(
            connection=connection,
            revision=next_revision,
            event=event,
        )

        append_processed_command(
            connection=connection,
            command=ProcessedCommand(
                command_id=command_id,
                command_type="repair_mill",
                actor_id=actor_id,
                expected_revision=expected_revision,
                result_revision=next_revision,
            ),
        )

        result = StoredEvent(
            revision=next_revision,
            event=event,
        )

        connection.commit()
        return result

    except Exception:
        connection.rollback()
        raise
