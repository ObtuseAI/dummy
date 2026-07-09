from __future__ import annotations

from tests.v41_test_helpers import assert_current_test_report, v41_enabled_reports


def test_expanded_real_evidence_ledger_v2_counts_live_public_only() -> None:
    report = assert_current_test_report(__file__)
    assert report["eligible_evidence_mode"] == "LIVE_PUBLIC_PROBE_RESULT"
    assert report["fixture_evidence_entered"] is False
    enabled = v41_enabled_reports()["expanded_real_evidence_ledger_v2_report.json"]
    assert enabled["v41_new_evidence_count"] >= 6
    assert enabled["cumulative_evidence_count"] >= 12
