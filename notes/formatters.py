"""Render active HTTP response bodies; JSON is the baseline format."""

import csv
import io
import json


def render_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def render_csv(notes: list[dict]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(("id", "title", "tags"))
    for note in notes:
        writer.writerow((note["id"], note["title"], ";".join(note["tags"])))
    return output.getvalue().encode("utf-8")
