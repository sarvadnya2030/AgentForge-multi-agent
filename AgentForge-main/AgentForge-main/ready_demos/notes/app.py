from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
import os

app = FastAPI()

# Ensure static directory exists
os.makedirs("static", exist_ok=True)

# In-memory storage for notes
notes_db = []

class NoteCreate(BaseModel):
    title: str
    content: str
    tags: List[str] = Field(default_factory=list)

class Note(NoteCreate):
    id: str

@app.get("/")
def read_root():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "Welcome to the Notes API"}

@app.get("/notes", response_model=List[Note])
def get_notes():
    return notes_db

@app.post("/notes", response_model=Note, status_code=201)
def create_note(note_data: NoteCreate):
    new_note = Note(
        id=str(uuid.uuid4()),
        title=note_data.title,
        content=note_data.content,
        tags=note_data.tags
    )
    notes_db.append(new_note)
    return new_note

@app.get("/notes/search", response_model=List[Note])
def search_notes(q: Optional[str] = Query(None), tag: Optional[str] = Query(None)):
    results = notes_db
    if q:
        q_lower = q.lower()
        results = [
            note for note in results
            if q_lower in note.title.lower() or q_lower in note.content.lower()
        ]
    if tag:
        tag_lower = tag.lower()
        results = [
            note for note in results
            if any(t.lower() == tag_lower for t in note.tags)
        ]
    return results

@app.delete("/notes/{note_id}")
def delete_note(note_id: str):
    for i, note in enumerate(notes_db):
        if note.id == note_id:
            notes_db.pop(i)
            return {"ok": True}
    raise HTTPException(status_code=404, detail="Not found")
