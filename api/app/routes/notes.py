"""Create, list and retrieve notes through the public API."""

from fastapi import APIRouter, HTTPException, Request

from app.storage import create_entry, get_entry, list_entries

router = APIRouter()


@router.get("/notes")
def get_notes() -> list[dict]:
    return list_entries("notes")


@router.get("/notes/{id}")
def get_note(id: str) -> dict:
    try:
        note_id = int(id)
    except ValueError:
        raise HTTPException(status_code=404, detail="not found") from None
    note = get_entry("notes", note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="not found")
    return note


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
