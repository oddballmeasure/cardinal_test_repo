"""Exercise the API and production frontend through the Compose stack."""

import json
from uuid import uuid4
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


def test_retrieve_note_by_id_preserves_ordered_list(api_url: str) -> None:
    before = request(api_url, "/notes")[2]
    first = request(api_url, "/notes", {"title": "First", "tags": ["read"]})
    second = request(api_url, "/notes", {"title": "Second", "tags": []})
    third = request(api_url, "/notes", {"title": "Third", "tags": ["later"]})
    assert first[0] == second[0] == third[0] == 201
    ordered = [*before, first[2], second[2], third[2]]
    assert request(api_url, "/notes") == (200, "application/json", ordered)
    assert request(api_url, f"/notes/{second[2]['id']}") == (200, "application/json", second[2])
    assert request(api_url, "/notes") == (200, "application/json", ordered)


def test_unknown_and_nonnumeric_note_ids_return_json_404(api_url: str) -> None:
    notes = request(api_url, "/notes")[2]
    unknown_id = max((note["id"] for note in notes), default=0) + 1
    for path in (f"/notes/{unknown_id}", "/notes/not-a-number"):
        assert request(api_url, path) == (404, "application/json", {"error": "not found"})


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


def test_browser_creates_note_through_proxy_and_updates_list_without_reload(web_url: str) -> None:
    existing_title = f"Existing {uuid4().hex}"
    status, _, existing = request(web_url, "/api/notes", {"title": existing_title, "tags": ["saved"]})
    assert status == 201
    title = f"Café 東京 {uuid4().hex}"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(web_url)
        notes = page.get_by_role("list", name="Notes list")
        expect(notes.get_by_text(existing_title)).to_be_visible()
        page.evaluate("window.notesPageMarker = 'original page'")

        title_input = page.get_by_role("textbox", name="Title")
        tags_input = page.get_by_role("textbox", name="Tags (comma-separated)")
        assert title_input.get_attribute("required") is not None
        title_input.fill(title)
        tags_input.fill("  café , , 東京  , \t🙂\t ,  ")
        with page.expect_request(lambda req: req.url == web_url + "/api/notes" and req.method == "POST") as sent:
            with page.expect_response(lambda res: res.url == web_url + "/api/notes" and res.request.method == "POST") as received:
                page.get_by_role("button", name="Create note").click()
        assert json.loads(sent.value.post_data) == {"title": title, "tags": ["café", "東京", "🙂"]}
        assert sent.value.headers["content-type"].startswith("application/json")
        assert received.value.status == 201
        created = received.value.json()
        assert created == {"id": created["id"], "title": title, "tags": ["café", "東京", "🙂"]}
        expect(notes.get_by_role("listitem").filter(has_text=title)).to_contain_text("café, 東京, 🙂")
        assert page.evaluate("window.notesPageMarker") == "original page"
        assert request(web_url, f"/api/notes/{created['id']}")[2] == created
        browser.close()


def test_browser_rejects_empty_and_whitespace_titles(web_url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(web_url)
        before = request(web_url, "/api/notes")[2]
        posts = []
        page.on("request", lambda req: posts.append(req) if req.url == web_url + "/api/notes" and req.method == "POST" else None)
        title = page.get_by_role("textbox", name="Title")
        assert title.get_attribute("required") is not None
        page.get_by_role("textbox", name="Tags (comma-separated)").fill("work")
        page.get_by_role("button", name="Create note").click()
        assert title.evaluate("input => input.validity.valueMissing")
        title.fill("  \t  ")
        page.get_by_role("button", name="Create note").click()
        expect(page.get_by_role("alert")).to_have_text("Title is required.")
        assert posts == []
        assert request(web_url, "/api/notes")[2] == before
        browser.close()


def test_notes_survive_restarting_only_the_api(stack) -> None:
    note = {"title": "Redis persistence", "tags": ["infra"]}
    before = request(stack.api_url, "/notes")[2]
    status, _, created = request(stack.api_url, "/notes", note)
    assert status == 201
    stack.restart_api()
    assert request(stack.api_url, "/notes")[2] == [*before, created]
