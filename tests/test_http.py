"""Exercise the notes service through its public HTTP boundary."""

import json
import socket
import subprocess
import sys
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class NotesHTTPTests(unittest.TestCase):
    def setUp(self) -> None:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        self.base = f"http://127.0.0.1:{port}"
        self.process = subprocess.Popen(
            [sys.executable, "-m", "notes", "--host", "127.0.0.1", "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(40):
            if self.process.poll() is not None:
                self.fail(f"notes service exited: {self.process.stderr.read()}")
            try:
                self.request("/health")
                break
            except URLError:
                time.sleep(0.05)
        else:
            self.fail("notes service did not become ready")

    def tearDown(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=2)
        self.process.stderr.close()

    def request(self, path: str, payload: dict | None = None) -> tuple[int, str, object]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            self.base + path,
            data=body,
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        try:
            response = urlopen(request, timeout=2)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.headers["Content-Type"], json.loads(response.read())

    def test_health_reports_ready(self) -> None:
        status, content_type, body = self.request("/health")
        self.assertEqual(status, 200)
        self.assertTrue(content_type.startswith("application/json"))
        self.assertEqual(body, {"status": "ok"})

    def test_create_and_list_notes_in_order(self) -> None:
        first = self.request("/notes", {"title": "Café", "tags": ["personal"]})
        second = self.request("/notes", {"title": "Plan", "tags": ["work", "urgent"]})
        self.assertEqual([first[0], second[0]], [201, 201])
        self.assertEqual(first[2], {"id": 1, "title": "Café", "tags": ["personal"]})
        self.assertEqual(second[2], {"id": 2, "title": "Plan", "tags": ["work", "urgent"]})
        status, content_type, body = self.request("/notes")
        self.assertEqual(status, 200)
        self.assertTrue(content_type.startswith("application/json"))
        self.assertEqual(body, [first[2], second[2]])

    def test_get_note_by_id_preserves_ordered_list(self) -> None:
        first = self.request("/notes", {"title": "Café", "tags": ["personal"]})
        second = self.request("/notes", {"title": "Plan", "tags": ["work", "urgent"]})
        self.assertEqual((first[0], second[0]), (201, 201))

        for created in (second, first):
            status, content_type, body = self.request(f"/notes/{created[2]['id']}")
            self.assertEqual(status, 200)
            self.assertTrue(content_type.startswith("application/json"))
            self.assertEqual(body, created[2])

        status, content_type, body = self.request("/notes")
        self.assertEqual(status, 200)
        self.assertTrue(content_type.startswith("application/json"))
        self.assertEqual(body, [first[2], second[2]])

    def test_get_missing_and_nonnumeric_note_returns_json_not_found(self) -> None:
        self.request("/notes", {"title": "Existing", "tags": []})
        for path in ("/notes/999", "/notes/not-a-number"):
            with self.subTest(path=path):
                status, content_type, body = self.request(path)
                self.assertEqual(status, 404)
                self.assertTrue(content_type.startswith("application/json"))
                self.assertEqual(body, {"error": "not found"})

    def test_invalid_note_does_not_change_list(self) -> None:
        status, _, body = self.request("/notes", {"title": "", "tags": ["work"]})
        self.assertEqual(status, 400)
        self.assertIn("title", body["error"])
        status, _, body = self.request("/notes")
        self.assertEqual(status, 200)
        self.assertEqual(body, [])

    def test_unknown_route_returns_not_found(self) -> None:
        status, _, body = self.request("/missing")
        self.assertEqual(status, 404)
        self.assertEqual(body, {"error": "not found"})


if __name__ == "__main__":
    unittest.main()
