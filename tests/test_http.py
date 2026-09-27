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


def test_get_note_by_id_preserves_ordered_list(api_url: str) -> None:
    first = request(api_url, "/notes", {"title": "First lookup", "tags": ["first"]})
    second = request(api_url, "/notes", {"title": "Second lookup", "tags": ["second"]})
    assert first[0] == second[0] == 201

    before = request(api_url, "/notes")
    assert before[0:2] == (200, "application/json")
    assert before[2][-2:] == [first[2], second[2]]

    assert request(api_url, f"/notes/{first[2]['id']}") == (200, "application/json", first[2])
    assert request(api_url, "/notes") == before


def test_unknown_and_nonnumeric_note_ids_return_json_not_found(api_url: str) -> None:
    status, _, created = request(api_url, "/notes", {"title": "Known ID", "tags": []})
    assert status == 201
    for note_id in (str(created["id"] + 10000), "not-a-number"):
        assert request(api_url, f"/notes/{note_id}") == (404, "application/json", {"error": "not found"})


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


def test_browser_loads_existing_notes_and_creates_note_without_reloading(web_url: str, api_url: str) -> None:
    existing_title = f"Existing {uuid4().hex}"
    created_title = f"Café {uuid4().hex}"
    status, _, existing = request(api_url, "/notes", {"title": existing_title, "tags": ["saved"]})
    assert status == 201

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        posted = []
        loads = []
        page.on("request", lambda req: posted.append(req.post_data_json)
                if req.method == "POST" and req.url.endswith("/api/notes") else None)
        page.on("load", lambda _: loads.append(True))
        page.goto(web_url)
        notes_list = page.get_by_role("list", name="Notes list")
        expect(notes_list.get_by_role("listitem").filter(has_text=existing_title)).to_contain_text("saved")
        assert len(loads) == 1

        title_field = page.get_by_role("textbox", name="Title")
        tags_field = page.get_by_role("textbox", name="Tags (comma-separated)")
        assert title_field.get_attribute("required") is not None
        assert tags_field.get_attribute("required") is not None
        title_field.fill(created_title)
        tags_field.fill("  café , 日本語  ,  résumé  ")
        page.get_by_role("button", name="Create note").click()

        # The new item appears in the current document, before any navigation or reload.
        expect(notes_list.get_by_role("listitem").filter(has_text=created_title)).to_contain_text(
            "café, 日本語, résumé"
        )
        assert len(loads) == 1
        assert posted == [{"title": created_title, "tags": ["café", "日本語", "résumé"]}]
        persisted = page.request.get(web_url + "/api/notes")
        assert persisted.status == 200
        assert existing in persisted.json()
        assert any(note["title"] == created_title and note["tags"] == posted[0]["tags"]
                   for note in persisted.json())
        browser.close()


def test_browser_rejects_empty_and_whitespace_titles(web_url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        posts = []
        page.on("request", lambda req: posts.append(req.url)
                if req.method == "POST" and req.url.endswith("/api/notes") else None)
        page.goto(web_url)
        before = page.request.get(web_url + "/api/notes").json()
        page.get_by_role("textbox", name="Tags (comma-separated)").fill("valid")
        page.get_by_role("button", name="Create note").click()
        page.get_by_role("textbox", name="Title").fill("   ")
        page.get_by_role("button", name="Create note").click()
        assert posts == []
        assert page.request.get(web_url + "/api/notes").json() == before
        browser.close()


def test_notes_survive_restarting_only_the_api(stack) -> None:
    note = {"title": "Redis persistence", "tags": ["infra"]}
    before = request(stack.api_url, "/notes")[2]
    status, _, created = request(stack.api_url, "/notes", note)
    assert status == 201
    stack.restart_api()
    assert request(stack.api_url, "/notes")[2] == [*before, created]
