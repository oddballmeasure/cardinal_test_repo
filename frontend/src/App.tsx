import { FormEvent, useEffect, useState } from "react";

type Note = { id: number; title: string; tags: string[] };

export function parseTags(raw: string): string[] {
  return raw
    .split(",")
    .map((tag) => tag.trim())
    .filter((tag) => tag.length > 0);
}

// Page shell for the notes and diaries interface.
export default function App() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/notes")
      .then((response) => (response.ok ? response.json() : []))
      .then((existing: Note[]) => {
        // Keep notes created before the initial load finished.
        setNotes((current) => [
          ...existing,
          ...current.filter((note) => !existing.some((item) => item.id === note.id)),
        ]);
      })
      .catch(() => undefined);
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (title.trim() === "") {
      setError("Title is required");
      return;
    }
    setError("");
    try {
      const response = await fetch("/api/notes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, tags: parseTags(tags) }),
      });
      if (!response.ok) {
        setError("Could not create note");
        return;
      }
      const created: Note = await response.json();
      setNotes((current) => [...current, created]);
      setTitle("");
      setTags("");
    } catch {
      setError("Could not create note");
    }
  }

  return (
    <main>
      <h1>Notes</h1>
      <section aria-labelledby="notes-heading">
        <h2 id="notes-heading">Notes</h2>
        <form onSubmit={submit} noValidate aria-label="New note">
          <label>
            Title
            <input
              name="title"
              required
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
          </label>
          <label>
            Tags
            <input
              name="tags"
              value={tags}
              placeholder="comma, separated"
              onChange={(event) => setTags(event.target.value)}
            />
          </label>
          <button type="submit">Add note</button>
          {error && <p role="alert" className="error">{error}</p>}
        </form>
        <ul aria-label="Notes list">
          {notes.map((note) => (
            <li key={note.id} data-testid="note">
              <span className="note-title">{note.title}</span>{" "}
              <span className="note-tags">{note.tags.join(", ")}</span>
            </li>
          ))}
        </ul>
      </section>
      <section aria-labelledby="diaries-heading">
        <h2 id="diaries-heading">Diaries</h2>
      </section>
    </main>
  );
}
