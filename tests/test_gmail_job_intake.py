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
    result = module.build_properties(
        props,
        title="Associate Technical Support Engineer",
        company="Salesforce",
        body="JD body",
        url="https://example.com/job/1",
        source="Gmail",
        gmail_id="abc123",
    )
    assert result["Status"] == {"status": {"name": "Discovered"}}
    assert result["Processing Stage"] == {"select": {"name": "Discovered"}}
    assert result["Resume Status"] == {"select": {"name": "Not Started"}}
    assert result["Job"]["title"][0]["text"]["content"] == "Associate Technical Support Engineer"


def test_application_confirmation_is_not_ingested():
    text = "Thank you for applying to the Technical Support Engineer position. We received your application."
    assert module.JOB_TERMS.search(text)
    assert module.EXCLUDE_TERMS.search(text)
