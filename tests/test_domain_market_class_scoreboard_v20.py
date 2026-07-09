from __future__ import annotations

from tests.v35_test_helpers import assert_current_test_report


def test_domain_market_class_scoreboard_v20_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["domain_market_class_scoreboard_v20_status"] == "PASS_PARTIAL_EXPECTED"
    assert report["frontend_build_scoreboard_status"] == "PASS"
    assert len(report["rows"]) == 4
    for row in report["rows"]:
        assert row["evidence_mode"] == "FAKE_TRANSPORT_TEST"
        assert row["live_public_eligible"] is False
        assert row["low_sample_status"] == "PIPELINE_SCORE_ONLY"
    assert report["execution_bridge_present"] is False
