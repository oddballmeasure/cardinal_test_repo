"""Create, list, retrieve, and update notes through the public API."""

import csv
from io import StringIO

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.storage import create_entry, get_entry, list_entries, update_entry

router = APIRouter()


@router.get("/notes", response_model=None)
def get_notes(tag: str | None = None, format: str | None = None) -> list[dict] | Response:
    notes = list_entries("notes")
    if tag is not None:
        normalized_tag = tag.casefold()
        notes = [note for note in notes if any(value.casefold() == normalized_tag for value in note["tags"])]
    if format == "csv":
        output = StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["id", "title", "tags"])
        for note in notes:
            writer.writerow([note["id"], note["title"], ";".join(note["tags"])])
        return Response(content=output.getvalue(), media_type="text/csv")
    return notes


@router.get("/notes/{id}")
def get_note(id: str) -> dict:
    try:
        note_id = int(id)
    except ValueError:
        raise HTTPException(status_code=404) from None
    note = get_entry("notes", note_id)
    if note is None:
        raise HTTPException(status_code=404)
    return note


async def note_payload(request: Request) -> object:
    try:
        return await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid JSON body") from None


def validate_title(title: object) -> None:
    if not isinstance(title, str) or not title.strip():
        raise HTTPException(status_code=400, detail="title must be a nonempty string")


def validate_tags(tags: object) -> None:
    if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag for tag in tags):
        raise HTTPException(status_code=400, detail="tags must be a list of nonempty strings")


@router.post("/notes", status_code=201)
async def post_note(request: Request) -> dict:
    payload = await note_payload(request)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="title must be a nonempty string")
    validate_title(payload.get("title"))
    validate_tags(payload.get("tags"))
    return create_entry("notes", {"title": payload["title"], "tags": payload["tags"]})


@router.patch("/notes/{id}")
async def patch_note(id: str, request: Request) -> dict:
    try:
        note_id = int(id)
    except ValueError:
        raise HTTPException(status_code=404) from None
    payload = await note_payload(request)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="invalid request")
    changes = {}
    if "title" in payload:
        validate_title(payload["title"])
        changes["title"] = payload["title"]
    if "tags" in payload:
        validate_tags(payload["tags"])
        changes["tags"] = payload["tags"]
    note = update_entry("notes", note_id, changes)
    if note is None:
        raise HTTPException(status_code=404)
    return note
