"""Own note creation and ordered storage for the active HTTP service."""


class NoteStore:
    def __init__(self) -> None:
        self._notes: list[dict] = []

    def create(self, title: str, tags: list[str]) -> dict:
        note = {"id": len(self._notes) + 1, "title": title, "tags": list(tags)}
        self._notes.append(note)
        return note.copy()

    def get(self, note_id: int) -> dict | None:
        """Look up a note without changing its position in the ordered collection."""
        if not 1 <= note_id <= len(self._notes):
            return None
        note = self._notes[note_id - 1]
        return {"id": note["id"], "title": note["title"], "tags": list(note["tags"])}

    def list_notes(self) -> list[dict]:
        return [note.copy() for note in self._notes]
