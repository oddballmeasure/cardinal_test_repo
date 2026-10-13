"""Create and list notes through the public API."""

from fastapi import APIRouter, HTTPException, Request

from app.storage import create_entry, list_entries

router = APIRouter()


@router.get("/notes")
def get_notes() -> list[dict]:
    return list_entries("notes")


@router.get("/notes/{note_id}")
def get_note(note_id: str) -> dict:
    if note_id.isascii() and note_id.isdigit():
        wanted = int(note_id)
        for note in list_entries("notes"):
            if note.get("id") == wanted:
                return note
    raise HTTPException(status_code=404, detail="not found")


@router.post("/notes", status_code=201)
async def post_note(request: Request) -> dict:
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid JSON body") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("title"), str) or not payload["title"].strip():
        raise HTTPException(status_code=400, detail="title must be a nonempty string")
    tags = payload.get("tags")
    if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag for tag in tags):
        raise HTTPException(status_code=400, detail="tags must be a list of nonempty strings")
    return create_entry("notes", {"title": payload["title"], "tags": tags})
