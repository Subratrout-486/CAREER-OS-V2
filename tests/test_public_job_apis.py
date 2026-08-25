from __future__ import annotations

import json
from urllib.error import HTTPError
from io import BytesIO

import pytest

from career_os.agents.public_job_scout import PublicJobScout
from career_os.integrations.public_api_client import PublicAPIClient
from career_os.integrations.public_job_apis import AdzunaAdapter, ArbeitnowAdapter, OpenSkillsAdapter
from career_os.models.job import SourceType


class FakeClient:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.urls = []

    def get_json(self, url, **_kwargs):
        self.urls.append(url)
        return self.payloads.pop(0)


def test_adzuna_normalizes_job_and_salary_metadata():
    client = FakeClient([{
        "results": [{
            "id": "123",
            "title": "Production Support Engineer",
            "company": {"display_name": "Acme"},
            "location": {"display_name": "Hyderabad"},
            "description": "Support production applications.",
            "redirect_url": "https://example.com/apply/123",
            "created": "2026-08-25T10:00:00Z",
            "salary_min": 900000,
            "salary_max": 1300000,
            "salary_is_predicted": False,
            "contract_time": "full_time",
            "contract_type": "permanent",
            "category": {"label": "IT Jobs"},
        }]
    }])
    jobs = AdzunaAdapter("id", "key", client=client).fetch(query="support", country="in")
    assert jobs[0].company == "Acme"
    assert jobs[0].salary_currency == "INR"
    assert jobs[0].salary_min == 900000
    assert jobs[0].employment_type == "full_time / permanent"
    assert "app_id=id" in client.urls[0]


def test_arbeitnow_filters_remote_jobs_locally():
    client = FakeClient([{
        "data": [
            {"slug": "one", "company_name": "Acme", "title": "Support Engineer", "description": "Python support", "remote": True, "url": "https://arbeitnow.com/one", "tags": ["IT"], "location": "Remote", "created_at": 1787000000},
            {"slug": "two", "company_name": "Other", "title": "Designer", "description": "Design", "remote": False, "url": "https://arbeitnow.com/two", "tags": ["Design"], "location": "Berlin", "created_at": 1787000000},
        ],
        "links": {"next": None},
    }])
    jobs = ArbeitnowAdapter(client=client).fetch(query="support", remote_only=True)
    assert [job.external_id for job in jobs] == ["one"]
    assert jobs[0].remote is True


def test_open_skills_requires_explicit_http_opt_in():
    with pytest.raises(ValueError):
        OpenSkillsAdapter()


def test_open_skills_enrichment_is_deterministic_with_fixture():
    client = FakeClient([
        [{"title": "application support engineer", "description": "application support engineer", "parent_uuid": "job-1"}],
        [{"skill_name": "SQL"}, {"skill_name": "Linux"}, {"skill_name": "SQL"}],
    ])
    result = OpenSkillsAdapter(client=client, base_url="https://skills.example.test/v1").enrich_title("support engineer")
    assert result.canonical_title == "application support engineer"
    assert result.job_uuid == "job-1"
    assert result.skills == ("SQL", "Linux")


def test_public_job_scout_uses_job_board_source_type():
    jobs = ArbeitnowAdapter(client=FakeClient([{"data": [{
        "slug": "one", "company_name": "Acme", "title": "Support Engineer", "description": "Support", "url": "https://example.com/one", "location": "Hyderabad", "created_at": 1787000000,
    }], "links": {"next": None}}])).fetch(query="support")
    record = PublicJobScout().ingest(jobs)[0]
    assert record.source_type is SourceType.JOB_BOARD
    assert record.external_id == "one"
    assert record.location == "Hyderabad"


def test_public_api_client_retries_retryable_http_errors():
    class Response:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def read(self):
            return json.dumps({"ok": True}).encode()

    calls = {"count": 0}

    def opener(*_args, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise HTTPError("https://example.test", 503, "busy", {}, BytesIO(b""))
        return Response()

    client = PublicAPIClient(opener=opener, sleeper=lambda _: None)
    assert client.get_json("https://example.test") == {"ok": True}
    assert calls["count"] == 2
