from scripts import gmail_job_intake as module


def test_extract_url_prefers_html_application_href_over_earlier_body_url():
    message = {
        "payload": {
            "headers": [],
            "mimeType": "text/html",
            "body": {
                "data": "PGh0bWw+PGJvZHk+Q29tcGFueTogaHR0cHM6Ly9leGFtcGxlLmNvbS90cmFja2luZyA8YSBocmVmPSdodHRwczovL2NhcmVlcnMuZXhhbXBsZS5jb20vam9icy80NTYnPkFwcGx5PC9hPjwvYm9keT48L2h0bWw+"
            },
        }
    }
    _, body = module.message_text(message)
    assert module.extract_url(body) == "https://careers.example.com/jobs/456"


def test_extract_url_excludes_linkedin_help_urls():
    text = "https://www.linkedin.com/help/linkedin/answer/1 https://careers.example.com/jobs/789"
    assert module.extract_url(text) == "https://careers.example.com/jobs/789"
