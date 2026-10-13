"""Create and list dated diary entries through the public API."""

import re
from datetime import date

from fastapi import APIRouter, HTTPException, Request

from app.storage import create_entry, list_entries

router = APIRouter()

_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _valid_date(value: object) -> bool:
    if not isinstance(value, str) or not _DATE_RE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


@router.get("/diaries")
def get_diaries() -> list[dict]:
    return list_entries("diary")


@router.post("/diaries", status_code=201)
async def post_diary(request: Request) -> dict:
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid JSON body") from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")
    if not _valid_date(payload.get("date")):
        raise HTTPException(status_code=400, detail="date must be a valid YYYY-MM-DD date")
    for field in ("title", "body"):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise HTTPException(status_code=400, detail=f"{field} must be a nonempty string")
    return create_entry(
        "diary",
        {"date": payload["date"], "title": payload["title"], "body": payload["body"]},
    )
