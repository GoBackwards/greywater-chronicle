import sqlite3
from contextlib import closing
from pathlib import Path

from app.chronicle.models import MillRepaired
from app.chronicle.store import (
    ProcessedCommand,
    append_event,
    append_processed_command,
    load_processed_command,
)


MIGRATION_PATHS = (
    Path(__file__).parents[1]
    / "migrations"
    / "001_create_chronicle_events.sql",
    Path(__file__).parents[1]
    / "migrations"
    / "002_create_processed_commands.sql",
)


def _apply_migrations(connection: sqlite3.Connection) -> None:
    for migration_path in MIGRATION_PATHS:
        connection.executescript(
            migration_path.read_text(encoding="utf-8")
        )

    connection.commit()


def test_processed_command_round_trip(tmp_path: Path):
    database_path = tmp_path / "chronicle.db"

    original = ProcessedCommand(
        command_id="repair-command-1",
        command_type="repair_mill",
        actor_id="player-a",
        expected_revision=0,
        result_revision=1,
    )

    with closing(sqlite3.connect(database_path)) as writer:
        writer.execute("PRAGMA foreign_keys = ON")
        _apply_migrations(writer)

        append_event(
            connection=writer,
            revision=1,
            event=MillRepaired(actor_id="player-a"),
        )
        append_processed_command(
            connection=writer,
            command=original,
        )
        writer.commit()

    with closing(sqlite3.connect(database_path)) as reader:
        restored = load_processed_command(
            connection=reader,
            command_id="repair-command-1",
        )

    assert restored == original
    assert restored is not original


def test_load_processed_command_returns_none_for_unknown_id(
    tmp_path: Path,
):
    database_path = tmp_path / "chronicle.db"

    with closing(sqlite3.connect(database_path)) as connection:
        _apply_migrations(connection)

        restored = load_processed_command(
            connection=connection,
            command_id="never-processed",
        )

    assert restored is None
