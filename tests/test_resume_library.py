from career_os.resume_library import build_resume_library_properties, next_version


def test_resume_library_properties_include_tailored_file_and_job_relation():
    properties = build_resume_library_properties(
        resume_name="Subrat_Rout_Product_Support_Engineer.pdf",
        status="Tailored",
        role_family="Product Support",
        version="v1",
        source="Official posting",
        claims_verified=True,
        notes="generated",
        ats_score=87.5,
        job_id="11111111-2222-3333-4444-555555555555",
        file_upload_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        filename="Subrat_Rout_Product_Support_Engineer.pdf",
    )

    assert properties["Status"] == {"select": {"name": "Tailored"}}
    assert properties["Claims Verified"] == {"checkbox": True}
    assert properties["ATS Score"] == {"number": 87.5}
    assert properties["Job"]["relation"][0]["id"] == "11111111-2222-3333-4444-555555555555"
    assert properties["File"]["files"][0]["type"] == "file_upload"
    assert properties["File"]["files"][0]["file_upload"]["id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_next_version_ignores_non_numeric_versions_and_increments_highest():
    assert next_version(["v1", "v3", "Master", "draft"]) == "v4"
    assert next_version([]) == "v1"


def test_resume_library_rejects_invalid_status():
    try:
        build_resume_library_properties(
            resume_name="x.pdf",
            status="Ready",
            role_family="Other",
            version="v1",
            source="Career OS",
            claims_verified=False,
        )
    except ValueError as exc:
        assert "Unsupported resume status" in str(exc)
    else:
        raise AssertionError("invalid Resume Library status was accepted")
