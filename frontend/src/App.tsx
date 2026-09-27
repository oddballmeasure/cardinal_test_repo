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

  useEffect(() => {
    let active = true;
    async function loadNotes() {
      try {
        const response = await fetch("/api/notes");
        if (!response.ok) throw new Error("Could not load notes.");
        const loaded: Note[] = await response.json();
        if (active) setNotes(loaded);
      } catch {
        if (active) setError("Could not load notes.");
      }
    }
    void loadNotes();
    return () => { active = false; };
  }, []);

  async function createNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      setError("Title is required.");
      return;
    }

    const parsedTags = tags.split(",").map((tag) => tag.trim()).filter(Boolean);
    try {
      const response = await fetch("/api/notes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: trimmedTitle, tags: parsedTags }),
      });
      if (!response.ok) throw new Error("Could not create note.");
      const created: Note = await response.json();
      setNotes((current) => [...current, created]);
      setTitle("");
      setTags("");
      setError("");
    } catch {
      setError("Could not create note.");
    }
  }

  return (
    <main>
      <h1>Notes</h1>
      <section aria-labelledby="notes-heading">
        <h2 id="notes-heading">Notes</h2>
        <form onSubmit={createNote}>
          <label htmlFor="note-title">Title</label>
          <input id="note-title" name="title" required value={title} onChange={(event) => setTitle(event.target.value)} />
          <label htmlFor="note-tags">Tags (comma-separated)</label>
          <input id="note-tags" name="tags" value={tags} onChange={(event) => setTags(event.target.value)} />
          <button type="submit">Create note</button>
        </form>
        {error && <p role="alert">{error}</p>}
        <ul aria-label="Notes list">
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
