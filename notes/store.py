"""Own note creation and ordered storage for the active HTTP service."""


class NoteStore:
    def __init__(self) -> None:
        self._notes: list[dict] = []

    def create(self, title: str, tags: list[str]) -> dict:
        note = {"id": len(self._notes) + 1, "title": title, "tags": list(tags)}
        self._notes.append(note)
        return note.copy()

    def list_notes(self) -> list[dict]:
        return [note.copy() for note in self._notes]
