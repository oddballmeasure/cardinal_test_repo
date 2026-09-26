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

    def request(self, path: str, payload: object = None, *, method: str | None = None) -> tuple[int, str, object]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            self.base + path,
            data=body,
            headers={"Content-Type": "application/json"} if body is not None else {},
            method=method or ("POST" if body is not None else "GET"),
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

    def test_retrieve_note_preserves_ordered_list(self) -> None:
        first = self.request("/notes", {"title": "Café", "tags": ["personal"]})
        second = self.request("/notes", {"title": "Plan", "tags": ["work", "urgent"]})
        self.assertEqual([first[0], second[0]], [201, 201])
        status, content_type, body = self.request(f"/notes/{second[2]['id']}")
        self.assertEqual(status, 200)
        self.assertTrue(content_type.startswith("application/json"))
        self.assertEqual(body, second[2])
        status, _, body = self.request(f"/notes/{first[2]['id']}")
        self.assertEqual(status, 200)
        self.assertEqual(body, first[2])
        status, content_type, body = self.request("/notes")
        self.assertEqual(status, 200)
        self.assertTrue(content_type.startswith("application/json"))
        self.assertEqual(body, [first[2], second[2]])

    def test_unknown_and_nonnumeric_note_ids_return_json_404(self) -> None:
        self.request("/notes", {"title": "Existing", "tags": []})
        for path in ("/notes/999", "/notes/not-an-id"):
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

    def test_patch_title_only_preserves_tags_id_and_order(self) -> None:
        first = self.request("/notes", {"title": "Original", "tags": ["personal"]})[2]
        second = self.request("/notes", {"title": "Other", "tags": ["work"]})[2]
        status, content_type, body = self.request("/notes/1", {"title": "Café revisited"}, method="PATCH")
        self.assertEqual(status, 200)
        self.assertTrue(content_type.startswith("application/json"))
        updated = {"id": 1, "title": "Café revisited", "tags": first["tags"]}
        self.assertEqual(body, updated)
        self.assertEqual(self.request("/notes/1")[2], updated)
        self.assertEqual(self.request("/notes")[2], [updated, second])

    def test_patch_tags_only_preserves_title_id_and_order(self) -> None:
        first = self.request("/notes", {"title": "First", "tags": ["old"]})[2]
        second = self.request("/notes", {"title": "Second", "tags": ["work"]})[2]
        status, content_type, body = self.request("/notes/2", {"tags": ["日本語", "café"]}, method="PATCH")
        self.assertEqual(status, 200)
        self.assertTrue(content_type.startswith("application/json"))
        updated = {"id": 2, "title": second["title"], "tags": ["日本語", "café"]}
        self.assertEqual(body, updated)
        self.assertEqual(self.request("/notes/2")[2], updated)
        self.assertEqual(self.request("/notes")[2], [first, updated])

    def test_invalid_patch_does_not_mutate_note(self) -> None:
        original = self.request("/notes", {"title": "Keep", "tags": ["original"]})[2]
        invalid = [
            {"title": ""}, {"title": "  \t "}, {"title": None},
            {"tags": "not a list"}, {"tags": None}, {"tags": ["ok", ""]},
            {"tags": ["ok", 12]},
            {"title": "Valid", "tags": [""]},
            {"title": " ", "tags": ["valid"]},
            {}, [],
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                status, content_type, body = self.request("/notes/1", payload, method="PATCH")
                self.assertEqual(status, 400)
                self.assertTrue(content_type.startswith("application/json"))
                self.assertIn("error", body)
                self.assertEqual(self.request("/notes/1")[2], original)
                self.assertEqual(self.request("/notes")[2], [original])

    def test_patch_missing_id_returns_json_404_without_mutation(self) -> None:
        original = self.request("/notes", {"title": "Keep", "tags": []})[2]
        for path in ("/notes/999", "/notes/not-an-id", "/notes/2"):
            with self.subTest(path=path):
                status, content_type, body = self.request(path, {"title": "New"}, method="PATCH")
                self.assertEqual(status, 404)
                self.assertTrue(content_type.startswith("application/json"))
                self.assertEqual(body, {"error": "not found"})
                self.assertEqual(self.request("/notes")[2], [original])

    def test_unknown_route_returns_not_found(self) -> None:
        status, _, body = self.request("/missing")
        self.assertEqual(status, 404)
        self.assertEqual(body, {"error": "not found"})


if __name__ == "__main__":
    unittest.main()
