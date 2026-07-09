import os


def test_dummy_canonical_identity_v4():
    from scripts.generate_v8_identity_reports import generate_dummy_canonical_identity_report_v4

    report = generate_dummy_canonical_identity_report_v4()
    assert report["project"] == "Dummy"
    assert report["previous_name"] == "Dumby"
    assert report["active_root"] == "C:\\src\\engine\\dummy"
    assert report["old_root_absent"] is True
    assert report["pyproject_name"] == "dummy"
    assert report["readme_says_dummy"] is True
    assert report["old_root_runtime_refs"] == []
    assert report["verdict"] == "PASS"


def test_dummy_canonical_identity_no_secret_leak():
    from scripts.generate_v8_identity_reports import generate_dummy_canonical_identity_report_v4

    report = generate_dummy_canonical_identity_report_v4()
    text = str(report)
    key_id = os.environ.get("KALSHI_API_KEY_ID", "")
    if key_id:
        assert key_id not in text
