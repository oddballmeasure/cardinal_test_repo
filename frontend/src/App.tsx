import { FormEvent, useEffect, useState } from "react";

type Note = { id: number; title: string; tags: string[] };

type Diary = { id: number; date: string; title: string; body: string };

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

  const [diaries, setDiaries] = useState<Diary[]>([]);
  const [diaryDate, setDiaryDate] = useState("");
  const [diaryTitle, setDiaryTitle] = useState("");
  const [diaryBody, setDiaryBody] = useState("");
  const [diaryError, setDiaryError] = useState("");

  useEffect(() => {
    fetch("/api/diaries")
      .then((response) => (response.ok ? response.json() : []))
      .then((existing: Diary[]) => {
        // Keep entries created before the initial load finished.
        setDiaries((current) => [
          ...existing,
          ...current.filter((diary) => !existing.some((item) => item.id === diary.id)),
        ]);
      })
      .catch(() => undefined);
  }, []);

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

  async function submitDiary(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (diaryDate.trim() === "") {
      setDiaryError("Date is required");
      return;
    }
    if (diaryTitle.trim() === "") {
      setDiaryError("Title is required");
      return;
    }
    if (diaryBody.trim() === "") {
      setDiaryError("Body is required");
      return;
    }
    setDiaryError("");
    try {
      const response = await fetch("/api/diaries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date: diaryDate, title: diaryTitle, body: diaryBody }),
      });
      if (!response.ok) {
        setDiaryError("Could not create diary entry");
        return;
      }
      const created: Diary = await response.json();
      setDiaries((current) => [...current, created]);
      setDiaryDate("");
      setDiaryTitle("");
      setDiaryBody("");
    } catch {
      setDiaryError("Could not create diary entry");
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
        <form onSubmit={submitDiary} noValidate aria-label="New diary entry">
          <label>
            Date
            <input
              type="date"
              name="date"
              required
              value={diaryDate}
              onChange={(event) => setDiaryDate(event.target.value)}
            />
          </label>
          <label>
            Title
            <input
              name="title"
              required
              value={diaryTitle}
              onChange={(event) => setDiaryTitle(event.target.value)}
            />
          </label>
          <label>
            Body
            <textarea
              name="body"
              required
              value={diaryBody}
              onChange={(event) => setDiaryBody(event.target.value)}
            />
          </label>
          <button type="submit">Create diary</button>
          {diaryError && <p role="alert" className="error">{diaryError}</p>}
        </form>
        <ul aria-label="Diary list">
          {diaries.map((diary) => (
            <li key={diary.id} data-testid="diary">
              <span className="diary-date">{diary.date}</span>{" "}
              <span className="diary-title">{diary.title}</span>{" "}
              <span className="diary-body">{diary.body}</span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
