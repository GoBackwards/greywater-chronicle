import sqlite3
from contextlib import closing
from pathlib import Path

from app.session_store import (
    PlayerSession,
    append_player_session,
    load_player_session,
)


MIGRATION_DIRECTORY = (
    Path(__file__).parents[1] / "migrations"
)

MIGRATION_PATHS = (
    MIGRATION_DIRECTORY / "001_create_chronicle_events.sql",
    MIGRATION_DIRECTORY / "002_create_processed_commands.sql",
    MIGRATION_DIRECTORY / "003_create_player_sessions.sql",
)


def _apply_migrations(
    connection: sqlite3.Connection,
) -> None:
    for migration_path in MIGRATION_PATHS:
        connection.executescript(
            migration_path.read_text(encoding="utf-8")
        )

    connection.commit()


def test_player_session_round_trip(tmp_path: Path):
    database_path = tmp_path / "chronicle.db"

    original = PlayerSession(
        session_token="token-a",
        player_id="player-a",
    )

    with closing(sqlite3.connect(database_path)) as writer:
        _apply_migrations(writer)

        append_player_session(
            connection=writer,
            session=original,
        )
        writer.commit()

    with closing(sqlite3.connect(database_path)) as reader:
        restored = load_player_session(
            connection=reader,
            session_token="token-a",
        )

    assert restored == original
    assert restored is not original

def test_load_player_session_returns_none_for_unknown_token(
    tmp_path: Path,
):
    database_path = tmp_path / "chronicle.db"

    with closing(sqlite3.connect(database_path)) as connection:
        _apply_migrations(connection)

        restored = load_player_session(
            connection=connection,
            session_token="unknown-token",
        )

    assert restored is None