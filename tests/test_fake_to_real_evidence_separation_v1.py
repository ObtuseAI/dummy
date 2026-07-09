from __future__ import annotations

from tests.v36_test_helpers import assert_current_test_report


def test_fake_to_real_evidence_separation_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["separation_enforced"] is True
    assert report["execution_bridge_present"] is False
