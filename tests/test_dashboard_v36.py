from __future__ import annotations

from tests.v36_test_helpers import assert_current_test_report


def test_dashboard_v36() -> None:
    report = assert_current_test_report(__file__)
    assert "routes" in report
    assert report["cache_policy"] == "artifact-backed deterministic report slices"
    assert report["execution_bridge_present"] is False
