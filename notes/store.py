"""Own note creation and ordered storage for the active HTTP service."""


class NoteStore:
    def __init__(self) -> None:
        self._notes: list[dict] = []

    def create(self, title: str, tags: list[str]) -> dict:
        note = {"id": len(self._notes) + 1, "title": title, "tags": list(tags)}
        self._notes.append(note)
        return note.copy()

    def get(self, note_id: int) -> dict | None:
        if 1 <= note_id <= len(self._notes):
            return self._notes[note_id - 1].copy()
        return None

    def update(self, note_id: int, *, title: str | None = None, tags: list[str] | None = None) -> dict | None:
        if not 1 <= note_id <= len(self._notes):
            return None
        note = self._notes[note_id - 1]
        if title is not None:
            note["title"] = title
        if tags is not None:
            note["tags"] = list(tags)
        return note.copy()

    def list_notes(self, *, tag: str | None = None) -> list[dict]:
        if tag is None:
            return [note.copy() for note in self._notes]
        needle = tag.casefold()
        return [note.copy() for note in self._notes if any(value.casefold() == needle for value in note["tags"])]
