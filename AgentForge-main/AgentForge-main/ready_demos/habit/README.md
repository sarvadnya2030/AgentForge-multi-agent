# Habit Tracker API

A simple API for tracking daily habits.

## Installation and Running

1. **Prerequisites:** Python 3.x
2. **Setup:** (Assuming a virtual environment is used)
3. **Run:** `python app.py`

The API will start running locally, typically on `http://127.0.0.1:5000`.

## API Endpoints

- `POST /habits`: Creates a new habit.
  - **Request:** `{"name": "string"}`
  - **Response (201):** `{"id": "string", "name": "string", "streak": 0}`
- `GET /habits`: Retrieves all habits.
  - **Response (200):** `[{"id": "string", "name": "string", "streak": 0, "completed_today": false}]`
- `POST /habits/{id}/check-in`: Marks a habit as completed for today.
  - **Response (200):** `{"id": "string", "name": "string", "streak": 1, "completed_today": true}`
- `DELETE /habits/{id}`: Deletes a habit by ID.
  - **Response (204):** No Content
