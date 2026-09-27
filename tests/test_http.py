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


def test_get_note_by_id_returns_created_note(api_url: str) -> None:
    status, _, created = request(api_url, "/notes", {"title": "Read me", "tags": ["personal", "todo"]})
    assert status == 201
    assert request(api_url, f"/notes/{created['id']}") == (200, "application/json", created)


def test_get_missing_note_ids_return_json_not_found(api_url: str) -> None:
    status, _, created = request(api_url, "/notes", {"title": "Exists", "tags": []})
    assert status == 201
    for missing_id in (str(created["id"] + 1000), "not-a-number"):
        assert request(api_url, f"/notes/{missing_id}") == (404, "application/json", {"error": "not found"})


def test_get_note_by_id_preserves_ordered_notes_list(api_url: str) -> None:
    created = []
    for title in ("First", "Middle", "Last"):
        status, _, note = request(api_url, "/notes", {"title": title, "tags": [title.lower()]})
        assert status == 201
        created.append(note)
    before = request(api_url, "/notes")
    assert before[0] == 200
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


def test_browser_creates_note_with_unicode_tags_without_reloading(web_url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        loads = []
        page.on("load", lambda _: loads.append(True))
        page.goto(web_url)

        title = page.get_by_role("textbox", name="Title")
        tags = page.get_by_role("textbox", name="Tags (comma-separated)")
        assert title.get_attribute("required") is not None
        assert tags.get_attribute("required") is not None
        title.fill("  Travel ideas  ")
        tags.fill("  café , 東京 ,  سفر  , , ")
        with page.expect_response(
            lambda response: response.url == web_url + "/api/notes" and response.request.method == "POST"
        ) as created_response:
            page.get_by_role("button", name="Create note").click()

        response = created_response.value
        assert response.status == 201
        assert response.request.post_data_json == {
            "title": "Travel ideas", "tags": ["café", "東京", "سفر"]
        }
        created = response.json()
        assert created["id"] > 0
        assert created["title"] == "Travel ideas"
        assert created["tags"] == ["café", "東京", "سفر"]
        note = page.get_by_role("list", name="Notes list").locator(":scope > li").filter(
            has=page.get_by_text(created["title"], exact=True)
        )
        expect(note).to_have_count(1)
        expect(note.get_by_role("list", name="Tags for Travel ideas").get_by_role("listitem")).to_have_text(
            created["tags"]
        )
        assert loads == [True]
        browser.close()


def test_browser_rejects_empty_and_whitespace_title_without_creating_note(web_url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(web_url)
        title = page.get_by_role("textbox", name="Title")
        tags = page.get_by_role("textbox", name="Tags (comma-separated)")
        tags.fill("personal")
        before = page.request.get(web_url + "/api/notes").json()
        posts = []
        page.on("request", lambda req: posts.append(req) if req.method == "POST" else None)

        page.get_by_role("button", name="Create note").click()
        assert title.evaluate("element => element.validity.valueMissing")
        title.fill("   ")
        page.get_by_role("button", name="Create note").click()
        expect(page.get_by_role("alert")).to_have_text("Title is required.")
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
