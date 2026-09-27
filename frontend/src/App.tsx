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
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    fetch("/api/notes")
      .then((response) => {
        if (!response.ok) throw new Error("Unable to load notes.");
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
        if (active) setError("Unable to load notes.");
      });
    return () => { active = false; };
  }, []);

  async function createNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanTitle = title.trim();
    const cleanTags = tags.split(",").map((tag) => tag.trim()).filter(Boolean);
    if (!cleanTitle || cleanTags.length === 0 || saving) return;

    setSaving(true);
    setError("");
    try {
      const response = await fetch("/api/notes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: cleanTitle, tags: cleanTags }),
      });
      if (!response.ok) throw new Error("Unable to create note.");
      const created = await response.json() as Note;
      setNotes((current) => current.some((note) => note.id === created.id) ? current : [...current, created]);
      setTitle("");
      setTags("");
    } catch {
      setError("Unable to create note.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main>
      <h1>Notes</h1>
      <section aria-labelledby="notes-heading">
        <h2 id="notes-heading">Notes</h2>
        <form onSubmit={createNote}>
          <label htmlFor="note-title">Title</label>
          <input id="note-title" value={title} onChange={(event) => setTitle(event.target.value)} required />
          <label htmlFor="note-tags">Tags (comma-separated)</label>
          <input id="note-tags" value={tags} onChange={(event) => setTags(event.target.value)} required />
          <button type="submit" disabled={saving}>Create note</button>
        </form>
        {error && <p role="alert">{error}</p>}
        <ul aria-label="Notes list">
          {notes.map((note) => (
            <li key={note.id}>
              <strong>{note.title}</strong>
              <span> — {note.tags.join(", ")}</span>
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
