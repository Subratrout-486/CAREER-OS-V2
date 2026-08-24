#!/usr/bin/env python3
"""Read job-opportunity emails from Gmail and create deduplicated Career OS Notion jobs.

Uses Gmail OAuth refresh tokens directly (no third-party service) and the existing
Notion Jobs data source as the canonical queue. It is intentionally read-only on
Gmail: messages are never marked read, moved, labelled, or deleted.
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

NOTION_VERSION = os.environ.get("NOTION_VERSION", "2026-03-11")
DEFAULT_DATA_SOURCE_ID = "8374c380-f148-41ab-a77f-eb35de20f2db"
MAX_MESSAGES = max(1, int(os.environ.get("CAREER_OS_GMAIL_MAX_MESSAGES", "25")))
QUERY = os.environ.get(
    "CAREER_OS_GMAIL_QUERY",
    'newer_than:2d {job jobs hiring recruiter careers "technical support" "application support" "software support"}',
)
REPORT_PATH = ".career-os/gmail-intake-report.json"

JOB_TERMS = re.compile(
    r"\b(job|jobs|hiring|vacancy|career|careers|role|position|recruiter|technical support|application support|software support|analyst|engineer|developer|associate)\b",
    re.I,
)
EXCLUDE_TERMS = re.compile(
    r"\b(application received|application submitted|thank you for applying|we received your application|interview scheduled|interview invitation|application status|unfortunately|not selected|rejected|withdrawn)\b",
    re.I,
)
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
TITLE_RE = re.compile(r"(?i)(?:position|role|job|opening|opportunity)\s*[:\-–—]\s*([^|\n]{3,120})")


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return re.sub(r"\s+", " ", html.unescape(" ".join(self.parts))).strip()


def _request_json(url: str, *, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
    req = Request(url, method=method, data=body, headers=headers or {})
    with urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def gmail_access_token() -> str:
    client_id = os.environ.get("GMAIL_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GMAIL_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("GMAIL_REFRESH_TOKEN", "").strip()
    if not all((client_id, client_secret, refresh_token)):
        raise RuntimeError("Gmail intake disabled: GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET and GMAIL_REFRESH_TOKEN are required")
    payload = urlencode({"client_id": client_id, "client_secret": client_secret, "refresh_token": refresh_token, "grant_type": "refresh_token"}).encode()
    response = _request_json("https://oauth2.googleapis.com/token", method="POST", body=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
    token = str(response.get("access_token", ""))
    if not token:
        raise RuntimeError("Gmail OAuth refresh did not return an access token")
    return token


def gmail_api(path: str, token: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    url = "https://gmail.googleapis.com/gmail/v1/users/me/" + path
    if params:
        url += "?" + urlencode(params)
    return _request_json(url, headers={"Authorization": f"Bearer {token}"})


def _decode_b64url(value: str) -> str:
    if not value:
        return ""
    raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    return raw.decode("utf-8", errors="replace")


def _collect_parts(part: dict[str, Any], texts: list[str]) -> None:
    mime = part.get("mimeType", "")
    data = (part.get("body", {}) or {}).get("data")
    if data and mime in {"text/plain", "text/html"}:
        decoded = _decode_b64url(data)
        if mime == "text/html":
            parser = _HTMLText()
            parser.feed(decoded)
            decoded = parser.text()
        texts.append(decoded)
    for child in part.get("parts", []) or []:
        _collect_parts(child, texts)


def message_text(message: dict[str, Any]) -> tuple[dict[str, str], str]:
    headers = {h.get("name", "").lower(): h.get("value", "") for h in (message.get("payload", {}) or {}).get("headers", [])}
    texts: list[str] = []
    _collect_parts(message.get("payload", {}) or {}, texts)
    return headers, ("\n".join(x for x in texts if x).strip() or str(message.get("snippet", "")))


def extract_url(text: str) -> str:
    urls = [u.rstrip(".,);]>") for u in URL_RE.findall(text)]
    preferred = [u for u in urls if not re.search(r"(unsubscribe|privacy|google|facebook|linkedin\.com/help)", u, re.I)]
    return (preferred or urls)[0] if (preferred or urls) else ""


def extract_title(subject: str, body: str) -> str:
    match = TITLE_RE.search(subject + "\n" + body[:3000])
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip(" -–—|")[:150]
    clean = re.sub(r"\s+", " ", subject).strip()
    for prefix in ("Job Alert:", "New Job:", "Jobs:", "Hiring:", "Career Opportunity:"):
        if clean.lower().startswith(prefix.lower()):
            clean = clean[len(prefix):].strip()
            break
    return clean[:150] or "Gmail Job Opportunity"


def extract_company(headers: dict[str, str], subject: str, body: str) -> str:
    sender = headers.get("from", "")
    domain = re.search(r"@([A-Za-z0-9.-]+)", sender)
    if domain:
        host = domain.group(1).lower()
        if host not in {"gmail.com", "outlook.com", "hotmail.com", "yahoo.com"}:
            return host.split(".")[0].replace("-", " ").title()
    for pattern in (r"(?i)company\s*[:\-]\s*([^|\n]{2,100})", r"(?i)at\s+([A-Z][A-Za-z0-9&.\- ]{2,60})"):
        match = re.search(pattern, subject + "\n" + body[:2000])
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip(" .,-")[:100]
    return "Unknown Employer"


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().casefold()


def notion_request(path: str, token: str, *, method: str = "GET", body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = None if body is None else json.dumps(body).encode()
    headers = {"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION, "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Career-OS-V2-Gmail-Intake/1.0"}
    return _request_json("https://api.notion.com/v1" + path, method=method, body=payload, headers=headers)


def schema(token: str, data_source_id: str) -> dict[str, dict[str, Any]]:
    response = notion_request(f"/data_sources/{data_source_id.replace('-', '')}", token)
    return response.get("properties", {}) or {}


def find_prop(props: dict[str, dict[str, Any]], name: str) -> tuple[str, dict[str, Any]] | None:
    wanted = normalize(name)
    for key, value in props.items():
        if normalize(key) == wanted:
            return key, value
    return None


def value_for(prop_type: str, value: Any) -> dict[str, Any] | None:
    if prop_type == "title":
        return {"title": [{"type": "text", "text": {"content": str(value)[:1900]}}]}
    if prop_type == "rich_text":
        return {"rich_text": [{"type": "text", "text": {"content": str(value)[:1900]}}]} if value else {"rich_text": []}
    if prop_type == "url":
        return {"url": value or None}
    if prop_type == "number":
        return {"number": float(value) if value is not None else None}
    return None


def select_value(definition: dict[str, Any], preferred: list[str]) -> str | None:
    kind = definition.get("type")
    if kind not in {"select", "status"}:
        return None
    options = (definition.get(kind) or {}).get("options", [])
    names = {normalize(o.get("name", "")): o.get("name", "") for o in options}
    for item in preferred:
        if normalize(item) in names:
            return names[normalize(item)]
    return None


def build_properties(props: dict[str, dict[str, Any]], *, title: str, company: str, body: str, url: str, source: str, gmail_id: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    title_prop = next(((name, definition) for name, definition in props.items() if definition.get("type") == "title"), None)
    if not title_prop:
        raise RuntimeError("Notion Jobs data source has no title property")
    payload[title_prop[0]] = value_for("title", title)
    for wanted, value in {"Company": company, "JD": body, "Job URL": url, "Source": source, "Gmail Message ID": gmail_id}.items():
        found = find_prop(props, wanted)
        if found and value:
            name, definition = found
            encoded = value_for(definition.get("type", ""), value)
            if encoded is not None:
                payload[name] = encoded
    for wanted, preferred in {"Status": ["Discovered", "New", "Review Required"], "Processing Stage": ["Discovered"], "Resume Status": ["Not Started", "Pending"]}.items():
        found = find_prop(props, wanted)
        if found:
            name, definition = found
            selected = select_value(definition, preferred)
            if selected:
                payload[name] = {definition.get("type"): {"name": selected}}
    return payload


def existing_keys(token: str, data_source_id: str, props: dict[str, dict[str, Any]]) -> set[str]:
    response = notion_request(f"/data_sources/{data_source_id.replace('-', '')}/query", token, method="POST", body={"page_size": 100})
    keys: set[str] = set()
    for page in response.get("results", []):
        values = page.get("properties", {})
        for wanted in ("Job URL", "Gmail Message ID"):
            found = find_prop(props, wanted)
            if not found:
                continue
            name, _ = found
            value_obj = values.get(name, {})
            kind = value_obj.get("type")
            value = value_obj.get(kind)
            if kind == "url":
                value = value or ""
            elif kind == "rich_text":
                value = "".join(x.get("plain_text", "") for x in (value or []))
            if value:
                keys.add(normalize(str(value)))
    return keys


def create_page(token: str, data_source_id: str, properties: dict[str, Any], body: str) -> str:
    children = [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": body[:1900]}}]}}]
    response = notion_request("/pages", token, method="POST", body={"parent": {"data_source_id": data_source_id}, "properties": properties, "children": children})
    return str(response.get("id", ""))


def process_message(token: str, data_source_id: str, props: dict[str, dict[str, Any]], message: dict[str, Any], known: set[str]) -> tuple[str, str]:
    message_id = str(message.get("id", ""))
    headers, body = message_text(message)
    subject = headers.get("subject", "").strip()
    combined = f"{subject}\n{body[:10000]}"
    if not JOB_TERMS.search(combined) or EXCLUDE_TERMS.search(combined):
        return "skipped", "not a likely job opportunity"
    url = extract_url(combined)
    fingerprint = normalize(url) if url else hashlib.sha256(normalize(subject + "\n" + body[:1000]).encode()).hexdigest()
    if fingerprint in known or normalize(message_id) in known:
        return "duplicates", "already present in Career OS"
    title = extract_title(subject, body)
    company = extract_company(headers, subject, body)
    properties = build_properties(props, title=title, company=company, body=combined, url=url, source="Gmail", gmail_id=message_id)
    page_id = create_page(token, data_source_id, properties, combined)
    if not page_id:
        raise RuntimeError("Notion page creation returned no page id")
    known.add(fingerprint)
    known.add(normalize(message_id))
    return "created", f"{company} — {title}"


def main() -> int:
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    report: dict[str, Any] = {"ok": True, "enabled": False, "messages_seen": 0, "created": 0, "duplicates": 0, "skipped": 0, "failures": 0, "results": []}
    if not all(os.environ.get(k, "").strip() for k in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN")):
        report["message"] = "Gmail intake not configured; no action taken."
        with open(REPORT_PATH, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        print(report["message"])
        return 0
    try:
        gmail_token = gmail_access_token()
        notion_token = os.environ.get("NOTION_TOKEN", "").strip()
        if not notion_token:
            raise RuntimeError("NOTION_TOKEN is required for Gmail → Notion intake")
        data_source_id = os.environ.get("NOTION_DATA_SOURCE_ID", DEFAULT_DATA_SOURCE_ID)
        props = schema(notion_token, data_source_id)
        known = existing_keys(notion_token, data_source_id, props)
        listing = gmail_api("messages", gmail_token, {"maxResults": str(MAX_MESSAGES), "q": QUERY})
        messages = listing.get("messages", []) or []
        report["enabled"] = True
        report["messages_seen"] = len(messages)
        for stub in messages:
            try:
                message = gmail_api(f"messages/{stub['id']}", gmail_token, {"format": "full"})
                outcome, detail = process_message(gmail_token, data_source_id, props, message, known)
                report[outcome] = report.get(outcome, 0) + 1
                report["results"].append({"message_id": stub["id"], "outcome": outcome, "detail": detail})
            except Exception as exc:
                report["failures"] += 1
                report["ok"] = False
                report["results"].append({"message_id": stub.get("id"), "outcome": "failure", "detail": f"{type(exc).__name__}: {exc}"[:500]})
        print(f"Gmail intake: {report['created']} created, {report['duplicates']} duplicates, {report['skipped']} skipped, {report['failures']} failures")
    except Exception as exc:
        report["ok"] = False
        report["error"] = f"{type(exc).__name__}: {exc}"[:1200]
        print(f"GMAIL_INTAKE_SYSTEM_ERROR: {report['error']}")
    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
