"""Render active HTTP response bodies; JSON is the baseline format."""

import json


def render_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode("utf-8")
