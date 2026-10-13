"""Exercise the API and production frontend through the Compose stack."""

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from playwright.sync_api import expect, sync_playwright


def request(
    base: str, path: str, payload: dict | None = None, method: str | None = None
) -> tuple[int, str, object]:
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


def test_health_reports_redis_backed_service_ready(api_url: str) -> None:
    assert request(api_url, "/health") == (200, "application/json", {"status": "ok"})


def test_create_and_list_notes_in_order(api_url: str) -> None:
    first = request(api_url, "/notes", {"title": "Café", "tags": ["personal"]})
    second = request(api_url, "/notes", {"title": "Plan", "tags": ["work", "urgent"]})
    assert first[0] == second[0] == 201
    assert first[2] == {"id": 1, "title": "Café", "tags": ["personal"]}
    assert second[2] == {"id": 2, "title": "Plan", "tags": ["work", "urgent"]}
    assert request(api_url, "/notes")[2] == [first[2], second[2]]


def get_text(base: str, path: str) -> tuple[int, str, str]:
    with urlopen(Request(base + path), timeout=3) as response:
        return response.status, response.headers["Content-Type"], response.read().decode("utf-8")


def test_tag_filter_and_csv_export(api_url: str) -> None:
    import csv
    import io

    a = request(api_url, "/notes", {"title": 'Hi, "there"\nline Café', "tags": ["TagQx", "b"]})[2]
    request(api_url, "/notes", {"title": "home", "tags": ["homeTagQx"]})
    c = request(api_url, "/notes", {"title": "日本", "tags": ["tagqx"]})[2]

    status, ctype, body = request(api_url, "/notes?tag=TAGQX")
    assert status == 200 and ctype == "application/json"
    assert body == [a, c]

    status, ctype, text = get_text(api_url, "/notes?tag=tagQX&format=csv")
    assert status == 200 and ctype.startswith("text/csv")
    rows = list(csv.reader(io.StringIO(text, newline="")))
    assert rows == [
        ["id", "title", "tags"],
        [str(a["id"]), a["title"], "TagQx;b"],
        [str(c["id"]), "日本", "tagqx"],
    ]

    assert get_text(api_url, "/notes?tag=nomatch-zz&format=csv")[2].strip() == "id,title,tags"
    all_rows = list(csv.reader(io.StringIO(get_text(api_url, "/notes?format=csv")[2], newline="")))
    assert all_rows[0] == ["id", "title", "tags"]
    assert len(all_rows) == len(request(api_url, "/notes")[2]) + 1


def test_get_note_by_id_returns_created_note_without_changing_list(api_url: str) -> None:
    created = request(api_url, "/notes", {"title": "Lookup", "tags": ["x"]})
    assert created[0] == 201
    before = request(api_url, "/notes")[2]
    note_path = f"/notes/{created[2]['id']}"
    assert request(api_url, note_path) == (200, "application/json", created[2])
    assert request(api_url, note_path)[2] == created[2]
    assert request(api_url, "/notes")[2] == before


def test_get_unknown_or_nonnumeric_note_id_returns_not_found(api_url: str) -> None:
    before = request(api_url, "/notes")[2]
    for path in ("/notes/999999", "/notes/abc", "/notes/-1", "/notes/1.5"):
        assert request(api_url, path) == (404, "application/json", {"error": "not found"})
    assert request(api_url, "/notes")[2] == before


def test_invalid_note_does_not_change_list(api_url: str) -> None:
    before = request(api_url, "/notes")[2]
    status, _, body = request(api_url, "/notes", {"title": "", "tags": ["work"]})
    assert status == 400
    assert "title" in body["error"]
    assert request(api_url, "/notes")[2] == before


def test_patch_title_changes_only_title(api_url: str) -> None:
    request(api_url, "/notes", {"title": "Other", "tags": []})
    created = request(api_url, "/notes", {"title": "Old", "tags": ["keep"]})[2]
    path = f"/notes/{created['id']}"
    status, _, body = request(api_url, path, {"title": "new"}, method="PATCH")
    expected = {"id": created["id"], "title": "new", "tags": ["keep"]}
    assert (status, body) == (200, expected)
    assert request(api_url, path)[2] == expected


def test_patch_tags_unicode_keeps_id_and_position(api_url: str) -> None:
    created = request(api_url, "/notes", {"title": "Pos", "tags": ["a"]})[2]
    request(api_url, "/notes", {"title": "After", "tags": []})
    before = request(api_url, "/notes")[2]
    status, _, body = request(
        api_url, f"/notes/{created['id']}", {"tags": ["é", "日本"]}, method="PATCH"
    )
    expected = {"id": created["id"], "title": "Pos", "tags": ["é", "日本"]}
    assert (status, body) == (200, expected)
    after = request(api_url, "/notes")[2]
    assert after == [expected if n["id"] == created["id"] else n for n in before]


def test_patch_invalid_input_returns_400_without_change(api_url: str) -> None:
    created = request(api_url, "/notes", {"title": "Same", "tags": ["t"]})[2]
    path = f"/notes/{created['id']}"
    before = request(api_url, "/notes")[2]
    for payload in (
        {"title": ""},
        {"title": "   "},
        {"title": 5},
        {"tags": "x"},
        {"tags": [""]},
        {"tags": [1]},
        {"title": "changed", "tags": [""]},
        [],
    ):
        assert request(api_url, path, payload, method="PATCH")[0] == 400
    req = Request(api_url + path, data=b"{bad", method="PATCH",
                  headers={"Content-Type": "application/json"})
    try:
        urlopen(req, timeout=3)
        raise AssertionError("expected 400")
    except HTTPError as error:
        assert error.code == 400
        error.close()
    assert request(api_url, path)[2] == created
    assert request(api_url, "/notes")[2] == before


def test_patch_unknown_note_returns_not_found(api_url: str) -> None:
    before = request(api_url, "/notes")[2]
    for path in ("/notes/999999", "/notes/abc", "/notes/-1", "/notes/%D9%A1"):
        assert request(api_url, path, {"title": "x"}, method="PATCH") == (
            404, "application/json", {"error": "not found"})
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


def test_note_form_fields_are_visible(web_url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(web_url)
        expect(page.get_by_label("Title")).to_be_visible()
        expect(page.get_by_label("Tags")).to_be_visible()
        expect(page.get_by_role("button", name="Add note")).to_be_visible()
        browser.close()


def test_note_form_creates_note_with_trimmed_unicode_tags(web_url: str) -> None:
    title = "Hello form"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(web_url)
        page.get_by_label("Title").fill(title)
        page.get_by_label("Tags").fill(" alpha , 日本語 , café ,, ")
        with page.expect_response(
            lambda r: r.url.endswith("/api/notes") and r.request.method == "POST"
        ) as posted:
            page.get_by_role("button", name="Add note").click()
        assert posted.value.status == 201
        assert posted.value.request.post_data_json == {
            "title": title,
            "tags": ["alpha", "日本語", "café"],
        }
        item = page.get_by_test_id("note").filter(has_text=title)
        expect(item).to_have_count(1)
        expect(item).to_contain_text("alpha, 日本語, café")
        expect(page.get_by_label("Title")).to_have_value("")
        expect(page.get_by_label("Tags")).to_have_value("")
        stored = page.request.get(web_url + "/api/notes").json()
        assert any(
            n["title"] == title and n["tags"] == ["alpha", "日本語", "café"] for n in stored
        )
        browser.close()


def test_note_form_rejects_empty_title(web_url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(web_url)
        before = page.request.get(web_url + "/api/notes").json()
        page.get_by_label("Tags").fill("x")
        page.get_by_label("Title").fill("   ")
        page.get_by_role("button", name="Add note").click()
        expect(page.get_by_role("alert")).to_contain_text("Title is required")
        assert page.request.get(web_url + "/api/notes").json() == before
        browser.close()


def test_notes_survive_restarting_only_the_api(stack) -> None:
    note = {"title": "Redis persistence", "tags": ["infra"]}
    before = request(stack.api_url, "/notes")[2]
    status, _, created = request(stack.api_url, "/notes", note)
    assert status == 201
    stack.restart_api()
    assert request(stack.api_url, "/notes")[2] == [*before, created]


def test_create_and_list_diaries_in_order(stack) -> None:
    api_url = stack.api_url  # the port changes after an API restart
    before = request(api_url, "/diaries")[2]
    one = {"date": "2024-02-29", "title": "Café", "body": "Leap day"}
    two = {"date": "2024-03-01", "title": "Next", "body": "日本"}
    first = request(api_url, "/diaries", one)
    second = request(api_url, "/diaries", two)
    assert first[0] == second[0] == 201
    assert first[1] == "application/json"
    assert {k: v for k, v in first[2].items() if k != "id"} == one
    assert isinstance(first[2]["id"], int)
    assert {k: v for k, v in second[2].items() if k != "id"} == two
    assert request(api_url, "/diaries")[2] == [*before, first[2], second[2]]


def test_invalid_diary_returns_400_without_change(stack) -> None:
    api_url = stack.api_url  # the port changes after an API restart
    before = request(api_url, "/diaries")[2]
    good = {"date": "2024-01-02", "title": "T", "body": "B"}
    for payload in (
        {**good, "date": "2024-02-30"},
        {**good, "date": "abc"},
        {**good, "date": "2024-1-2"},
        {**good, "date": 20240102},
        {"title": "T", "body": "B"},
        {"date": "2024-01-02", "body": "B"},
        {"date": "2024-01-02", "title": "T"},
        {**good, "title": ""},
        {**good, "title": "   "},
        {**good, "body": ""},
        {**good, "body": 5},
        [],
    ):
        status, _, body = request(api_url, "/diaries", payload)
        assert status == 400
        assert "error" in body
    req = Request(api_url + "/diaries", data=b"{bad", method="POST",
                  headers={"Content-Type": "application/json"})
    try:
        urlopen(req, timeout=3)
        raise AssertionError("expected 400")
    except HTTPError as error:
        assert error.code == 400
        error.close()
    assert request(api_url, "/diaries")[2] == before


def test_diaries_survive_restarting_only_the_api(stack) -> None:
    diary = {"date": "2024-05-06", "title": "Persist", "body": "Redis"}
    before = request(stack.api_url, "/diaries")[2]
    status, _, created = request(stack.api_url, "/diaries", diary)
    assert status == 201
    stack.restart_api()
    assert request(stack.api_url, "/diaries")[2] == [*before, created]


def test_tag_stats_summarise_stored_notes(stack) -> None:
    assert request(stack.api_url, "/notes", {"title": "Stats", "tags": ["a", "b"]})[0] == 201
    notes = request(stack.api_url, "/notes")[2]
    total = sum(len(note["tags"]) for note in notes)
    assert request(stack.api_url, "/stats/tags") == (200, "application/json", {
        "notes": len(notes), "tags": total, "average_tags_per_note": round(total / len(notes), 2)})
