import sqlite3
from contextlib import closing
from pathlib import Path

import pytest


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "migrations"
    / "001_create_chronicle_events.sql"
)


def _apply_initial_migration(connection: sqlite3.Connection) -> None:
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")
    connection.executescript(migration_sql)
    connection.commit()


def test_initial_migration_creates_chronicle_events_table(tmp_path: Path):
    database_path = tmp_path / "chronicle.db"

    with closing(sqlite3.connect(database_path)) as connection:
        _apply_initial_migration(connection)

        columns = connection.execute(
            "PRAGMA table_info(chronicle_events)"
        ).fetchall()

    assert [column[1] for column in columns] == [
        "revision",
        "event_type",
        "schema_version",
        "payload_json",
    ]

    primary_key_positions = {
        column[1]: column[5]
        for column in columns
    }

    assert primary_key_positions["revision"] == 1


def test_revision_is_unique_in_shared_world(tmp_path: Path):
    database_path = tmp_path / "chronicle.db"

    insert_event = """
        INSERT INTO chronicle_events (
            revision,
            event_type,
            schema_version,
            payload_json
        )
        VALUES (?, ?, ?, ?)
    """

    with closing(sqlite3.connect(database_path)) as connection:
        _apply_initial_migration(connection)

        connection.execute(
            insert_event,
            (
                1,
                "mill_repaired",
                1,
                '{"actor_id":"player-a"}',
            ),
        )

        # The next revision is legal in the same shared world.
        connection.execute(
            insert_event,
            (
                2,
                "mill_repaired",
                1,
                '{"actor_id":"player-b"}',
            ),
        )

        connection.commit()

        # A revision cannot occur twice in the shared Chronicle.
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                insert_event,
                (
                    1,
                    "mill_repaired",
                    1,
                    '{"actor_id":"player-c"}',
                ),
            )

        row_count = connection.execute(
            "SELECT COUNT(*) FROM chronicle_events"
        ).fetchone()[0]

    assert row_count == 2
