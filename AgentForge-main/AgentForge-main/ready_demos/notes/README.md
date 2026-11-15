# Note Taking API

A simple API for managing notes.

## File Structure
- `app.py`: Main application logic.
- `static/index.html`: Frontend serving page.
- `tests/test_app.py`: Unit and integration tests.
- `README.md`: This documentation.

## API Endpoints

1. **`GET /`**: Serves `static/index.html` (200 OK)
2. **`GET /notes`**: Returns all notes.
   * Res: `[{"id": "str", "title": "str", "content": "str", "tags": ["str"]}]` (200 OK)
3. **`POST /notes`**: Creates a new note.
   * Req: `{"title": "str", "content": "str", "tags": ["str"]}`
   * Res: Created Note object (201 Created)
4. **`GET /notes/search?q=str&tag=str`**: Searches notes by query (`q`) or tag (`tag`).
   * Res: List of Note objects (200 OK)
5. **`DELETE /notes/{id}`**: Deletes a note by ID.
   * Res: `{"ok": true}` (200 OK) or `{"detail": "Not found"}` (404 Not Found)

## Running Instructions

1. **Install dependencies**: (Assume necessary requirements are listed, e.g., `pip install -r requirements.txt`)
2. **Run the server**:
