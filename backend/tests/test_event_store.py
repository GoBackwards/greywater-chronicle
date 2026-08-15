import json
import sqlite3
from contextlib import closing
from pathlib import Path

from app.chronicle.models import MillRepaired, MillStatus
from app.chronicle.reducer import replay
from app.chronicle.store import StoredEvent, append_event, load_events


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "migrations"
    / "001_create_chronicle_events.sql"
)


def test_append_event_persists_encoded_event(tmp_path: Path):
    database_path = tmp_path / "chronicle.db"
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")

    with closing(sqlite3.connect(database_path)) as connection:
        connection.executescript(migration_sql)

        append_event(
            connection=connection,
            revision=1,
            event=MillRepaired(actor_id="player-a"),
        )
        connection.commit()

        row = connection.execute(
            """
            SELECT revision, event_type, schema_version, payload_json
            FROM chronicle_events
            """
        ).fetchone()

    assert row is not None

    revision, event_type, schema_version, payload_json = row

    assert revision == 1
    assert event_type == "mill_repaired"
    assert schema_version == 1
    assert json.loads(payload_json) == {
        "actor_id": "player-a",
    }


def test_load_events_decodes_stored_event(tmp_path: Path):
    database_path = tmp_path / "chronicle.db"
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")
    original = MillRepaired(actor_id="player-a")

    with closing(sqlite3.connect(database_path)) as connection:
        connection.executescript(migration_sql)

        append_event(
            connection=connection,
            revision=1,
            event=original,
        )
        connection.commit()

        stored_events = load_events(connection)

    assert stored_events == [
        StoredEvent(
            revision=1,
            event=MillRepaired(actor_id="player-a"),
        ),
    ]

    assert stored_events[0].event is not original


def test_reopen_database_and_replay_restores_world_state(tmp_path: Path):
    database_path = tmp_path / "chronicle.db"
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")

    # Simulate the first application session.
    with closing(sqlite3.connect(database_path)) as writer:
        writer.executescript(migration_sql)

        append_event(
            connection=writer,
            revision=1,
            event=MillRepaired(actor_id="player-a"),
        )
        writer.commit()

    # The writer is closed. Simulate restarting the application.
    with closing(sqlite3.connect(database_path)) as reader:
        stored_events = load_events(reader)

    recovered_state = replay(
        [stored_event.event for stored_event in stored_events]
    )

    assert [stored_event.revision for stored_event in stored_events] == [1]
    assert recovered_state.mill_status is MillStatus.WORKING


def test_load_events_returns_events_in_revision_order(tmp_path: Path):
    database_path = tmp_path / "chronicle.db"
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")

    with closing(sqlite3.connect(database_path)) as connection:
        connection.executescript(migration_sql)

        # Insert out of order deliberately.
        append_event(
            connection=connection,
            revision=2,
            event=MillRepaired(actor_id="player-b"),
        )
        append_event(
            connection=connection,
            revision=1,
            event=MillRepaired(actor_id="player-a"),
        )
        connection.commit()

        stored_events = load_events(connection)

    assert stored_events == [
        StoredEvent(
            revision=1,
            event=MillRepaired(actor_id="player-a"),
        ),
        StoredEvent(
            revision=2,
            event=MillRepaired(actor_id="player-b"),
        ),
    ]
