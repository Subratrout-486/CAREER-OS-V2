from pathlib import Path

from career_os.automation.job_processor import AutomaticJobProcessor, JobProcessingRequest, _candidate_inputs


def test_candidate_source_of_truth_builds_evidence_backed_resume_inputs():
    resume, claims = _candidate_inputs(Path("candidate/source_of_truth.json"))
    assert resume.summary
    assert resume.bullets
    assert claims
    assert set(resume.bullets[0].evidence_claim_ids) == {claims[0].claim_id}


def test_job_processor_invokes_pipeline(monkeypatch, tmp_path):
    calls = {}

    class FakeCheckpoint:
        pass

    class FakePipeline:
        def __init__(self, checkpoint):
            calls["checkpoint"] = checkpoint

        def run(self, **kwargs):
            calls.update(kwargs)
            return FakeCheckpoint()

    monkeypatch.setattr("career_os.automation.job_processor.CareerPipeline", FakePipeline)
    processor = AutomaticJobProcessor(
        candidate_path=Path("candidate/source_of_truth.json"),
        checkpoint_root=tmp_path,
    )
    job = {"company": "Example", "title": "Support Engineer", "url": "https://example.com/job/1", "description": "SQL and Linux production support"}

    result = processor.process(JobProcessingRequest(job=job))

    assert isinstance(result, FakeCheckpoint)
    assert calls["run_id"]
    assert calls["raw_job"] == job
    assert calls["resume"].summary
    assert calls["claims"]
    assert calls["checkpoint"].parent == tmp_path
