# Notes test service

This is a small, dependency-free Python 3.13 HTTP service for Cardinal's live
repository test scenario. Notes are kept in memory and reset when the process
restarts.

```sh
python -m notes --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/notes \
  -H 'Content-Type: application/json' \
  -d '{"title":"Plan","tags":["work"]}'
curl http://127.0.0.1:8000/notes
```

`POST /notes` accepts a nonempty `title` and a list of nonempty string `tags`.
It returns the new note with a numeric ID. `GET /notes` returns notes in creation
order as JSON. Use `GET /notes?tag=work` to return only notes with a tag
exactly matching `work` (case-insensitive), still in creation order as JSON;
for example, `WORK` matches but `workshop` does not. An unmatched tag returns
an empty JSON list. For CSV instead of JSON, use `GET /notes?format=csv`:
its UTF-8 `text/csv` response has columns `id,title,tags` and one row per note,
with tags joined by semicolons. CSV quotes fields containing commas, quotes, or
line breaks. Combine filtering and export with `GET /notes?tag=WORK&format=csv`;
an empty or unmatched result still contains the header. `GET /health` returns
`{"status":"ok"}`.

Run the repository's HTTP end-to-end checks with:

```sh
python -m unittest discover -s tests -v
```

The `deploy/` pair is a fake-host validation fixture. Its script records the
configured host, and its health command succeeds only after that record and the
fake host's readiness marker are present. It does not install or start the
service on a production host.
