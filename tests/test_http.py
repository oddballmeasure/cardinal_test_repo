"""Exercise the API and production frontend through the Compose stack."""

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

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


def test_get_note_by_id_returns_created_json(api_url: str) -> None:
    status, content_type, created = request(api_url, "/notes", {"title": "Retrieve me", "tags": ["lookup"]})
    assert (status, content_type) == (201, "application/json")
    assert request(api_url, f"/notes/{created['id']}") == (200, "application/json", created)


def test_get_note_by_unknown_or_nonnumeric_id_returns_json_404(api_url: str) -> None:
    notes = request(api_url, "/notes")[2]
    unknown_id = max((note["id"] for note in notes), default=0) + 1000
    for path in (f"/notes/{unknown_id}", "/notes/not-a-number"):
        assert request(api_url, path) == (404, "application/json", {"error": "not found"})


def test_get_note_by_id_preserves_list_order(api_url: str) -> None:
    created = [request(api_url, "/notes", {"title": title, "tags": []})[2]
               for title in ("First lookup", "Middle lookup", "Last lookup")]
    before = request(api_url, "/notes")
    assert before[2][-3:] == created
    assert request(api_url, f"/notes/{created[1]['id']}")[2] == created[1]
    assert request(api_url, "/notes") == before


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


def test_browser_creates_note_with_trimmed_unicode_tags(web_url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        with page.expect_response(lambda response: response.url.endswith("/api/notes") and response.request.method == "GET"):
            page.goto(web_url)
        title_field = page.get_by_role("textbox", name="Title")
        tags_field = page.get_by_role("textbox", name="Tags (comma-separated)")
        expect(title_field).to_be_visible()
        expect(tags_field).to_be_visible()
        assert title_field.get_attribute("required") is not None
        navigations = []
        page.on("framenavigated", lambda frame: navigations.append(frame.url) if frame == page.main_frame else None)
        title = f"Browser note {uuid4().hex}"
        title_field.fill(title)
        tags_field.fill("  café , , 東京 ,  🍵  , ")
        with page.expect_response(lambda response: response.url.endswith("/api/notes") and response.request.method == "POST") as posted:
            page.get_by_role("button", name="Create note").click()
        response = posted.value
        assert response.status == 201
        assert response.request.post_data_json == {"title": title, "tags": ["café", "東京", "🍵"]}
        created = response.json()
        assert created == {"id": created["id"], "title": title, "tags": ["café", "東京", "🍵"]}
        expect(page.locator("section[aria-labelledby='notes-heading'] li").filter(has_text=title)).to_contain_text(
            "café, 東京, 🍵"
        )
        # The list is updated on the current page, rather than after navigation/reload.
        assert navigations == []
        expect(page.get_by_role("textbox", name="Title")).to_be_empty()
        browser.close()


def test_browser_rejects_blank_note_titles(web_url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        with page.expect_response(lambda response: response.url.endswith("/api/notes") and response.request.method == "GET"):
            page.goto(web_url)
        before = page.request.get(web_url + "/api/notes").json()
        title = page.get_by_role("textbox", name="Title")
        tags = page.get_by_role("textbox", name="Tags (comma-separated)")
        tags.fill("test")
        page.get_by_role("button", name="Create note").click()
        assert title.evaluate("element => element.validity.valueMissing")
        title.fill("  \t  ")
        page.get_by_role("button", name="Create note").click()
        expect(page.get_by_role("alert")).to_contain_text("Enter a title")
        assert page.request.get(web_url + "/api/notes").json() == before
        browser.close()


def test_notes_survive_restarting_only_the_api(stack) -> None:
    note = {"title": "Redis persistence", "tags": ["infra"]}
    before = request(stack.api_url, "/notes")[2]
    status, _, created = request(stack.api_url, "/notes", note)
    assert status == 201
    stack.restart_api()
    assert request(stack.api_url, "/notes")[2] == [*before, created]


def test_tag_stats_summarise_stored_notes(stack) -> None:
    assert request(stack.api_url, "/notes", {"title": "Stats", "tags": ["a", "b"]})[0] == 201
    notes = request(stack.api_url, "/notes")[2]
    total = sum(len(note["tags"]) for note in notes)
    assert request(stack.api_url, "/stats/tags") == (200, "application/json", {
        "notes": len(notes), "tags": total, "average_tags_per_note": round(total / len(notes), 2)})
