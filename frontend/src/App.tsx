import { useEffect, useState, type FormEvent } from "react";

type Note = { id: number; title: string; tags: string[] };
type Diary = { id: number; date: string; title: string; body: string };

export default function App() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [diaries, setDiaries] = useState<Diary[]>([]);
  const [diaryDate, setDiaryDate] = useState("");
  const [diaryTitle, setDiaryTitle] = useState("");
  const [diaryBody, setDiaryBody] = useState("");
  const [diaryError, setDiaryError] = useState("");
  const [submittingDiary, setSubmittingDiary] = useState(false);

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

  useEffect(() => {
    let active = true;
    fetch("/api/diaries")
      .then((response) => {
        if (!response.ok) throw new Error("Could not load diaries.");
        return response.json() as Promise<Diary[]>;
      })
      .then((loaded) => {
        if (active) {
          // Keep entries created while the initial list request was in flight.
          setDiaries((current) => [
            ...loaded,
            ...current.filter((diary) => !loaded.some((existing) => existing.id === diary.id)),
          ]);
        }
      })
      .catch(() => {
        if (active) setDiaryError("Could not load diaries.");
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

  async function createDiary(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedTitle = diaryTitle.trim();
    const trimmedBody = diaryBody.trim();
    if (!diaryDate || !trimmedTitle || !trimmedBody) {
      setDiaryError("Date, title, and body are required.");
      return;
    }
    setDiaryError("");
    setSubmittingDiary(true);
    try {
      const response = await fetch("/api/diaries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date: diaryDate, title: trimmedTitle, body: trimmedBody }),
      });
      if (!response.ok) throw new Error("Could not create diary.");
      const diary = (await response.json()) as Diary;
      setDiaries((current) => [...current, diary]);
      setDiaryDate("");
      setDiaryTitle("");
      setDiaryBody("");
    } catch {
      setDiaryError("Could not create diary.");
    } finally {
      setSubmittingDiary(false);
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
        <form onSubmit={createDiary}>
          <div>
            <label htmlFor="diary-date">Date</label>
            <input id="diary-date" name="date" type="date" required value={diaryDate} onChange={(event) => setDiaryDate(event.target.value)} />
          </div>
          <div>
            <label htmlFor="diary-title">Title</label>
            <input id="diary-title" name="title" required value={diaryTitle} onChange={(event) => setDiaryTitle(event.target.value)} />
          </div>
          <div>
            <label htmlFor="diary-body">Body</label>
            <textarea id="diary-body" name="body" required value={diaryBody} onChange={(event) => setDiaryBody(event.target.value)} />
          </div>
          <button type="submit" disabled={submittingDiary}>Create diary</button>
        </form>
        {diaryError && <p role="alert">{diaryError}</p>}
        <ul aria-label="Diaries list">
          {diaries.map((diary) => (
            <li key={diary.id}>
              <time dateTime={diary.date}>{diary.date}</time>
              <strong>{diary.title}</strong>
              <p>{diary.body}</p>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
