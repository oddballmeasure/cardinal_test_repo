"""Exercise the API and production frontend through the Compose stack."""

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from playwright.sync_api import expect, sync_playwright


def request(base: str, path: str, payload: dict | None = None) -> tuple[int, str, object]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        base + path,
        data=body,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        response = urlopen(req, timeout=3)
    except HTTPError as error:
        response = error
    with response:
        return response.status, response.headers["Content-Type"], json.loads(response.read())


def test_health_reports_redis_backed_service_ready(api_url: str) -> None:
    assert request(api_url, "/health") == (200, "application/json", {"status": "ok"})


def test_create_and_list_notes_in_order(api_url: str) -> None:
    first = request(api_url, "/notes", {"title": "Café", "tags": ["personal"]})
    second = request(api_url, "/notes", {"title": "Plan", "tags": ["work", "urgent"]})
    assert first[0] == second[0] == 201
    assert first[2] == {"id": 1, "title": "Café", "tags": ["personal"]}
    assert second[2] == {"id": 2, "title": "Plan", "tags": ["work", "urgent"]}
    assert request(api_url, "/notes")[2] == [first[2], second[2]]


def test_get_note_by_id_returns_exact_created_note(api_url: str) -> None:
    created = request(api_url, "/notes", {"title": "Find me", "tags": ["lookup"]})
    assert created[0] == 201
    status, content_type, body = request(api_url, f"/notes/{created[2]['id']}")
    assert (status, content_type, body) == (200, "application/json", created[2])


def test_get_note_with_unknown_or_nonnumeric_id_returns_json_404(api_url: str) -> None:
    for path in ("/notes/999999999", "/notes/not-a-number"):
        assert request(api_url, path) == (404, "application/json", {"error": "not found"})


def test_get_note_does_not_change_ordered_list(api_url: str) -> None:
    before = request(api_url, "/notes")[2]
    created = [
        request(api_url, "/notes", {"title": title, "tags": []})[2]
        for title in ("First", "Second", "Third")
    ]
    expected = [*before, *created]
    assert request(api_url, "/notes")[2] == expected
    assert request(api_url, f"/notes/{created[1]['id']}") == (200, "application/json", created[1])
    assert request(api_url, "/notes") == (200, "application/json", expected)


def test_invalid_note_does_not_change_list(api_url: str) -> None:
    before = request(api_url, "/notes")[2]
    status, _, body = request(api_url, "/notes", {"title": "", "tags": ["work"]})
    assert status == 400
    assert "title" in body["error"]
    assert request(api_url, "/notes")[2] == before


def test_unknown_route_returns_not_found(api_url: str) -> None:
    assert request(api_url, "/missing")[2] == {"error": "not found"}


def test_frontend_is_production_built_and_api_proxy_works(web_url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(web_url)
        expect(page.get_by_role("heading", name="Notes", level=1)).to_be_visible()
        response = page.request.get(web_url + "/api/health")
        assert response.status == 200
        assert response.json() == {"status": "ok"}
        browser.close()


def test_notes_survive_restarting_only_the_api(stack) -> None:
    note = {"title": "Redis persistence", "tags": ["infra"]}
    before = request(stack.api_url, "/notes")[2]
    status, _, created = request(stack.api_url, "/notes", note)
    assert status == 201
    stack.restart_api()
    assert request(stack.api_url, "/notes")[2] == [*before, created]
