import { useEffect, useState, type FormEvent } from "react";

type Note = { id: number; title: string; tags: string[] };

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
        if (!response.ok) throw new Error("Could not load notes.");
        return response.json() as Promise<Note[]>;
      })
      .then((loaded) => {
        if (active) {
          // A create may have finished while the initial list request was in flight.
          setNotes((current) => [
            ...loaded,
            ...current.filter((note) => !loaded.some((existing) => existing.id === note.id)),
          ]);
        }
      })
      .catch(() => {
        if (active) setError("Could not load notes.");
      });
    return () => { active = false; };
  }, []);

  async function createNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedTitle = title.trim();
    const parsedTags = tags.split(",").map((tag) => tag.trim()).filter(Boolean);
    if (!trimmedTitle) {
      setError("Title is required.");
      return;
    }
    if (!parsedTags.length) {
      setError("Enter at least one tag.");
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      const response = await fetch("/api/notes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: trimmedTitle, tags: parsedTags }),
      });
      if (!response.ok) throw new Error("Could not create note.");
      const note = (await response.json()) as Note;
      setNotes((current) => [...current, note]);
      setTitle("");
      setTags("");
    } catch {
      setError("Could not create note.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main>
      <h1>Notes</h1>
      <section aria-labelledby="notes-heading">
        <h2 id="notes-heading">Notes</h2>
        <form onSubmit={createNote}>
          <div>
            <label htmlFor="note-title">Title</label>
            <input id="note-title" name="title" required value={title} onChange={(event) => setTitle(event.target.value)} />
          </div>
          <div>
            <label htmlFor="note-tags">Tags (comma-separated)</label>
            <input id="note-tags" name="tags" required value={tags} onChange={(event) => setTags(event.target.value)} />
          </div>
          <button type="submit" disabled={submitting}>Create note</button>
        </form>
        {error && <p role="alert">{error}</p>}
        <ul aria-label="Notes list">
          {notes.map((note) => (
            <li key={note.id}>
              <strong>{note.title}</strong>
              <ul aria-label={`Tags for ${note.title}`}>
                {note.tags.map((tag, index) => <li key={index}>{tag}</li>)}
              </ul>
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
