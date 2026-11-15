from app import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_create_habit():
    response = client.post("/habits", json={"name": "Exercise"})
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["name"] == "Exercise"
    assert data["streak"] == 0


def test_get_habits():
    client.post("/habits", json={"name": "Read"})
    response = client.get("/habits")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "completed_today" in data[0]


def test_check_in_habit():
    create_res = client.post("/habits", json={"name": "Meditate"})
    habit_id = create_res.json()["id"]

    response = client.post(f"/habits/{habit_id}/check-in")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == habit_id
    assert data["streak"] == 1
    assert data["completed_today"] is True


def test_delete_habit():
    create_res = client.post("/habits", json={"name": "Sleep Early"})
    habit_id = create_res.json()["id"]

    response = client.delete(f"/habits/{habit_id}")
    assert response.status_code == 204
    assert response.content == b""
