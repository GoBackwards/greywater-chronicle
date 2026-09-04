from pathlib import Path
from contextlib import closing
from fastapi.testclient import TestClient
from app.database import connect_database
from app.session_store import load_player_session
from app.main import create_app

def test_create_session_persists_identity(tmp_path: Path):
    database_path = tmp_path / "chronicle.db"
    test_app = create_app(database_path=database_path)

    with TestClient(test_app) as client:
        response = client.post("/sessions")

    assert response.status_code == 201
    created_session = response.json()

    with closing(connect_database(database_path)) as connection:
        stored_session = load_player_session(
            connection=connection,
            session_token=created_session["session_token"],
        )

    assert stored_session is not None
    assert stored_session.player_id == created_session["player_id"]
    assert (
        stored_session.session_token
        == created_session["session_token"]
    )

def test_create_sessions_returns_distinct_server_identities(
    tmp_path: Path,
):
    test_app = create_app(
        database_path=tmp_path / "chronicle.db"
    )

    with TestClient(test_app) as client:
        first_response = client.post("/sessions")
        second_response = client.post("/sessions")

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    first_session = first_response.json()
    second_session = second_response.json()

    assert set(first_session) == {
        "player_id",
        "session_token",
    }
    assert set(second_session) == {
        "player_id",
        "session_token",
    }

    assert first_session["player_id"]
    assert first_session["session_token"]

    assert (
        first_session["player_id"]
        != second_session["player_id"]
    )
    assert (
        first_session["session_token"]
        != second_session["session_token"]
    )