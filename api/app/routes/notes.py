"""Create, retrieve, update, and list notes through the public API."""

from fastapi import APIRouter, HTTPException, Request

from app.storage import create_entry, get_entry, list_entries, update_entry

router = APIRouter()


@router.get("/notes")
def get_notes() -> list[dict]:
    return list_entries("notes")


@router.get("/notes/{note_id}")
def get_note(note_id: str) -> dict:
    try:
        entry_id = int(note_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="not found") from None
    note = get_entry("notes", entry_id)
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


@router.patch("/notes/{note_id}")
async def patch_note(note_id: str, request: Request) -> dict:
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid JSON body") from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="invalid JSON body")
    if "title" in payload and (not isinstance(payload["title"], str) or not payload["title"].strip()):
        raise HTTPException(status_code=400, detail="title must be a nonempty string")
    if "tags" in payload:
        tags = payload["tags"]
        if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag for tag in tags):
            raise HTTPException(status_code=400, detail="tags must be a list of nonempty strings")
    try:
        entry_id = int(note_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="not found") from None
    note = update_entry("notes", entry_id, {key: payload[key] for key in ("title", "tags") if key in payload})
    if note is None:
        raise HTTPException(status_code=404, detail="not found")
    return note
