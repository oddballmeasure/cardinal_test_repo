"""Exercise the API and production frontend through the Compose stack."""

import csv
from io import StringIO
import json
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


def request(base: str, path: str, payload: dict | None = None, *, method: str | None = None) -> tuple[int, str, object]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
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


def csv_response(base: str, path: str) -> tuple[int, str, str]:
    with urlopen(base + path, timeout=3) as response:
        return response.status, response.headers["Content-Type"], response.read().decode("utf-8")


def test_health_reports_redis_backed_service_ready(api_url: str) -> None:
    assert request(api_url, "/health") == (200, "application/json", {"status": "ok"})


def test_csv_listing_without_notes_has_only_header(api_url: str) -> None:
    assert request(api_url, "/notes") == (200, "application/json", [])
    status, content_type, text = csv_response(api_url, "/notes?format=csv")
    assert status == 200
    assert content_type.split(";", 1)[0] == "text/csv"
    assert text == "id,title,tags\r\n"


def test_create_and_list_notes_in_order(api_url: str) -> None:
    first = request(api_url, "/notes", {"title": "Café", "tags": ["personal"]})
    second = request(api_url, "/notes", {"title": "Plan", "tags": ["work", "urgent"]})
    assert first[0] == second[0] == 201
    assert first[2] == {"id": 1, "title": "Café", "tags": ["personal"]}
    assert second[2] == {"id": 2, "title": "Plan", "tags": ["work", "urgent"]}
    assert request(api_url, "/notes")[2] == [first[2], second[2]]


def test_tag_filter_exact_case_insensitive_and_ordered(api_url: str) -> None:
    tag = f"Straße-{uuid4().hex}"
    before = request(api_url, "/notes")[2]
    first = request(api_url, "/notes", {"title": "First", "tags": [tag.upper(), "other"]})[2]
    partial = request(api_url, "/notes", {"title": "Partial", "tags": [tag + "-extra"]})[2]
    last = request(api_url, "/notes", {"title": "Last", "tags": [tag.lower()]})[2]
    assert request(api_url, f"/notes?tag={quote(tag)}") == (200, "application/json", [first, last])
    assert request(api_url, "/notes") == (200, "application/json", [*before, first, partial, last])


def test_csv_listing_quotes_special_characters_and_preserves_unicode(api_url: str) -> None:
    note = request(api_url, "/notes", {"title": 'He said "hi",\n東京', "tags": ["café,work", 'quoted"tag', "line\nbreak"]})[2]
    empty_tags = request(api_url, "/notes", {"title": "No tags", "tags": []})[2]
    listed = request(api_url, "/notes")
    assert listed[0:2] == (200, "application/json")
    assert listed[2][-2:] == [note, empty_tags]

    status, content_type, text = csv_response(api_url, "/notes?format=csv")
    assert status == 200
    assert content_type.split(";", 1)[0] == "text/csv"
    assert text.startswith("id,title,tags\r\n")
    assert f'{note["id"]},"He said ""hi"",\n東京","café,work;quoted""tag;line\nbreak"\r\n' in text
    assert text.endswith(f'{empty_tags["id"]},No tags,\r\n')
    assert list(csv.reader(StringIO(text))) == [
        ["id", "title", "tags"],
        *[[str(entry["id"]), entry["title"], ";".join(entry["tags"])] for entry in listed[2]],
    ]


def test_csv_tag_filter_combination_and_no_matches(api_url: str) -> None:
    tag = f"Csv-{uuid4().hex}"
    first = request(api_url, "/notes", {"title": "One, 東京", "tags": [tag.upper(), "extra"]})[2]
    request(api_url, "/notes", {"title": "Not included", "tags": [tag + "suffix"]})
    last = request(api_url, "/notes", {"title": 'Two "quoted"', "tags": [tag.lower()]})[2]
    status, content_type, text = csv_response(api_url, f"/notes?tag={tag}&format=csv")
    assert status == 200
    assert content_type.split(";", 1)[0] == "text/csv"
    assert text == (
        "id,title,tags\r\n"
        f'{first["id"]},"One, 東京",{tag.upper()};extra\r\n'
        f'{last["id"]},"Two ""quoted""",{tag.lower()}\r\n'
    )
    assert csv_response(api_url, f"/notes?tag={uuid4().hex}&format=csv")[2] == "id,title,tags\r\n"


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


def test_patch_title_preserves_tags_and_order(api_url: str) -> None:
    first = request(api_url, "/notes", {"title": "First", "tags": ["café"]})[2]
    second = request(api_url, "/notes", {"title": "Second", "tags": ["work"]})[2]
    before = request(api_url, "/notes")[2]

    updated = {**first, "title": "New title"}
    assert request(api_url, f"/notes/{first['id']}", {"title": "New title"}, method="PATCH") == (
        200, "application/json", updated
    )
    assert request(api_url, f"/notes/{first['id']}")[2] == updated
    assert request(api_url, "/notes")[2] == [*before[:-2], updated, second]


def test_patch_tags_preserves_title_id_and_order_with_unicode(api_url: str) -> None:
    first = request(api_url, "/notes", {"title": "Before", "tags": ["old"]})[2]
    second = request(api_url, "/notes", {"title": "After", "tags": ["other"]})[2]
    before = request(api_url, "/notes")[2]

    updated = {**first, "tags": ["東京", "café", "سفر"]}
    assert request(api_url, f"/notes/{first['id']}", {"tags": updated["tags"]}, method="PATCH") == (
        200, "application/json", updated
    )
    assert request(api_url, f"/notes/{first['id']}")[2] == updated
    assert request(api_url, "/notes")[2] == [*before[:-2], updated, second]


def test_patch_invalid_fields_does_not_change_note_or_list(api_url: str) -> None:
    note = request(api_url, "/notes", {"title": "Keep", "tags": ["work"]})[2]
    before = request(api_url, "/notes")[2]
    for payload, error in (
        ({"title": ""}, "title must be a nonempty string"),
        ({"title": "   "}, "title must be a nonempty string"),
        ({"title": None}, "title must be a nonempty string"),
        ({"tags": "not a list"}, "tags must be a list of nonempty strings"),
        ({"tags": ["ok", ""]}, "tags must be a list of nonempty strings"),
        ({"tags": [42]}, "tags must be a list of nonempty strings"),
        ({"title": "Should not persist", "tags": [None]}, "tags must be a list of nonempty strings"),
    ):
        assert request(api_url, f"/notes/{note['id']}", payload, method="PATCH") == (
            400, "application/json", {"error": error}
        )
        assert request(api_url, f"/notes/{note['id']}")[2] == note
        assert request(api_url, "/notes")[2] == before


def test_patch_missing_id_returns_json_not_found(api_url: str) -> None:
    before = request(api_url, "/notes")[2]
    for missing_id in ("999999", "not-a-number"):
        assert request(api_url, f"/notes/{missing_id}", {"title": "Missing"}, method="PATCH") == (
            404, "application/json", {"error": "not found"}
        )
    assert request(api_url, "/notes")[2] == before


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

        notes = page.get_by_role("region", name="Notes")
        title = notes.get_by_role("textbox", name="Title")
        tags = notes.get_by_role("textbox", name="Tags (comma-separated)")
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
        notes = page.get_by_role("region", name="Notes")
        title = notes.get_by_role("textbox", name="Title")
        tags = notes.get_by_role("textbox", name="Tags (comma-separated)")
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


def test_browser_diary_requires_date_title_and_body(web_url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(web_url)
        diaries = page.get_by_role("region", name="Diaries")
        date = diaries.get_by_label("Date")
        title = diaries.get_by_label("Title")
        body = diaries.get_by_label("Body")
        button = diaries.get_by_role("button", name="Create diary")
        for field in (date, title, body):
            assert field.get_attribute("required") is not None

        before = page.request.get(web_url + "/api/diaries").json()
        posts = []
        page.on("request", lambda req: posts.append(req) if req.url == web_url + "/api/diaries" and req.method == "POST" else None)
        for missing in (date, title, body):
            date.fill("2024-02-29")
            title.fill("Leap day")
            body.fill("Café in 東京")
            missing.fill("")
            button.click()
            assert missing.evaluate("element => element.validity.valueMissing")
        assert posts == []
        assert page.request.get(web_url + "/api/diaries").json() == before
        browser.close()


def test_browser_creates_diary_and_renders_api_response_without_reloading(web_url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        loads = []
        page.on("load", lambda _: loads.append(True))
        page.goto(web_url)
        diaries = page.get_by_role("region", name="Diaries")
        diaries.get_by_label("Date").fill("2024-02-29")
        diaries.get_by_label("Title").fill("Leap day")
        diaries.get_by_label("Body").fill("Café in 東京")
        with page.expect_response(
            lambda response: response.url == web_url + "/api/diaries" and response.request.method == "POST"
        ) as created_response:
            diaries.get_by_role("button", name="Create diary").click()

        response = created_response.value
        assert response.status == 201
        assert response.request.post_data_json == {
            "date": "2024-02-29", "title": "Leap day", "body": "Café in 東京"
        }
        created = response.json()
        assert created == {"id": created["id"], **response.request.post_data_json}
        entry = diaries.get_by_role("list", name="Diaries list").locator(":scope > li").filter(
            has=page.get_by_text("Leap day", exact=True)
        )
        expect(entry).to_have_count(1)
        expect(entry.locator("time")).to_have_text(created["date"])
        expect(entry.locator("strong")).to_have_text(created["title"])
        expect(entry.locator("p")).to_have_text(created["body"])
        assert loads == [True]
        browser.close()


def test_browser_reload_lists_diaries_stored_by_api(web_url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(web_url)
        payload = {"date": "2025-03-14", "title": f"Stored {uuid4().hex}", "body": "Still here after reload"}
        response = page.request.post(web_url + "/api/diaries", data=payload)
        assert response.status == 201
        stored = response.json()
        with page.expect_response(
            lambda response: response.url == web_url + "/api/diaries" and response.request.method == "GET"
        ) as listed_response:
            page.reload()
        assert listed_response.value.status == 200
        assert stored in listed_response.value.json()
        diaries = page.get_by_role("region", name="Diaries")
        entry = diaries.get_by_role("list", name="Diaries list").locator(":scope > li").filter(
            has=page.get_by_text(stored["title"], exact=True)
        )
        expect(entry).to_have_count(1)
        expect(entry.locator("time")).to_have_text(stored["date"])
        expect(entry.locator("strong")).to_have_text(stored["title"])
        expect(entry.locator("p")).to_have_text(stored["body"])
        browser.close()


def test_create_and_list_diaries_in_creation_order(api_url: str) -> None:
    before = request(api_url, "/diaries")
    assert before[0:2] == (200, "application/json")
    first = {"date": "2024-02-29", "title": "Leap day", "body": "Café in 東京"}
    second = {"date": "2025-01-02", "title": "Next", "body": "A new entry"}
    first_response = request(api_url, "/diaries", first)
    second_response = request(api_url, "/diaries", second)
    assert first_response == (201, "application/json", {"id": len(before[2]) + 1, **first})
    assert second_response == (201, "application/json", {"id": len(before[2]) + 2, **second})
    assert request(api_url, "/diaries") == (
        200, "application/json", [*before[2], first_response[2], second_response[2]]
    )


def test_invalid_diaries_do_not_change_list(api_url: str) -> None:
    before = request(api_url, "/diaries")
    valid = {"date": "2024-02-29", "title": "Keep", "body": "Original"}
    invalid = [
        {"date": date} for date in ("2023-02-29", "2024-04-31", "2024-13-01", "20240101", "nonsense")
    ]
    for field in ("date", "title", "body"):
        invalid.extend(({field: ""}, {field: "   "}, {field: None}, {field: 42}, {field: []}))
    for changes in invalid:
        status, content_type, _ = request(api_url, "/diaries", {**valid, **changes})
        assert (status, content_type) == (400, "application/json")
        assert request(api_url, "/diaries") == before
    for field in ("date", "title", "body"):
        missing = {key: value for key, value in valid.items() if key != field}
        assert request(api_url, "/diaries", missing)[0] == 400
        assert request(api_url, "/diaries") == before
    assert request(api_url, "/diaries", [], method="POST")[0] == 400
    assert request(api_url, "/diaries") == before


def test_diaries_survive_restarting_only_the_api(stack) -> None:
    before = request(stack.api_url, "/diaries")[2]
    diary = {"date": "2026-05-18", "title": "Redis persistence", "body": "Still here"}
    status, _, created = request(stack.api_url, "/diaries", diary)
    assert status == 201
    assert created == {"id": len(before) + 1, **diary}
    stack.restart_api()
    assert request(stack.api_url, "/diaries") == (200, "application/json", [*before, created])


def test_notes_survive_restarting_only_the_api(stack) -> None:
    note = {"title": "Redis persistence", "tags": ["infra"]}
    before = request(stack.api_url, "/notes")[2]
    status, _, created = request(stack.api_url, "/notes", note)
    assert status == 201
    stack.restart_api()
    assert request(stack.api_url, "/notes")[2] == [*before, created]
