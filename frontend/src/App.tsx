import { useEffect, useState, type FormEvent } from "react";

type Note = {
  id: number;
  title: string;
  tags: string[];
};

export default function App() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let active = true;
    fetch("/api/notes")
      .then((response) => {
        if (!response.ok) throw new Error("Could not load notes");
        return response.json() as Promise<Note[]>;
      })
      .then((loaded) => {
        if (active) {
          setNotes((current) => [
            ...loaded,
            ...current.filter((note) => !loaded.some((item) => item.id === note.id)),
          ]);
        }
      })
      .catch(() => {
        if (active) setError("Could not load notes");
      });
    return () => { active = false; };
  }, []);

  async function createNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim()) {
      setError("Title is required");
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      const response = await fetch("/api/notes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          tags: tags.split(",").map((tag) => tag.trim()).filter((tag) => tag.length > 0),
        }),
      });
      if (!response.ok) throw new Error("Could not create note");
      const created = (await response.json()) as Note;
      setNotes((current) => [...current.filter((note) => note.id !== created.id), created]);
      setTitle("");
      setTags("");
    } catch {
      setError("Could not create note");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main>
      <h1>Notes</h1>
      <form onSubmit={createNote}>
        <label htmlFor="note-title">Title</label>
        <input id="note-title" required value={title} onChange={(event) => setTitle(event.target.value)} />
        <label htmlFor="note-tags">Tags (comma-separated)</label>
        <input id="note-tags" value={tags} onChange={(event) => setTags(event.target.value)} />
        <button type="submit" disabled={submitting}>Create note</button>
      </form>
      {error && <p role="alert">{error}</p>}
      <section aria-labelledby="notes-heading">
        <h2 id="notes-heading">Notes</h2>
        <ul>
          {notes.map((note) => (
            <li key={note.id}>
              <strong>{note.title}</strong>
              {note.tags.length > 0 && <span> — {note.tags.join(", ")}</span>}
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
