"""Send unhandled errors to Cardinal's ingest endpoint as LogRecords (schema_version 1).

Reporting is off unless CARDINAL_INGEST_URL is set. It runs on a background thread with a short
timeout and never raises: a monitoring outage must not become an API outage.
"""

import json
import os
import socket
import threading
import traceback
import urllib.request
from pathlib import Path

INGEST_URL = os.getenv("CARDINAL_INGEST_URL", "")
INGEST_TOKEN = os.getenv("CARDINAL_INGEST_TOKEN", "")
SOURCE_REPO = os.getenv("CARDINAL_SOURCE_REPO", "oddballmeasure/cardinal_test_repo")
# The image copies api/app to /app/app; frames are reported with repository-relative paths.
PACKAGE_ROOT = Path(__file__).resolve().parent.parent
REPO_PREFIX = "api/"


def record(error: BaseException, method: str, path: str) -> dict:
    frames = [frame for frame in traceback.extract_tb(error.__traceback__)
              if Path(frame.filename).resolve().is_relative_to(PACKAGE_ROOT)]
    stack = [{"file": REPO_PREFIX + str(Path(frame.filename).resolve().relative_to(PACKAGE_ROOT)),
              "function": frame.name, "line": frame.lineno} for frame in frames]
    text = "".join(traceback.format_exception(error)).replace(str(PACKAGE_ROOT) + "/", REPO_PREFIX)
    return {
        "schema_version": 1,
        "level": "error",
        "event": "request_failed",
        "message": f"{method} {path} raised {type(error).__name__}",
        "source": {"repo": SOURCE_REPO, "component": "api", "revision": os.getenv("GIT_SHA") or None,
                   "host": socket.gethostname(), "pid": os.getpid()},
        "error": {"type": type(error).__name__, "message": str(error), "stack": stack, "traceback": text[-20000:]},
        "data": {"method": method, "path": path},
    }


def send(payload: dict) -> None:
    try:
        request = urllib.request.Request(
            INGEST_URL, data=json.dumps([payload]).encode(), method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {INGEST_TOKEN}"},
        )
        urllib.request.urlopen(request, timeout=3).close()
    except Exception as exc:  # noqa: BLE001 - see module docstring; the failure is still printed
        print(f"cardinal report failed: {exc!r}", flush=True)


def report(error: BaseException, method: str, path: str) -> None:
    if INGEST_URL:
        threading.Thread(target=send, args=(record(error, method, path),), daemon=True).start()
