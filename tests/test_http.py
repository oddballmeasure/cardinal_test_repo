"""Exercise the API and production frontend through the Compose stack."""

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from playwright.sync_api import expect, sync_playwright


def request(base: str, path: str, payload: dict | None = None, *, method: str | None = None) -> tuple[int, str, object]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        base + path,
        data=body,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method=method,
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


def test_get_note_by_id_preserves_ordered_list(api_url: str) -> None:
    existing = request(api_url, "/notes")[2]
    created = [
        request(api_url, "/notes", {"title": "First", "tags": ["one"]}),
        request(api_url, "/notes", {"title": "Middle", "tags": ["two", "three"]}),
        request(api_url, "/notes", {"title": "Last", "tags": []}),
    ]
    assert all(status == 201 for status, _, _ in created)
    before = request(api_url, "/notes")
    assert before == (200, "application/json", [*existing, *(body for _, _, body in created)])

    middle = created[1][2]
    assert request(api_url, f"/notes/{middle['id']}") == (200, "application/json", middle)
    assert request(api_url, "/notes") == before


def test_get_note_by_id_returns_json_404_for_missing_ids(api_url: str) -> None:
    for path in ("/notes/999999", "/notes/not-a-number", "/notes/0", "/notes/-1"):
        assert request(api_url, path) == (404, "application/json", {"error": "not found"})


def test_patch_title_updates_only_title_in_get_and_ordered_list(api_url: str) -> None:
    before = request(api_url, "/notes")[2]
    first = request(api_url, "/notes", {"title": "First", "tags": ["keep"]})[2]
    middle = request(api_url, "/notes", {"title": "Old", "tags": ["work", "café"]})[2]
    last = request(api_url, "/notes", {"title": "Last", "tags": []})[2]

    updated = {**middle, "title": "New title"}
    assert request(api_url, f"/notes/{middle['id']}", {"title": "New title"}, method="PATCH") == (
        200, "application/json", updated
    )
    assert request(api_url, f"/notes/{middle['id']}") == (200, "application/json", updated)
    assert request(api_url, "/notes") == (200, "application/json", [*before, first, updated, last])


def test_patch_tags_supports_unicode_and_keeps_id_title_and_list_order(api_url: str) -> None:
    before = request(api_url, "/notes")[2]
    first = request(api_url, "/notes", {"title": "First", "tags": ["old"]})[2]
    middle = request(api_url, "/notes", {"title": "Unchanged", "tags": []})[2]
    last = request(api_url, "/notes", {"title": "Last", "tags": ["keep"]})[2]

    updated = {**middle, "tags": ["工作", "日本語", "café"]}
    assert request(api_url, f"/notes/{middle['id']}", {"tags": updated["tags"]}, method="PATCH") == (
        200, "application/json", updated
    )
    assert request(api_url, f"/notes/{middle['id']}") == (200, "application/json", updated)
    assert request(api_url, "/notes") == (200, "application/json", [*before, first, updated, last])


def test_invalid_patch_never_changes_note_or_ordered_list(api_url: str) -> None:
    original = request(api_url, "/notes", {"title": "Keep", "tags": ["safe"]})[2]
    path = f"/notes/{original['id']}"
    before = request(api_url, "/notes")
    for payload in (
        {"title": ""},
        {"title": "  \t "},
        {"title": None},
        {"title": 42},
        {"tags": "not a list"},
        {"tags": None},
        {"tags": ["valid", ""]},
        {"tags": ["valid", 7]},
        {"title": "Would change", "tags": [None]},
    ):
        status, content_type, body = request(api_url, path, payload, method="PATCH")
        assert (status, content_type) == (400, "application/json")
        assert "error" in body
        assert request(api_url, path) == (200, "application/json", original)
        assert request(api_url, "/notes") == before


def test_patch_unknown_id_returns_json_404_without_changing_list(api_url: str) -> None:
    before = request(api_url, "/notes")
    for path in ("/notes/999999", "/notes/not-a-number", "/notes/0", "/notes/-1"):
        assert request(api_url, path, {"tags": ["valid"]}, method="PATCH") == (
            404, "application/json", {"error": "not found"}
        )
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


def test_browser_creates_note_with_unicode_tags_and_renders_without_reload(web_url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(web_url)
        title = page.get_by_role("textbox", name="Title")
        tags = page.get_by_role("textbox", name="Tags (comma-separated)")
        assert title.get_attribute("required") is not None
        assert tags.is_visible()
        page.evaluate("window.notePageMarker = 'still here'")

        title.fill("Café meeting")
        tags.fill("  工作 , , café  ,  日本語 ,   ")
        with page.expect_response(
            lambda response: response.url.endswith("/api/notes") and response.request.method == "POST"
        ) as captured:
            page.get_by_role("button", name="Create note").click()
        response = captured.value
        assert response.status == 201
        assert response.request.post_data_json == {
            "title": "Café meeting",
            "tags": ["工作", "café", "日本語"],
        }
        created = response.json()
        assert created["id"] > 0
        assert created["title"] == "Café meeting"
        assert created["tags"] == ["工作", "café", "日本語"]
        note = page.locator("section[aria-labelledby='notes-heading'] li").filter(has_text="Café meeting")
        expect(note).to_have_text("Café meeting — 工作, café, 日本語")
        assert page.evaluate("window.notePageMarker") == "still here"
        browser.close()


def test_browser_rejects_empty_and_whitespace_titles_without_post(web_url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(web_url)
        posted = []
        page.on(
            "request",
            lambda req: posted.append(req) if req.url.endswith("/api/notes") and req.method == "POST" else None,
        )
        title = page.get_by_role("textbox", name="Title")
        page.get_by_role("textbox", name="Tags (comma-separated)").fill("one, two")
        page.get_by_role("button", name="Create note").click()
        assert not title.evaluate("element => element.validity.valid")
        assert posted == []

        title.fill("   \t  ")
        page.get_by_role("button", name="Create note").click()
        expect(page.get_by_role("alert")).to_have_text("Title is required")
        assert posted == []
        assert page.evaluate("window.location.pathname") == "/"
        browser.close()


def test_notes_survive_restarting_only_the_api(stack) -> None:
    note = {"title": "Redis persistence", "tags": ["infra"]}
    before = request(stack.api_url, "/notes")[2]
    status, _, created = request(stack.api_url, "/notes", note)
    assert status == 201
    stack.restart_api()
    assert request(stack.api_url, "/notes")[2] == [*before, created]
