from tests.v25_test_helpers import assert_current_test_report


def test_v25_security_report_uses_actual_artifact_proof_path() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
    assert report["proof_path"].endswith("no_secret_leak_report_v25.json")
