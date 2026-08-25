from career_os.job_sources.public_ats import ATSJobSource, _ashby_jobs, _greenhouse_jobs, _lever_jobs


def test_greenhouse_adapter_normalizes_job():
    jobs = _greenhouse_jobs({"jobs": [{"title": "Support Engineer", "location": {"name": "Hyderabad"}, "absolute_url": "https://example.com/job/1", "content": "SQL and Linux", "updated_at": "2026-08-25T00:00:00Z"}]}, ATSJobSource("greenhouse", "example"))
    assert jobs[0]["title"] == "Support Engineer"
    assert jobs[0]["location"] == "Hyderabad"
    assert jobs[0]["source"] == "greenhouse"


def test_ashby_adapter_uses_public_job_url():
    jobs = _ashby_jobs({"jobPostings": [{"title": "Product Support Analyst", "locationNames": ["Hyderabad", "Remote"], "jobUrl": "https://jobs.example.com/1", "descriptionPlain": "Oracle SQL"}]}, ATSJobSource("ashby", "example"))
    assert jobs[0]["url"] == "https://jobs.example.com/1"
    assert jobs[0]["location"] == "Hyderabad, Remote"


def test_lever_adapter_maps_categories():
    jobs = _lever_jobs([{ "text": "Application Support Engineer", "categories": {"location": "India"}, "hostedUrl": "https://jobs.example.com/1", "descriptionPlain": "Production support"}], ATSJobSource("lever", "example"))
    assert jobs[0]["title"] == "Application Support Engineer"
    assert jobs[0]["location"] == "India"


def test_endpoint_is_public_and_credential_free():
    assert ATSJobSource("greenhouse", "example").endpoint().startswith("https://boards-api.greenhouse.io/")
    assert ATSJobSource("ashby", "example").endpoint().startswith("https://api.ashbyhq.com/")
    assert ATSJobSource("lever", "example").endpoint().startswith("https://api.lever.co/")
