from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200

def test_create_and_get_notes():
    note_data = {
        "title": "Test Note",
        "content": "This is a test note content.",
        "tags": ["test", "fastapi"]
    }
    response = client.post("/notes", json=note_data)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == note_data["title"]
    assert data["content"] == note_data["content"]
    assert data["tags"] == note_data["tags"]
    assert "id" in data
    
    note_id = data["id"]

    response = client.get("/notes")
    assert response.status_code == 200
    notes = response.json()
    assert any(note["id"] == note_id for note in notes)

def test_search_notes():
    note_data = {
        "title": "Unique Search Title",
        "content": "Searching for specific terms.",
        "tags": ["unique"]
    }
    client.post("/notes", json=note_data)

    response = client.get("/notes/search?q=Unique&tag=unique")
    assert response.status_code == 200
    results = response.json()
    assert len(results) >= 1
    assert any(note["title"] == "Unique Search Title" for note in results)

def test_delete_note():
    note_data = {
        "title": "Delete Me",
        "content": "Temporary note.",
        "tags": ["temp"]
    }
    create_response = client.post("/notes", json=note_data)
    note_id = create_response.json()["id"]

    delete_response = client.delete(f"/notes/{note_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"ok": True}

    not_found_response = client.delete(f"/notes/{note_id}")
    assert not_found_response.status_code == 404
    assert not_found_response.json() == {"detail": "Not found"}
