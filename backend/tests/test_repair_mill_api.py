from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_repair_mill_rejects_missing_session_token(
    tmp_path: Path,
):
    test_app = create_app(
        database_path=tmp_path / "chronicle.db"
    )

    with TestClient(test_app) as client:
        response = client.post(
            "/commands/repair-mill",
            json={
                "command_id": "repair-command-1",
                "expected_revision": 0,
            },
        )
        world_response = client.get("/world")

    assert response.status_code == 401
    assert response.json() == {
        "detail": {"code": "invalid_session"}
    }
    assert response.headers["www-authenticate"] == "Bearer"

    assert world_response.json() == {
        "revision": 0,
        "mill_status": "broken",
    }

def test_repair_mill_rejects_unknown_session_token(
    tmp_path: Path,
):
    test_app = create_app(
        database_path=tmp_path / "chronicle.db"
    )

    with TestClient(test_app) as client:
        response = client.post(
            "/commands/repair-mill",
            headers={
                "Authorization": "Bearer unknown-token",
            },
            json={
                "command_id": "repair-command-1",
                "expected_revision": 0,
            },
        )
        world_response = client.get("/world")

    assert response.status_code == 401
    assert response.json() == {
        "detail": {"code": "invalid_session"}
    }
    assert response.headers["www-authenticate"] == "Bearer"

    assert world_response.json() == {
        "revision": 0,
        "mill_status": "broken",
    }

def test_repair_mill_rejects_client_supplied_actor_id(
    tmp_path: Path,
):
    test_app = create_app(
        database_path=tmp_path / "chronicle.db"
    )

    with TestClient(test_app) as client:
        session_response = client.post("/sessions")
        session = session_response.json()

        response = client.post(
            "/commands/repair-mill",
            headers={
                "Authorization": (
                    f"Bearer {session['session_token']}"
                ),
            },
            json={
                "command_id": "repair-command-1",
                "expected_revision": 0,
                "actor_id": "spoofed-player",
            },
        )
        world_response = client.get("/world")

    assert response.status_code == 422

    validation_errors = response.json()["detail"]

    assert any(
        error["loc"] == ["body", "actor_id"]
        and error["type"] == "extra_forbidden"
        for error in validation_errors
    )

    assert world_response.json() == {
        "revision": 0,
        "mill_status": "broken",
    }

def test_authenticated_session_repairs_mill_as_its_player(
    tmp_path: Path,
):
    test_app = create_app(
        database_path=tmp_path / "chronicle.db"
    )

    with TestClient(test_app) as client:
        session_response = client.post("/sessions")

        assert session_response.status_code == 201
        session = session_response.json()

        response = client.post(
            "/commands/repair-mill",
            headers={
                "Authorization": (
                    f"Bearer {session['session_token']}"
                ),
            },
            json={
                "command_id": "repair-command-1",
                "expected_revision": 0,
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "revision": 1,
        "event_type": "mill_repaired",
        "actor_id": session["player_id"],
    }


def test_repair_mill_rejects_stale_revision(
    tmp_path: Path,
):
    test_app = create_app(
        database_path=tmp_path / "chronicle.db"
    )

    with TestClient(test_app) as client:
        session_response = client.post("/sessions")

        assert session_response.status_code == 201
        session = session_response.json()

        headers = {
            "Authorization": (
                f"Bearer {session['session_token']}"
            ),
        }

        first_response = client.post(
            "/commands/repair-mill",
            headers=headers,
            json={
                "command_id": "repair-command-1",
                "expected_revision": 0,
            },
        )

        assert first_response.status_code == 200

        # New command, but based on an outdated world revision.
        second_response = client.post(
            "/commands/repair-mill",
            headers=headers,
            json={
                "command_id": "repair-command-2",
                "expected_revision": 0,
            },
        )

        world_response = client.get("/world")

    assert second_response.status_code == 409
    assert second_response.json() == {
        "detail": {
            "code": "world_revision_conflict",
            "expected_revision": 0,
            "actual_revision": 1,
        }
    }

    assert world_response.status_code == 200
    assert world_response.json() == {
        "revision": 1,
        "mill_status": "working",
    }

def test_repair_mill_retry_returns_original_result(
    tmp_path: Path,
):
    test_app = create_app(
        database_path=tmp_path / "chronicle.db"
    )

    with TestClient(test_app) as client:
        session_response = client.post("/sessions")

        assert session_response.status_code == 201
        session = session_response.json()

        headers = {
            "Authorization": (
                f"Bearer {session['session_token']}"
            ),
        }
        payload = {
            "command_id": "repair-command-1",
            "expected_revision": 0,
        }

        first_response = client.post(
            "/commands/repair-mill",
            headers=headers,
            json=payload,
        )

        assert first_response.status_code == 200

        retry_response = client.post(
            "/commands/repair-mill",
            headers=headers,
            json=payload,
        )

        world_response = client.get("/world")

    assert retry_response.status_code == 200
    assert retry_response.json() == first_response.json()

    assert world_response.status_code == 200
    assert world_response.json() == {
        "revision": 1,
        "mill_status": "working",
    }

def test_repair_mill_rejects_already_working_mill(
    tmp_path: Path,
):
    test_app = create_app(
        database_path=tmp_path / "chronicle.db"
    )

    with TestClient(test_app) as client:
        session_response = client.post("/sessions")

        assert session_response.status_code == 201
        session = session_response.json()

        headers = {
            "Authorization": (
                f"Bearer {session['session_token']}"
            ),
        }

        first_response = client.post(
            "/commands/repair-mill",
            headers=headers,
            json={
                "command_id": "repair-command-1",
                "expected_revision": 0,
            },
        )

        assert first_response.status_code == 200

        second_response = client.post(
            "/commands/repair-mill",
            headers=headers,
            json={
                "command_id": "repair-command-2",
                "expected_revision": 1,
            },
        )

        world_response = client.get("/world")

    assert second_response.status_code == 409
    assert second_response.json() == {
        "detail": {
            "code": "mill_already_working",
        }
    }

    assert world_response.status_code == 200
    assert world_response.json() == {
        "revision": 1,
        "mill_status": "working",
    }

def test_repair_mill_rejects_reused_id_with_changed_request(
    tmp_path: Path,
):
    test_app = create_app(
        database_path=tmp_path / "chronicle.db"
    )

    with TestClient(test_app) as client:
        session_response = client.post("/sessions")

        assert session_response.status_code == 201
        session = session_response.json()

        headers = {
            "Authorization": (
                f"Bearer {session['session_token']}"
            ),
        }

        first_response = client.post(
            "/commands/repair-mill",
            headers=headers,
            json={
                "command_id": "repair-command-1",
                "expected_revision": 0,
            },
        )

        assert first_response.status_code == 200

        second_response = client.post(
            "/commands/repair-mill",
            headers=headers,
            json={
                "command_id": "repair-command-1",
                "expected_revision": 1,
            },
        )

        world_response = client.get("/world")

    assert second_response.status_code == 409
    assert second_response.json() == {
        "detail": {
            "code": "idempotency_key_reused",
            "command_id": "repair-command-1",
        }
    }

    assert world_response.status_code == 200
    assert world_response.json() == {
        "revision": 1,
        "mill_status": "working",
    }