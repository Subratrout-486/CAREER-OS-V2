#!/usr/bin/env python3
"""Exercise the real Arachne HTTP boundary with a live public job."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from career_os.automation.job_processor import AutomaticJobProcessor
from career_os.integrations.ats import GreenhouseAdapter


def main() -> None:
    os.environ["CAREER_OS_CONDUCTOR_TOKEN"] = "arachne-live-smoke-token"
    jobs = GreenhouseAdapter().fetch("stripe")
    job = next((item for item in jobs if item.description and item.job_url), None)
    if job is None:
        raise SystemExit("No live Greenhouse job with description was returned")

    raw = {
        "company": job.company,
        "title": job.title,
        "location": job.location,
        "url": job.job_url,
        "source": job.provider,
        "description": job.description,
        "posted_at": job.posted_at,
    }

    with tempfile.TemporaryDirectory() as tmp:
        processor = AutomaticJobProcessor(
            candidate_path=Path("candidate/source_of_truth.json"),
            checkpoint_root=Path(tmp) / "checkpoints",
        )

        from career_os.arachne_api import create_arachne_router
        from career_os.arachne_store import ArachneResultStore
        from career_os.conductor_bridge import IdempotencyStore
        from fastapi import FastAPI

        smoke_app = FastAPI()
        smoke_app.include_router(
            create_arachne_router(
                processor_factory=lambda: processor,
                store=ArachneResultStore(Path(tmp) / "arachne"),
                idempotency_store=IdempotencyStore(str(Path(tmp) / "idempotency.json")),
            )
        )

        with TestClient(smoke_app) as client:
            headers = {"X-Career-OS-Token": "arachne-live-smoke-token"}
            health = client.get("/api/v1/health", headers=headers)
            assert health.status_code == 200, health.text
            assert health.json()["submission_enabled"] is False

            response = client.post(
                "/api/v1/jobs",
                headers=headers,
                json={"idempotency_key": "arachne-live-smoke-001", "job": raw},
            )
            assert response.status_code == 200, response.text
            body = response.json()
            result = body["result"]
            assert body["processing"] == "automatic"
            assert result["checkpoint"]["status"] == "completed"
            assert result["tailored_resume"]["summary"]
            assert result["tailored_resume"]["bullets"]
            assert result["application_mode"] == "REVIEW_ONLY"
            assert result["submission_enabled"] is False

            key = result["job"]["canonical_key"]
            fetched = client.get(f"/api/v1/jobs/{key}", headers=headers)
            assert fetched.status_code == 200, fetched.text
            assert fetched.json()["job"]["canonical_key"] == key
            assert fetched.json()["tailored_resume"]["summary"] == result["tailored_resume"]["summary"]

            listed = client.get("/api/v1/jobs", headers=headers)
            assert listed.status_code == 200, listed.text
            assert listed.json()["count"] == 1

    print(f"ARACHNE LIVE SMOKE OK: {job.company} / {job.title}")
    print(f"canonical key: {key}")
    print("automatic processing: verified")
    print("tailored resume: verified")
    print("read-after-write: verified")
    print("submission: disabled")


if __name__ == "__main__":
    main()
