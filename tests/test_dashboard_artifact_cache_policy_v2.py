from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_dashboard_artifact_cache_policy_v2_prevents_repeated_live_calls() -> None:
    report = assert_v20_report("dashboard_artifact_cache_policy_v2_report.json", "dashboard_tests_use_cached_artifacts")
    assert report["dashboard_repeated_live_calls"] is False

