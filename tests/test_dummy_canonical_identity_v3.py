import os


def test_dummy_canonical_identity_v3():
    from archive.report_scripts.generate_v7_reports import generate_dummy_canonical_identity_report_v3
    report = generate_dummy_canonical_identity_report_v3()
    assert report["project"] == "Dummy"
    assert report["previous_name"] == "Dumby"
    assert report["active_root"] == "C:\\src\\engine\\dummy"
    assert report["old_root_absent"] is True
    assert report["pyproject_name"] == "dummy"
    assert report["milestone"] == "DUMMY_V7_HYBRID_ROUTING_DESIGN_V1"
    assert report["verdict"] == "PASS"


def test_dummy_canonical_identity_no_secret_leak():
    from archive.report_scripts.generate_v7_reports import generate_dummy_canonical_identity_report_v3
    report = generate_dummy_canonical_identity_report_v3()
    text = str(report)
    key_id = os.environ.get("KALSHI_API_KEY_ID", "")
    if key_id:
        assert key_id not in text
