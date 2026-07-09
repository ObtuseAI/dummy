from __future__ import annotations

from tests.v41_test_helpers import assert_current_test_report, v41_enabled_reports


def test_freshness_and_dedupe_gate_v1_blocks_inflation() -> None:
    report = assert_current_test_report(__file__)
    assert "source_family" in report["dedupe_keys"]
    assert report["duplicate_evidence_inflated_sample_count"] is False
    enabled = v41_enabled_reports()["freshness_and_dedupe_gate_v1_report.json"]
    assert enabled["v41_duplicate_stale_excluded_count"] == 0
    assert enabled["fresh_live_public_gate_required"] is True
