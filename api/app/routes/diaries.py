"""Create and list dated diary entries through the public API."""

from datetime import date
import re

from fastapi import APIRouter, HTTPException, Request

from app.storage import create_entry, list_entries

router = APIRouter()


@router.get("/diaries")
def get_diaries() -> list[dict]:
    return list_entries("diaries")


@router.post("/diaries", status_code=201)
async def post_diary(request: Request) -> dict:
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid JSON body") from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="invalid JSON body")
    for field in ("date", "title", "body"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            raise HTTPException(status_code=400, detail=f"{field} must be a nonempty string")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", payload["date"]):
        raise HTTPException(status_code=400, detail="date must be a valid YYYY-MM-DD calendar date")
    try:
        date.fromisoformat(payload["date"])
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be a valid YYYY-MM-DD calendar date") from None
    return create_entry("diaries", {field: payload[field] for field in ("date", "title", "body")})
