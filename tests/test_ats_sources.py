from career_os.agents.ats_sources import ATSClient


def test_detect_known_public_ats_board_urls():
    assert ATSClient.detect("https://boards.greenhouse.io/acme") == ("greenhouse", "acme")
    assert ATSClient.detect("https://jobs.lever.co/acme") == ("lever", "acme")
    assert ATSClient.detect("https://jobs.ashbyhq.com/acme") == ("ashby", "acme")


def test_detect_unknown_source():
    assert ATSClient.detect("https://careers.example.com/jobs/123") is None
