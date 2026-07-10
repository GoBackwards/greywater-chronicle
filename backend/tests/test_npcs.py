from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_npc_dialogue_happy_path():
    r = client.get("/npcs/guard/dialogue")
    assert r.status_code == 200
    body = r.json()
    assert body["npc_id"] == "guard"
    assert body["name"] == "Guard"
    assert "Welcome" in body["dialogue"]


def test_get_npc_dialogue_case_insensitive():
    r = client.get("/npcs/GUARD/dialogue")
    assert r.status_code == 200
    assert r.json()["npc_id"] == "guard"


def test_get_npc_dialogue_not_found():
    r = client.get("/npcs/nobody/dialogue")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()