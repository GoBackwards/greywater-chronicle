from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    test_app = create_app(
        database_path=tmp_path / "chronicle.db"
    )

    with TestClient(test_app) as test_client:
        yield test_client


def test_get_npc_dialogue_happy_path(
    client: TestClient,
):
    r = client.get("/npcs/guard/dialogue")
    assert r.status_code == 200
    body = r.json()
    assert body["npc_id"] == "guard"
    assert body["name"] == "Guard"
    assert "Welcome" in body["dialogue"]


def test_get_npc_dialogue_case_insensitive(
    client: TestClient,
):
    r = client.get("/npcs/GUARD/dialogue")
    assert r.status_code == 200
    assert r.json()["npc_id"] == "guard"


def test_get_npc_dialogue_not_found(
    client: TestClient,
):
    r = client.get("/npcs/nobody/dialogue")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


def test_miller_dialogue_changes_after_repair(
    client: TestClient,
):
    session_response = client.post("/sessions")

    assert session_response.status_code == 201
    session = session_response.json()

    repair_response = client.post(
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

    assert repair_response.status_code == 200

    dialogue_response = client.get(
        "/npcs/miller/dialogue"
    )

    assert dialogue_response.status_code == 200
    assert dialogue_response.json() == {
        "npc_id": "miller",
        "name": "Miller",
        "dialogue": (
            "The mill wheel is turning again. "
            "Greywater has flour once more."
        ),
    }