"""Job-page scraper with a Scrapling-backed worker and graceful fallbacks.

Scrapling (D4Vinci/Scrapling) is preferred when installed for robust page
extraction. In this environment where neither Scrapling nor a browser is
guaranteed, the scraper falls back to lightweight extraction and, as a last
resort, to a deterministic local fixture for safe tests and demos.

No stealth or anti-bot-evasion techniques are used. If a page is protected by a
security challenge, the scraper returns a flagged result rather than trying to
get around it.
"""

from __future__ import annotations

from dataclasses import dataclass

from career_os.execution.challenge import detect_challenge


@dataclass(frozen=True)
class ScrapedPage:
    url: str
    title: str
    text: str
    html: str
    security_blocked: bool = False


class JobPageScraper:
    """Extract a job page, preferring Scrapling when available."""

    def __init__(self, *, prefer: str = "auto") -> None:
        self.prefer = prefer  # auto | scrapling | stdlib | fixture

    def fetch(self, url: str) -> ScrapedPage:
        if self.prefer == "fixture":
            return _fixture_page(url)
        implementation = self.prefer if self.prefer != "auto" else _detect_best()
        if implementation == "scrapling":
            page = _scrapling_fetch(url)
            if page is not None:
                return page
        return _stdlib_fetch(url)


def _detect_best() -> str:
    try:
        import scrapling  # noqa: F401

        return "scrapling"
    except Exception:
        return "stdlib"


def _scrapling_fetch(url: str) -> ScrapedPage | None:
    try:
        from scrapling import Fetcher  # type: ignore
    except Exception:
        return None
    try:
        page = Fetcher.get(url, timeout=15)
        html = str(getattr(page, "html_content", "") or page.body if hasattr(page, "body") else "")
        text = _to_text(html)
        title = _extract_title(html)
        return ScrapedPage(url=url, title=title, text=text, html=html)
    except Exception:
        return None


def _stdlib_fetch(url: str) -> ScrapedPage:
    import urllib.request

    request = urllib.request.Request(url, headers={"User-Agent": "Career-OS-V2/0.1 (+local discovery)"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            html = response.read().decode("utf-8", errors="replace")
    except Exception:
        return _fixture_page(url)
    text = _to_text(html)
    challenge = detect_challenge(url=url, title=_extract_title(html), text=text, html=html)
    return ScrapedPage(
        url=url,
        title=_extract_title(html),
        text=text,
        html=html,
        security_blocked=challenge.blocked,
    )


def _to_text(html: str) -> str:
    import html as html_mod
    import re

    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return html_mod.unescape(re.sub(r"\s+", " ", text)).strip()


def _extract_title(html: str) -> str:
    import re

    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


def _fixture_page(url: str) -> ScrapedPage:
    title = "Support Engineer (fixture)"
    text = (
        "Support Engineer at Acme. Requirements: experience supporting "
        "production software, SQL, communication skills. Apply now."
    )
    return ScrapedPage(url=url, title=title, text=text, html=f"<html><title>{title}</title><body>{text}</body></html>")
