from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_fresh_player_inherits_repaired_world_after_restart(
    tmp_path: Path,
):
    database_path = tmp_path / "chronicle.db"

    player_a_app = create_app(database_path=database_path)

    with TestClient(player_a_app) as player_a_client:
        session_response = player_a_client.post("/sessions")

        assert session_response.status_code == 201
        player_a_session = session_response.json()

        repair_response = player_a_client.post(
            "/commands/repair-mill",
            headers={
                "Authorization": (
                    f"Bearer {player_a_session['session_token']}"
                ),
            },
            json={
                "command_id": "repair-command-1",
                "expected_revision": 0,
            },
        )

    assert repair_response.status_code == 200

    # A separate app and client simulate a backend restart
    # followed by a fresh Player B connection.
    player_b_app = create_app(database_path=database_path)

    with TestClient(player_b_app) as player_b_client:
        session_response = player_b_client.post("/sessions")

        assert session_response.status_code == 201
        player_b_session = session_response.json()

        world_response = player_b_client.get("/world")

        miller_response = player_b_client.get(
            "/npcs/miller/dialogue"
        )

    assert miller_response.status_code == 200
    assert miller_response.json() == {
        "npc_id": "miller",
        "name": "Miller",
        "dialogue": (
            "The mill wheel is turning again. "
            "Greywater has flour once more."
        ),
    }
    assert player_b_session["player_id"] != (
        player_a_session["player_id"]
    )
    assert player_b_session["session_token"] != (
        player_a_session["session_token"]
    )

    assert world_response.status_code == 200
    assert world_response.json() == {
        "revision": 1,
        "mill_status": "working",
    }