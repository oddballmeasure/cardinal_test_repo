"""Summary statistics over stored notes."""

from fastapi import APIRouter

from app.storage import list_entries

router = APIRouter()


@router.get("/stats/tags")
def tag_stats() -> dict:
    notes = list_entries("notes")
    total = sum(len(note["tags"]) for note in notes)
    return {
        "notes": len(notes),
        "tags": total,
        "average_tags_per_note": round(total / len(notes), 2) if notes else 0,
    }
