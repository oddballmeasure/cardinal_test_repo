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
order as JSON, and `GET /health` returns `{"status":"ok"}`.

Run the repository's HTTP end-to-end checks with:

```sh
python -m unittest discover -s tests -v
```

The `deploy/` pair is a fake-host validation fixture. Its script records the
configured host, and its health command succeeds only after that record and the
fake host's readiness marker are present. It does not install or start the
service on a production host.
