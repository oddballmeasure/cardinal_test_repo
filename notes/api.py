"""Route notes and health requests to storage and response formatting."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit

from notes.formatters import render_json
from notes.store import NoteStore


class NotesHandler(BaseHTTPRequestHandler):
    store: NoteStore

    def send_json(self, status: int, value: object) -> None:
        body = render_json(value)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/health":
            self.send_json(200, {"status": "ok"})
        elif path == "/notes":
            self.send_json(200, self.store.list_notes())
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/notes":
            self.send_json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            self.send_json(400, {"error": "invalid JSON body"})
            return
        if not isinstance(payload, dict) or not isinstance(payload.get("title"), str) or not payload["title"].strip():
            self.send_json(400, {"error": "title must be a nonempty string"})
            return
        tags = payload.get("tags")
        if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag for tag in tags):
            self.send_json(400, {"error": "tags must be a list of nonempty strings"})
            return
        self.send_json(201, self.store.create(payload["title"], tags))

    def log_message(self, format: str, *args: object) -> None:
        pass


def run_server(host: str, port: int) -> None:
    store = NoteStore()

    class Handler(NotesHandler):
        pass

    Handler.store = store
    with HTTPServer((host, port), Handler) as server:
        print(f"Serving notes at http://{host}:{server.server_port}", flush=True)
        server.serve_forever()
