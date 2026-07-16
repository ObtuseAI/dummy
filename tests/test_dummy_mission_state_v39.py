from __future__ import annotations

from tests.v39_test_helpers import assert_current_test_report, v39_enabled_reports


def test_dummy_mission_state_v39() -> None:
    report = assert_current_test_report(__file__)
    assert report["mission_state_verdict"] == "PARTIAL"
    assert report["v38_carried_status"] in {"PASS", "PARTIAL", "PASS_OR_PARTIAL_EXPECTED"}
    assert report["current_next_action"] == "OPERATOR_SET_EXACT_PUBLIC_PROBE_GATE"


def test_dummy_mission_state_v39_enabled_path_passes_milestones() -> None:
    report = v39_enabled_reports()["dummy_mission_state_report_v25.json"]
    assert report["readonly_live_intelligence_status"] == "PASS_READONLY_LIVE_INTELLIGENCE"
    assert report["first_live_score_milestone_status"] == "PASS_FIRST_REAL_LIVE_PUBLIC_SCORE"
    assert report["real_scored_count"] > 0
