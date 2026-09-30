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
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetch("/api/notes")
      .then((response) => {
        if (!response.ok) throw new Error("Could not load notes");
        return response.json() as Promise<Note[]>;
      })
      .then((loaded) => {
        if (active) setNotes(loaded);
      })
      .catch(() => {
        if (active) setError("Could not load notes");
      });
    return () => { active = false; };
  }, []);

  async function createNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      setError("Enter a title before creating a note.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const response = await fetch("/api/notes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: trimmedTitle,
          tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean),
        }),
      });
      if (!response.ok) throw new Error("Could not create note");
      const created = await response.json() as Note;
      setNotes((current) => [...current, created]);
      setTitle("");
      setTags("");
    } catch {
      setError("Could not create note. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main>
      <h1>Notes</h1>
      <form onSubmit={createNote}>
        <label htmlFor="note-title">Title</label>
        <input id="note-title" name="title" value={title} onChange={(event) => setTitle(event.target.value)} required />
        <label htmlFor="note-tags">Tags (comma-separated)</label>
        <input id="note-tags" name="tags" value={tags} onChange={(event) => setTags(event.target.value)} />
        <button type="submit" disabled={saving}>Create note</button>
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
