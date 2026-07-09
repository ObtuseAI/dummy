from __future__ import annotations

from tests.v35_test_helpers import assert_current_test_report


def test_sports_fixture_only_reverification_v6_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["sports_mode"] == "FIXTURE_REPLAY_ONLY"
    assert report["no_betting_source_activation"] is True
    assert report["no_fixture_evidence_scored_live"] is True
    assert report["execution_bridge_present"] is False


def test_sports_mode_check_v6_passes() -> None:
    from tests.v35_test_helpers import assert_v35_report_named

    report = assert_v35_report_named("sports_mode_check_v6_report.json")
    assert report["sports_mode_check_v6_status"] == "PASS"
