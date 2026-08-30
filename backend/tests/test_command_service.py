import queue
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

import pytest

from app.chronicle import service as service_module
from app.chronicle.handlers import CommandRejected
from app.chronicle.models import MillRepaired, MillStatus, RepairMill
from app.chronicle.reducer import replay
from app.chronicle.service import (
    IdempotencyConflict,
    RevisionConflict,
    execute_repair_mill,
)
from app.chronicle.store import (
    ProcessedCommand,
    StoredEvent,
    load_events,
    load_processed_command,
)

MIGRATIONS_DIRECTORY = Path(__file__).parents[1] / "migrations"

MIGRATION_PATHS = (
    MIGRATIONS_DIRECTORY / "001_create_chronicle_events.sql",
    MIGRATIONS_DIRECTORY / "002_create_processed_commands.sql",
)


def _apply_migrations(connection: sqlite3.Connection) -> None:
    for migration_path in MIGRATION_PATHS:
        connection.executescript(
            migration_path.read_text(encoding="utf-8")
        )

    connection.commit()


def test_execute_repair_mill_retries_same_command_without_appending(
    tmp_path: Path,
):
    database_path = tmp_path / "chronicle.db"

    with closing(sqlite3.connect(database_path)) as writer:
        writer.execute("PRAGMA foreign_keys = ON")
        _apply_migrations(writer)

        first_result = execute_repair_mill(
            connection=writer,
            command_id="repair-command-1",
            command=RepairMill(),
            actor_id="player-a",
            expected_revision=0,
        )

        retry_result = execute_repair_mill(
            connection=writer,
            command_id="repair-command-1",
            command=RepairMill(),
            actor_id="player-a",
            expected_revision=0,
        )

    with closing(sqlite3.connect(database_path)) as reader:
        stored_events = load_events(reader)
        processed_command = load_processed_command(
            connection=reader,
            command_id="repair-command-1",
        )

    assert retry_result == first_result
    assert stored_events == [first_result]
    assert processed_command == ProcessedCommand(
        command_id="repair-command-1",
        command_type="repair_mill",
        actor_id="player-a",
        expected_revision=0,
        result_revision=1,
    )


def test_execute_repair_mill_persists_first_event(tmp_path: Path):
    database_path = tmp_path / "chronicle.db"

    with closing(sqlite3.connect(database_path)) as writer:
        _apply_migrations(writer)

        result = execute_repair_mill(
            connection=writer,
            command_id="repair-command-1",
            command=RepairMill(),
            actor_id="player-a",
            expected_revision=0,
        )

    # A separate connection proves the service committed its transaction.
    with closing(sqlite3.connect(database_path)) as reader:
        stored_events = load_events(reader)
        processed_command = load_processed_command(
            connection=reader,
            command_id="repair-command-1",
        )

    recovered_state = replay(
        [stored_event.event for stored_event in stored_events]
    )

    assert processed_command == ProcessedCommand(
        command_id="repair-command-1",
        command_type="repair_mill",
        actor_id="player-a",
        expected_revision=0,
        result_revision=1,
    )

    assert result == StoredEvent(
        revision=1,
        event=MillRepaired(actor_id="player-a"),
    )
    assert stored_events == [result]
    assert recovered_state.mill_status is MillStatus.WORKING


def test_execute_repair_mill_rejects_stale_revision_without_appending(
    tmp_path: Path,
):
    database_path = tmp_path / "chronicle.db"

    with closing(sqlite3.connect(database_path)) as writer:
        _apply_migrations(writer)

        first_result = execute_repair_mill(
            connection=writer,
            command_id="repair-command-1",
            command=RepairMill(),
            actor_id="player-a",
            expected_revision=0,
        )

        with pytest.raises(RevisionConflict) as exc_info:
            execute_repair_mill(
                connection=writer,
                command_id="repair-command-2",
                command=RepairMill(),
                actor_id="player-b",
                expected_revision=0,
            )

    with closing(sqlite3.connect(database_path)) as reader:
        stored_events = load_events(reader)

    assert exc_info.value.expected_revision == 0
    assert exc_info.value.actual_revision == 1
    assert stored_events == [first_result]


def test_execute_repair_mill_rejects_already_working_without_appending(
    tmp_path: Path,
):
    database_path = tmp_path / "chronicle.db"

    with closing(sqlite3.connect(database_path)) as writer:
        _apply_migrations(writer)

        first_result = execute_repair_mill(
            connection=writer,
            command_id="repair-command-1",
            command=RepairMill(),
            actor_id="player-a",
            expected_revision=0,
        )

        with pytest.raises(
            CommandRejected,
            match="mill_already_working",
        ):
            execute_repair_mill(
                connection=writer,
                command_id="repair-command-2",
                command=RepairMill(),
                actor_id="player-b",
                expected_revision=1,
            )

    with closing(sqlite3.connect(database_path)) as reader:
        stored_events = load_events(reader)

    assert stored_events == [first_result]


def test_execute_repair_mill_rolls_back_failure_after_append(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    database_path = tmp_path / "chronicle.db"
    real_append_event = service_module.append_event

    def append_then_fail(
        connection: sqlite3.Connection,
        revision: int,
        event: MillRepaired,
    ) -> None:
        real_append_event(
            connection=connection,
            revision=revision,
            event=event,
        )
        raise RuntimeError("simulated_failure_after_append")

    monkeypatch.setattr(
        service_module,
        "append_event",
        append_then_fail,
    )

    with closing(sqlite3.connect(database_path)) as writer:
        _apply_migrations(writer)

        with pytest.raises(
            RuntimeError,
            match="simulated_failure_after_append",
        ):
            execute_repair_mill(
                connection=writer,
                command_id="repair-command-1",
                command=RepairMill(),
                actor_id="player-a",
                expected_revision=0,
            )

        assert load_events(writer) == []
        assert writer.in_transaction is False

    with closing(sqlite3.connect(database_path)) as reader:
        assert load_events(reader) == []


def test_execute_repair_mill_serializes_simultaneous_repairs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    database_path = tmp_path / "chronicle.db"

    with closing(sqlite3.connect(database_path)) as connection:
        _apply_migrations(connection)

    first_has_write_lock = threading.Event()
    second_attempted_begin = threading.Event()
    outcomes: queue.Queue[tuple[str, object]] = queue.Queue()
    real_load_events = service_module.load_events

    def coordinated_load_events(
        connection: sqlite3.Connection,
    ) -> list[StoredEvent]:
        # load_events runs only after BEGIN IMMEDIATE succeeds.
        if threading.current_thread().name == "first-repair":
            first_has_write_lock.set()

            if not second_attempted_begin.wait(timeout=5.0):
                raise TimeoutError(
                    "second repair did not attempt BEGIN IMMEDIATE"
                )

        return real_load_events(connection)

    class BeginSignallingConnection(sqlite3.Connection):
        def execute(self, sql, parameters=(), /):
            if sql.strip().upper() == "BEGIN IMMEDIATE":
                second_attempted_begin.set()

            return super().execute(sql, parameters)

    monkeypatch.setattr(
        service_module,
        "load_events",
        coordinated_load_events,
    )

    def run_first_repair() -> None:
        try:
            with closing(
                sqlite3.connect(database_path, timeout=5.0)
            ) as connection:
                outcome = execute_repair_mill(
                    connection=connection,
                    command_id="repair-command-a",
                    command=RepairMill(),
                    actor_id="player-a",
                    expected_revision=0,
                )
        except Exception as error:
            outcome = error

        outcomes.put(("player-a", outcome))

    def run_second_repair() -> None:
        try:
            if not first_has_write_lock.wait(timeout=5.0):
                raise TimeoutError(
                    "first repair did not acquire the write lock"
                )

            with closing(
                sqlite3.connect(
                    database_path,
                    timeout=5.0,
                    factory=BeginSignallingConnection,
                )
            ) as connection:
                outcome = execute_repair_mill(
                    connection=connection,
                    command_id="repair-command-b",
                    command=RepairMill(),
                    actor_id="player-b",
                    expected_revision=0,
                )
        except Exception as error:
            outcome = error

        outcomes.put(("player-b", outcome))

    first_thread = threading.Thread(
        target=run_first_repair,
        name="first-repair",
        daemon=True,
    )
    second_thread = threading.Thread(
        target=run_second_repair,
        name="second-repair",
        daemon=True,
    )

    first_thread.start()
    second_thread.start()

    first_thread.join(timeout=10.0)
    second_thread.join(timeout=10.0)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()

    observed = dict(
        [
            outcomes.get(timeout=1.0),
            outcomes.get(timeout=1.0),
        ]
    )

    first_outcome = observed["player-a"]
    second_outcome = observed["player-b"]

    assert first_outcome == StoredEvent(
        revision=1,
        event=MillRepaired(actor_id="player-a"),
    )

    assert isinstance(second_outcome, RevisionConflict)
    assert second_outcome.expected_revision == 0
    assert second_outcome.actual_revision == 1

    with closing(sqlite3.connect(database_path)) as reader:
        assert load_events(reader) == [first_outcome]


@pytest.mark.parametrize(
    ("retry_actor_id", "retry_expected_revision"),
    [
        ("player-b", 0),
        ("player-a", 1),
    ],
)
def test_execute_repair_mill_rejects_reused_id_for_different_fingerprint(
    tmp_path: Path,
    retry_actor_id: str,
    retry_expected_revision: int,
):
    database_path = tmp_path / "chronicle.db"

    with closing(sqlite3.connect(database_path)) as writer:
        _apply_migrations(writer)

        first_result = execute_repair_mill(
            connection=writer,
            command_id="repair-command-1",
            command=RepairMill(),
            actor_id="player-a",
            expected_revision=0,
        )

        with pytest.raises(
            IdempotencyConflict,
            match="idempotency_key_reused",
        ) as exc_info:
            execute_repair_mill(
                connection=writer,
                command_id="repair-command-1",
                command=RepairMill(),
                actor_id=retry_actor_id,
                expected_revision=retry_expected_revision,
            )

    with closing(sqlite3.connect(database_path)) as reader:
        stored_events = load_events(reader)
        processed_command = load_processed_command(
            connection=reader,
            command_id="repair-command-1",
        )

    assert exc_info.value.command_id == "repair-command-1"
    assert stored_events == [first_result]
    assert processed_command is not None
    assert processed_command.actor_id == "player-a"
