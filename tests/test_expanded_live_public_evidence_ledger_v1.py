from __future__ import annotations

from tests.v40_test_helpers import assert_current_test_report, v40_enabled_reports


def test_expanded_live_public_evidence_ledger_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["evidence_mode_required"] == "LIVE_PUBLIC_PROBE_RESULT"
    assert report["fake_transport_evidence_entered"] is False
    assert report["fixture_evidence_entered"] is False
    assert report["cumulative_evidence_count"] >= report["baseline_real_evidence_count"]


def test_expanded_live_public_evidence_ledger_v1_enabled_counts_new_evidence() -> None:
    report = v40_enabled_reports()["expanded_live_public_evidence_ledger_v1_report.json"]
    assert report["expanded_live_public_evidence_status"] == "PASS_EXPANDED_LIVE_PUBLIC_EVIDENCE"
    assert report["v40_new_evidence_count"] > 0
    assert report["dedupe_keys"] == ["source_family", "source_name", "metric", "timestamp_window", "market_class"]
