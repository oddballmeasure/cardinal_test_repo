import { useEffect, useState, type FormEvent } from "react";

type Note = {
  id: number;
  title: string;
  tags: string[];
};

type Diary = {
  id: number;
  date: string;
  title: string;
  body: string;
};

export default function App() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [diaries, setDiaries] = useState<Diary[]>([]);
  const [diaryDate, setDiaryDate] = useState("");
  const [diaryTitle, setDiaryTitle] = useState("");
  const [diaryBody, setDiaryBody] = useState("");
  const [savingDiary, setSavingDiary] = useState(false);
  const [diaryError, setDiaryError] = useState("");

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

  useEffect(() => {
    let active = true;
    fetch("/api/diaries")
      .then((response) => {
        if (!response.ok) throw new Error("Could not load diaries");
        return response.json() as Promise<Diary[]>;
      })
      .then((loaded) => {
        if (active) setDiaries(loaded);
      })
      .catch(() => {
        if (active) setDiaryError("Could not load diaries");
      });
    return () => { active = false; };
  }, []);

  async function createDiary(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (savingDiary) return;
    if (!diaryTitle.trim() || !diaryBody.trim()) {
      setDiaryError("Enter a title and body before creating a diary.");
      return;
    }
    setSavingDiary(true);
    setDiaryError("");
    try {
      const response = await fetch("/api/diaries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date: diaryDate, title: diaryTitle, body: diaryBody }),
      });
      if (!response.ok) throw new Error("Could not create diary");
      const created = await response.json() as Diary;
      setDiaries((current) => [...current, created]);
      setDiaryDate("");
      setDiaryTitle("");
      setDiaryBody("");
    } catch {
      setDiaryError("Could not create diary. Please try again.");
    } finally {
      setSavingDiary(false);
    }
  }

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
        <form onSubmit={createDiary}>
          <label htmlFor="diary-date">Date</label>
          <input id="diary-date" name="date" type="date" value={diaryDate} onChange={(event) => setDiaryDate(event.target.value)} required />
          <label htmlFor="diary-title">Title</label>
          <input id="diary-title" name="title" value={diaryTitle} onChange={(event) => setDiaryTitle(event.target.value)} required />
          <label htmlFor="diary-body">Body</label>
          <textarea id="diary-body" name="body" value={diaryBody} onChange={(event) => setDiaryBody(event.target.value)} required />
          <button type="submit" disabled={savingDiary}>Create diary</button>
        </form>
        {diaryError && <p role="alert">{diaryError}</p>}
        <ul>
          {diaries.map((diary) => (
            <li key={diary.id}>
              <time dateTime={diary.date}>{diary.date}</time>{" — "}
              <strong>{diary.title}</strong>{" — "}
              <span>{diary.body}</span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
