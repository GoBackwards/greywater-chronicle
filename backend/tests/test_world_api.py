from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app

from contextlib import closing

from app.chronicle.models import MillRepaired
from app.chronicle.store import append_event
from app.database import connect_database


def test_get_world_returns_initial_state(tmp_path: Path):
    test_app = create_app(
        database_path=tmp_path / "chronicle.db"
    )

    with TestClient(test_app) as client:
        response = client.get("/world")

    assert response.status_code == 200
    assert response.json() == {
        "revision": 0,
        "mill_status": "broken",
    }

def test_get_world_replays_persisted_event_after_restart(
    tmp_path: Path,
):
    database_path = tmp_path / "chronicle.db"

    first_app = create_app(database_path=database_path)

    # Starting the first application applies the migrations.
    with TestClient(first_app):
        with closing(
            connect_database(database_path)
        ) as connection:
            append_event(
                connection=connection,
                revision=1,
                event=MillRepaired(actor_id="player-a"),
            )
            connection.commit()

    # A new application instance simulates a backend restart.
    second_app = create_app(database_path=database_path)

    with TestClient(second_app) as client:
        response = client.get("/world")

    assert response.status_code == 200
    assert response.json() == {
        "revision": 1,
        "mill_status": "working",
    }