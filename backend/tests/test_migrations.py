import sqlite3
from contextlib import closing
from pathlib import Path

import pytest


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "migrations"
    / "001_create_chronicle_events.sql"
)

PROCESSED_COMMANDS_MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "migrations"
    / "002_create_processed_commands.sql"
)

PLAYER_SESSIONS_MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "migrations"
    / "003_create_player_sessions.sql"
)

def _apply_initial_migration(connection: sqlite3.Connection) -> None:
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")
    connection.executescript(migration_sql)
    connection.commit()


def _apply_processed_commands_migration(
    connection: sqlite3.Connection,
) -> None:
    migration_sql = PROCESSED_COMMANDS_MIGRATION_PATH.read_text(
        encoding="utf-8"
    )
    connection.executescript(migration_sql)
    connection.commit()

def _apply_player_sessions_migration(
    connection: sqlite3.Connection,
) -> None:
    migration_sql = PLAYER_SESSIONS_MIGRATION_PATH.read_text(
        encoding="utf-8"
    )
    connection.executescript(migration_sql)
    connection.commit()

def test_player_sessions_migration_creates_table(
    tmp_path: Path,
):
    database_path = tmp_path / "chronicle.db"

    with closing(sqlite3.connect(database_path)) as connection:
        # Migrations must be applied in historical order.
        _apply_initial_migration(connection)
        _apply_processed_commands_migration(connection)
        _apply_player_sessions_migration(connection)

        columns = connection.execute(
            "PRAGMA table_info(player_sessions)"
        ).fetchall()

    assert [(column[1], column[2]) for column in columns] == [
        ("session_token", "TEXT"),
        ("player_id", "TEXT"),
    ]

    primary_key_positions = {
        column[1]: column[5]
        for column in columns
    }

    assert primary_key_positions["session_token"] == 1
    assert all(column[3] == 1 for column in columns)

def test_player_id_is_unique_across_sessions(
    tmp_path: Path,
):
    database_path = tmp_path / "chronicle.db"

    insert_session = """
        INSERT INTO player_sessions (
            session_token,
            player_id
        )
        VALUES (?, ?)
    """

    with closing(sqlite3.connect(database_path)) as connection:
        _apply_initial_migration(connection)
        _apply_processed_commands_migration(connection)
        _apply_player_sessions_migration(connection)

        connection.execute(
            insert_session,
            ("token-a", "player-a"),
        )
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                insert_session,
                ("token-b", "player-a"),
            )

        row_count = connection.execute(
            "SELECT COUNT(*) FROM player_sessions"
        ).fetchone()[0]

    assert row_count == 1

def test_processed_commands_migration_creates_table(tmp_path: Path):
    database_path = tmp_path / "chronicle.db"

    with closing(sqlite3.connect(database_path)) as connection:
        # Migrations must be applied in historical order.
        _apply_initial_migration(connection)
        _apply_processed_commands_migration(connection)

        columns = connection.execute(
            "PRAGMA table_info(processed_commands)"
        ).fetchall()

    assert [(column[1], column[2]) for column in columns] == [
        ("command_id", "TEXT"),
        ("command_type", "TEXT"),
        ("actor_id", "TEXT"),
        ("expected_revision", "INTEGER"),
        ("result_revision", "INTEGER"),
    ]

    primary_key_positions = {column[1]: column[5] for column in columns}

    assert primary_key_positions["command_id"] == 1
    assert all(column[3] == 1 for column in columns)


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

    primary_key_positions = {column[1]: column[5] for column in columns}

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


def test_processed_command_id_is_unique(tmp_path: Path):
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

    insert_command = """
        INSERT INTO processed_commands (
            command_id,
            command_type,
            actor_id,
            expected_revision,
            result_revision
        )
        VALUES (?, ?, ?, ?, ?)
    """

    with closing(sqlite3.connect(database_path)) as connection:
        _apply_initial_migration(connection)
        _apply_processed_commands_migration(connection)

        # Both result revisions exist and are different. Therefore, the only
        # violated constraint below should be the repeated command_id.
        connection.execute(
            insert_event,
            (1, "mill_repaired", 1, '{"actor_id":"player-a"}'),
        )
        connection.execute(
            insert_event,
            (2, "mill_repaired", 1, '{"actor_id":"player-b"}'),
        )

        connection.execute(
            insert_command,
            (
                "repair-command-1",
                "repair_mill",
                "player-a",
                0,
                1,
            ),
        )
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                insert_command,
                (
                    "repair-command-1",
                    "repair_mill",
                    "player-b",
                    1,
                    2,
                ),
            )

        row_count = connection.execute(
            "SELECT COUNT(*) FROM processed_commands"
        ).fetchone()[0]

    assert row_count == 1


def test_processed_command_result_revision_is_unique(tmp_path: Path):
    database_path = tmp_path / "chronicle.db"

    insert_command = """
        INSERT INTO processed_commands (
            command_id,
            command_type,
            actor_id,
            expected_revision,
            result_revision
        )
        VALUES (?, ?, ?, ?, ?)
    """

    with closing(sqlite3.connect(database_path)) as connection:
        _apply_initial_migration(connection)
        _apply_processed_commands_migration(connection)

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
            (1, "mill_repaired", 1, '{"actor_id":"player-a"}'),
        )

        connection.execute(
            insert_command,
            (
                "repair-command-1",
                "repair_mill",
                "player-a",
                0,
                1,
            ),
        )
        connection.commit()

        # Different command ID, but it tries to claim the same event.
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                insert_command,
                (
                    "repair-command-2",
                    "repair_mill",
                    "player-b",
                    0,
                    1,
                ),
            )

        row_count = connection.execute(
            "SELECT COUNT(*) FROM processed_commands"
        ).fetchone()[0]

    assert row_count == 1


def test_processed_command_requires_existing_result_event(
    tmp_path: Path,
):
    database_path = tmp_path / "chronicle.db"

    with closing(sqlite3.connect(database_path)) as connection:
        # SQLite foreign-key enforcement is configured per connection.
        # Enable it before beginning any transaction.
        connection.execute("PRAGMA foreign_keys = ON")

        foreign_keys_enabled = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]

        assert foreign_keys_enabled == 1

        _apply_initial_migration(connection)
        _apply_processed_commands_migration(connection)

        # Revision 999 satisfies the positive-number CHECK, but no such
        # Chronicle event exists. Only the foreign key should reject it.
        with pytest.raises(sqlite3.IntegrityError):
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
                    "repair-command-1",
                    "repair_mill",
                    "player-a",
                    0,
                    999,
                ),
            )

        row_count = connection.execute(
            "SELECT COUNT(*) FROM processed_commands"
        ).fetchone()[0]

    assert row_count == 0
