"""Exercise the notes service through its public HTTP boundary."""

import csv
import io
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

    def request(self, path: str, payload: dict | None = None, *, method: str | None = None) -> tuple[int, str, object]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            self.base + path,
            data=body,
            headers={"Content-Type": "application/json"} if body is not None else {},
            method=method,
        )
        try:
            response = urlopen(request, timeout=2)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.headers["Content-Type"], json.loads(response.read())

    def request_csv(self, path: str) -> tuple[int, str, bytes, list[list[str]]]:
        with urlopen(self.base + path, timeout=2) as response:
            status = response.status
            content_type = response.headers["Content-Type"]
            body = response.read()
        rows = list(csv.reader(io.StringIO(body.decode("utf-8"), newline="")))
        return status, content_type, body, rows

    def test_csv_export_empty_and_unmatched(self) -> None:
        status, content_type, body, rows = self.request_csv("/notes?format=csv")
        self.assertEqual(status, 200)
        self.assertTrue(content_type.startswith("text/csv"))
        self.assertEqual(rows, [["id", "title", "tags"]])
        self.assertEqual(body.decode("utf-8").strip(), "id,title,tags")

        self.request("/notes", {"title": "Existing", "tags": ["work"]})
        status, content_type, _, rows = self.request_csv("/notes?tag=missing&format=csv")
        self.assertEqual(status, 200)
        self.assertTrue(content_type.startswith("text/csv"))
        self.assertEqual(rows, [["id", "title", "tags"]])

    def test_csv_export_quoting_unicode_filter_and_default_json(self) -> None:
        notes = []
        for title, tags in (
            ('Café, "planning"\n東京', ['WORK', 'tag,"line\nbreak', 'équipe']),
            ("Other", ["workshop"]),
            ("After", ["work", "urgent"]),
            ("Untagged", []),
        ):
            status, _, note = self.request("/notes", {"title": title, "tags": tags})
            self.assertEqual(status, 201)
            notes.append(note)

        status, content_type, body, rows = self.request_csv("/notes?format=csv")
        self.assertEqual(status, 200)
        self.assertTrue(content_type.startswith("text/csv"))
        self.assertIn("Café".encode("utf-8"), body)
        self.assertIn("東京".encode("utf-8"), body)
        expected_rows = [["id", "title", "tags"]] + [
            [str(note["id"]), note["title"], ";".join(note["tags"])] for note in notes
        ]
        self.assertEqual(rows, expected_rows)
        self.assertIn('"Café, ""planning""\n東京"', body.decode("utf-8"))

        status, content_type, _, rows = self.request_csv("/notes?tag=WORK&format=csv")
        self.assertEqual(status, 200)
        self.assertTrue(content_type.startswith("text/csv"))
        self.assertEqual(rows, [expected_rows[0], expected_rows[1], expected_rows[3]])

        status, content_type, listed = self.request("/notes")
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "application/json; charset=utf-8")
        self.assertEqual(listed, notes)

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

    def test_filter_notes_by_exact_case_insensitive_tag(self) -> None:
        created = []
        for title, tags in (
            ("First", ["WORK", "urgent"]),
            ("Substring", ["workshop"]),
            ("Other", ["personal"]),
            ("Second", ["work"]),
            ("No tags", []),
            ("Third", ["WoRk"]),
        ):
            status, content_type, note = self.request("/notes", {"title": title, "tags": tags})
            self.assertEqual(status, 201)
            self.assertTrue(content_type.startswith("application/json"))
            self.assertEqual(note, {"id": len(created) + 1, "title": title, "tags": tags})
            created.append(note)

        for path in ("/notes?tag=work", "/notes?tag=WORK"):
            with self.subTest(path=path):
                status, content_type, body = self.request(path)
                self.assertEqual(status, 200)
                self.assertEqual(content_type, "application/json; charset=utf-8")
                self.assertEqual(body, [created[0], created[3], created[5]])

        status, content_type, body = self.request("/notes?tag=missing")
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "application/json; charset=utf-8")
        self.assertEqual(body, [])

        status, content_type, body = self.request("/notes")
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "application/json; charset=utf-8")
        self.assertEqual(body, created)

    def test_retrieve_notes_and_failed_lookups_preserve_order(self) -> None:
        created = [
            self.request("/notes", {"title": "Café", "tags": ["personal"]}),
            self.request("/notes", {"title": "Plan", "tags": ["work", "urgent"]}),
            self.request("/notes", {"title": "Last", "tags": []}),
        ]
        for response in created:
            self.assertEqual(response[0], 201)
            status, content_type, body = self.request(f"/notes/{response[2]['id']}")
            self.assertEqual(status, 200)
            self.assertTrue(content_type.startswith("application/json"))
            self.assertEqual(body, response[2])

        for path in ("/notes/999", "/notes/not-a-number", "/notes/1/extra"):
            with self.subTest(path=path):
                status, content_type, body = self.request(path)
                self.assertEqual(status, 404)
                self.assertTrue(content_type.startswith("application/json"))
                self.assertEqual(body, {"error": "not found"})

        status, content_type, body = self.request("/notes")
        self.assertEqual(status, 200)
        self.assertTrue(content_type.startswith("application/json"))
        self.assertEqual(body, [response[2] for response in created])

    def test_invalid_note_does_not_change_list(self) -> None:
        status, _, body = self.request("/notes", {"title": "", "tags": ["work"]})
        self.assertEqual(status, 400)
        self.assertIn("title", body["error"])
        status, _, body = self.request("/notes")
        self.assertEqual(status, 200)
        self.assertEqual(body, [])

    def test_patch_title_preserves_tags_and_id(self) -> None:
        original = self.request("/notes", {"title": "First", "tags": ["personal"]})[2]
        updated = {"id": original["id"], "title": "Revised", "tags": ["personal"]}
        status, content_type, body = self.request("/notes/1", {"title": "Revised"}, method="PATCH")
        self.assertEqual(status, 200)
        self.assertTrue(content_type.startswith("application/json"))
        self.assertEqual(body, updated)
        self.assertEqual(self.request("/notes/1")[2], updated)

    def test_patch_unicode_tags_preserves_title_id_and_list_order(self) -> None:
        first = self.request("/notes", {"title": "First", "tags": ["old"]})[2]
        second = self.request("/notes", {"title": "Second", "tags": ["work"]})[2]
        last = self.request("/notes", {"title": "Last", "tags": []})[2]
        updated = {"id": second["id"], "title": second["title"], "tags": ["café", "東京"]}
        status, content_type, body = self.request("/notes/2", {"tags": updated["tags"]}, method="PATCH")
        self.assertEqual(status, 200)
        self.assertTrue(content_type.startswith("application/json"))
        self.assertEqual(body, updated)
        self.assertEqual(self.request("/notes/2")[2], updated)
        self.assertEqual(self.request("/notes")[2], [first, updated, last])

    def test_invalid_patch_and_unknown_id_do_not_change_notes(self) -> None:
        first = self.request("/notes", {"title": "First", "tags": ["old"]})[2]
        second = self.request("/notes", {"title": "Second", "tags": []})[2]
        for payload, error_field in (
            ({"title": "  "}, "title"),
            ({"tags": ["valid", ""]}, "tags"),
            ({"title": "Changed", "tags": [123]}, "tags"),
            ({"tags": "not a list"}, "tags"),
        ):
            with self.subTest(payload=payload):
                status, content_type, body = self.request("/notes/1", payload, method="PATCH")
                self.assertEqual(status, 400)
                self.assertTrue(content_type.startswith("application/json"))
                self.assertIn(error_field, body["error"])
                self.assertEqual(self.request("/notes/1")[2], first)
                self.assertEqual(self.request("/notes")[2], [first, second])

        status, content_type, body = self.request("/notes/999", {"title": "Missing"}, method="PATCH")
        self.assertEqual(status, 404)
        self.assertTrue(content_type.startswith("application/json"))
        self.assertEqual(body, {"error": "not found"})
        self.assertEqual(self.request("/notes/1")[2], first)
        self.assertEqual(self.request("/notes")[2], [first, second])

    def test_unknown_route_returns_not_found(self) -> None:
        status, _, body = self.request("/missing")
        self.assertEqual(status, 404)
        self.assertEqual(body, {"error": "not found"})


if __name__ == "__main__":
    unittest.main()
