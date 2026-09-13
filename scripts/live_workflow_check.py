"""Live end-to-end workflow verification for the ARACHNE release.

Two scenarios, both against a LOCAL HTTP form fixture (never a real employer):

Scenario A - truthful NEEDS_REVIEW
    The repo's real candidate/source_of_truth.json has no email/phone/work
    authorization. A form that requires those fields must be routed to
    NEEDS_REVIEW by dynamic form discovery - the engine never guesses.

Scenario B - verified submission via the real Chromium browser
    A complete fixture candidate profile (same values the test suite uses)
    lets dynamic discovery map every required control; the tailored resume is
    uploaded and the confirmation page / reference is verified, then persisted.
"""

from __future__ import annotations

import asyncio
import http.server
import json
import os
import socket
import tempfile
import threading
from pathlib import Path

os.environ.setdefault("CAREER_OS_ENABLE_BROWSER", "1")
os.environ.setdefault("APPLICATION_BROWSER_HEADLESS", "1")

REPO = Path(__file__).resolve().parent.parent
SOT_PATH = REPO / "candidate" / "source_of_truth.json"

FORM_HTML = """<!doctype html><html><head><title>Apply</title></head><body>
<form action="/apply" method="post">
  <label for="first">First name</label><input id="first" name="first_name" required>
  <label for="last">Last name</label><input id="last" name="last_name" required>
  <label for="mail">Email address</label><input id="mail" name="email" type="email" required>
  <label for="cv">Resume/CV</label><input id="cv" name="resume" type="file" required>
  <label for="wa">Work authorization</label>
  <select id="wa" name="work_authorization" required>
    <option>Select</option><option>Yes</option><option>No</option>
  </select>
  <label for="loc">Location</label><input id="loc" name="location" required>
  <input type="submit" value="Submit application">
</form></body></html>"""

CONFIRM_HTML = (
    "<html><head><title>Thanks</title></head><body>"
    "Your application has been submitted. Reference APP-4242"
    "</body></html>"
)

FIXTURE_PROFILE = {
    "first_name": "Subrat",
    "last_name": "Rout",
    "full_name": "Subrat Rout",
    "email": "subrat@example.com",
    "location": "Hyderabad, India",
    "candidate": {
        "name": "Subrat Rout",
        "location": "Hyderabad, India",
        "work_authorization": "Yes",
    },
}


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):  # noqa: N802
        body = FORM_HTML.encode() if self.path == "/apply" else CONFIRM_HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802
        body = CONFIRM_HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _fixture_material():
    """ResumeProfile + verified evidence claims used by the pipeline stages."""
    from career_os.models.evidence import EvidenceClaim, EvidenceKind, SupportStatus
    from career_os.models.resume import ResumeBullet, ResumeProfile

    profile = ResumeProfile(
        summary="Support engineer with Linux, AWS and Python automation experience.",
        bullets=(
            ResumeBullet("Supported production Linux systems for 3 years.", ("exp-1",)),
            ResumeBullet("Automated incident response with Python and AWS.", ("exp-2",)),
        ),
    )
    claims = [
        EvidenceClaim(
            claim_id="exp-1",
            claim="Worked as a support engineer maintaining Linux production systems.",
            kind=EvidenceKind.USER_PROVIDED,
            support=SupportStatus.SUPPORTED,
            confidence=0.9,
        ),
        EvidenceClaim(
            claim_id="exp-2",
            claim="Built Python automation for incident response on AWS.",
            kind=EvidenceKind.USER_PROVIDED,
            support=SupportStatus.SUPPORTED,
            confidence=0.9,
        ),
    ]
    return profile, claims


def _discovered(apply_url: str):
    from career_os.discovery.service import DiscoveryItem, JobDiscoveryService
    from career_os.integrations.ats import RawATSJob

    svc = JobDiscoveryService()
    raw = RawATSJob(
        provider="fixture",
        external_id="gh-4242",
        title="Support Engineer",
        company="Acme Fixtures",
        location="India",
        description=(
            "Acme Fixtures seeks a Support Engineer. Responsibilities include "
            "troubleshooting Linux systems, AWS infrastructure, Python-based "
            "automation, and incident management. Requires strong technical "
            "support and communication skills."
        ),
        job_url=apply_url,
        posted_at=None,
        raw={},
    )
    return svc.ingest([DiscoveryItem("fixture", raw)])


def _prepare(orchestrator, discovered, mutate=None):
    from career_os.execution.engine import ApplicationExecutor
    from career_os.execution.flow import build_application_plan
    from career_os.execution.runner import ApplicationBatchRunner
    from career_os.execution.state import ApplicationExecutionStateMachine

    executions = orchestrator.prepare(discovered)
    if mutate:
        for execution in executions:
            mutate(execution)
    machine = ApplicationExecutionStateMachine(orchestrator._store)
    runner = ApplicationBatchRunner(
        orchestrator._store,
        machine,
        executor=ApplicationExecutor(),
        plan_builder=build_application_plan,
    )
    approved = runner.approve_batch(executions)
    return runner, runner.queue_batch(approved)


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="career-os-live-"))
    store_root = root / "state"
    os.environ["CAREER_OS_EXECUTION_ROOT"] = str(store_root / "executions")
    os.environ["CAREER_OS_ARACHNE_ROOT"] = str(store_root / "arachne")

    port = free_port()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    apply_url = f"http://127.0.0.1:{port}/apply"

    from career_os.execution.state import ExecutionStatus, ExecutionStore
    from career_os.orchestration.e2e import EndToEndOrchestrator

    resume, claims = _fixture_material()

    # =====================================================================
    # Scenario A: real Source of Truth -> truthful NEEDS_REVIEW
    # =====================================================================
    print("--- Scenario A: real Source of Truth (truthfulness) ---")
    real_sot = json.loads(SOT_PATH.read_text(encoding="utf-8"))
    cand = json.dumps(real_sot["candidate"])
    print(f"    SOT has email/phone/work_auth: "
          f"{'email' in cand}/{ 'phone' in cand}/{ 'work_authorization' in cand}")
    store_a = ExecutionStore(store_root / "executions_a")
    orch_a = EndToEndOrchestrator(store=store_a, resume=resume, claims=claims)
    runner_a, queued_a = _prepare(orch_a, _discovered(apply_url))
    assert len(queued_a) == 1
    queued_a[0].pipeline["resume_path"] = str(root / "Subrat_Rout_Support_Engineer.pdf")
    Path(queued_a[0].pipeline["resume_path"]).write_bytes(b"%PDF-1.4 fixture artifact")
    outcome_a = asyncio.run(runner_a.execute_batch(queued_a))
    res_a = outcome_a.results[queued_a[0].execution_id]
    print(f"    outcome state    : {res_a.state}")
    print(f"    review reasons   : {res_a.details.get('review') or res_a.details}")
    assert res_a.state == "needs_review", "real SOT must never guess contact fields"
    saved_a = store_a.load(queued_a[0].execution_id)
    assert saved_a is not None
    assert saved_a.status == ExecutionStatus.NEEDS_REVIEW
    print(f"    persisted status : {saved_a.status}  => truthfulness OK\n")

    # =====================================================================
    # Scenario B: complete fixture profile -> verified submission (real browser)
    # =====================================================================
    print("--- Scenario B: complete profile -> verified submit (real browser) ---")
    store_b = ExecutionStore(store_root / "executions_b")
    orch_b = EndToEndOrchestrator(store=store_b, resume=resume, claims=claims)

    def _mutate_b(execution):
        execution.pipeline["fields"] = []
        execution.pipeline["profile"] = dict(FIXTURE_PROFILE)
        execution.pipeline["resume_path"] = str(root / "Subrat_Rout_Support_Engineer.pdf")
        Path(execution.pipeline["resume_path"]).write_bytes(b"%PDF-1.4 fixture artifact")

    runner_b, queued_b = _prepare(orch_b, _discovered(apply_url), mutate=_mutate_b)
    assert len(queued_b) == 1
    outcome_b = asyncio.run(runner_b.execute_batch(queued_b))
    res_b = outcome_b.results[queued_b[0].execution_id]
    print(f"    outcome state    : {res_b.state}")
    print(f"    evidence         : {list(res_b.evidence)}")
    assert res_b.submitted is True, res_b.details
    assert res_b.state == "submitted"
    saved_b = store_b.load(queued_b[0].execution_id)
    assert saved_b is not None
    assert saved_b.status == ExecutionStatus.SUBMISSION_VERIFIED, saved_b.status
    print(f"    persisted status : {saved_b.status}")
    print(f"    field discovery  : {len(res_b.details.get('field_discovery', []))} controls")
    print(f"    uploaded         : {res_b.details.get('uploaded', [])}")
    print(f"    filled           : {res_b.details.get('filled', [])}")
    evidence_text = (saved_b.execution or {}).get("submission_evidence", "")
    assert "APP-4242" in evidence_text
    print(f"    evidence saved   : {evidence_text[:90]}")
    assert "resume" in json.dumps(res_b.details)
    print("    resume upload    : OK")

    server.shutdown()
    print("\nWORKFLOW: OK  discovery->prepare->approve->browser-execute->verify->persist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())