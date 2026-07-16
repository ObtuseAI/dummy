from __future__ import annotations

from tests.v39_test_helpers import assert_current_test_report, v39_enabled_reports


def test_readonly_live_intelligence_completion_v2() -> None:
    report = assert_current_test_report(__file__)
    assert report["readonly_live_intelligence_status"] == "PARTIAL_BLOCKED_MISSING_EXACT_GATE"


def test_readonly_live_intelligence_enabled_path_passes() -> None:
    report = v39_enabled_reports()["readonly_live_intelligence_completion_v2_report.json"]
    assert report["readonly_live_intelligence_status"] == "PASS_READONLY_LIVE_INTELLIGENCE"
    assert report["real_probe_run_count"] > 0
    assert report["real_evidence_count"] > 0
