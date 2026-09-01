from importlib.util import module_from_spec, spec_from_file_location

spec = spec_from_file_location("gmail_job_intake", "scripts/gmail_job_intake.py")
module = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_extract_title_and_company():
    title = module.extract_title("Job Alert: Associate Technical Support Engineer", "")
    assert "Associate Technical Support Engineer" in title
    assert module.extract_company({"from": "jobs@salesforce.com"}, title, "") == "Salesforce"


def test_extract_url_ignores_unsubscribe_links():
    text = "Apply https://careers.example.com/jobs/123 unsubscribe https://example.com/unsubscribe"
    assert module.extract_url(text) == "https://careers.example.com/jobs/123"


def test_html_anchor_href_is_retained_for_url_extraction():
    import base64
    html_body = '<html><body><a href="https://careers.example.com/jobs/456">Apply now</a></body></html>'
    encoded = base64.urlsafe_b64encode(html_body.encode()).decode().rstrip("=")
    message = {"payload": {"headers": [], "mimeType": "text/html", "body": {"data": encoded}}}
    _, body = module.message_text(message)
    assert module.extract_url(body) == "https://careers.example.com/jobs/456"


def test_build_properties_respects_live_notion_property_types():
    props = {
        "Job": {"type": "title", "title": {}},
        "Company": {"type": "rich_text", "rich_text": {}},
        "JD": {"type": "rich_text", "rich_text": {}},
        "Job URL": {"type": "url", "url": {}},
        "Source": {"type": "rich_text", "rich_text": {}},
        "Gmail Message ID": {"type": "rich_text", "rich_text": {}},
        "Status": {"type": "status", "status": {"options": [{"name": "Discovered"}]}},
        "Processing Stage": {"type": "select", "select": {"options": [{"name": "Discovered"}]}},
        "Resume Status": {"type": "select", "select": {"options": [{"name": "Not Started"}]}},
    }
    result = module.build_properties(props, title="Associate Technical Support Engineer", company="Salesforce", body="JD body", url="https://example.com/job/1", source="Gmail", gmail_id="abc123")
    assert result["Status"] == {"status": {"name": "Discovered"}}
    assert result["Processing Stage"] == {"select": {"name": "Discovered"}}
    assert result["Resume Status"] == {"select": {"name": "Not Started"}}
    assert result["Job"]["title"][0]["text"]["content"] == "Associate Technical Support Engineer"


def test_rich_text_is_chunked_without_loss():
    body = "x" * 5001
    chunks = module.value_for("rich_text", body)["rich_text"]
    assert "".join(item["text"]["content"] for item in chunks) == body
    assert all(len(item["text"]["content"]) <= 1900 for item in chunks)


def test_application_confirmation_is_not_ingested():
    text = "Thank you for applying to the Technical Support Engineer position. We received your application."
    assert module.JOB_TERMS.search(text)
    assert module.EXCLUDE_TERMS.search(text)


def test_existing_keys_paginates_all_notion_results(monkeypatch):
    calls = []
    responses = [
        {"results": [{"properties": {"Gmail Message ID": {"type": "rich_text", "rich_text": [{"plain_text": "first"}]}}}], "has_more": True, "next_cursor": "cursor-2"},
        {"results": [{"properties": {"Gmail Message ID": {"type": "rich_text", "rich_text": [{"plain_text": "second"}]}}}], "has_more": False, "next_cursor": None},
    ]

    def fake_notion_request(path, token, *, method="GET", body=None):
        calls.append(body)
        return responses[len(calls) - 1]

    monkeypatch.setattr(module, "notion_request", fake_notion_request)
    props = {"Gmail Message ID": {"type": "rich_text", "rich_text": {}}}
    assert module.existing_keys("notion-token", "data-source", props) == {"first", "second"}
    assert calls[0] == {"page_size": 100}
    assert calls[1] == {"page_size": 100, "start_cursor": "cursor-2"}


def test_process_message_uses_notion_token_for_page_creation(monkeypatch):
    captured = {}

    def fake_create_page(token, data_source_id, properties, body):
        captured["token"] = token
        return "page-123"

    monkeypatch.setattr(module, "create_page", fake_create_page)
    monkeypatch.setattr(module, "build_properties", lambda *args, **kwargs: {})
    message = {"id": "gmail-123", "payload": {"headers": [{"name": "Subject", "value": "Job: Associate Technical Support Engineer"}, {"name": "From", "value": "jobs@example.com"}], "body": {"data": ""}}, "snippet": "We are hiring for an Associate Technical Support Engineer role."}
    outcome, _ = module.process_message("notion-token", "data-source", {"Job": {"type": "title", "title": {}}}, message, set())
    assert outcome == "created"
    assert captured["token"] == "notion-token"
