from __future__ import annotations

from tests.v36_test_helpers import assert_current_test_report


def test_real_probe_artifact_cache_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["redaction_audit_passed"] is True
    assert report["no_promotion"] is True
    assert report["execution_bridge_present"] is False
