from __future__ import annotations

from tests.v39_test_helpers import assert_current_test_report, v39_enabled_reports


def test_v38_exact_gated_rerun_adapter_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["v38_rerun_command"] == "python scripts/generate_v38_reports.py"
    assert report["v38_rerun_executed"] is False
    assert report["v38_rerun_blocker"] == "MISSING_EXACT_OPERATOR_GATE"


def test_v38_rerun_readback_counts_enabled_path() -> None:
    report = v39_enabled_reports()["v38_exact_gated_rerun_adapter_v1_report.json"]
    assert report["v38_rerun_executed"] is True
    assert report["v38_readback"]["real_probe_run_count"] > 0
    assert report["v38_readback"]["real_evidence_count"] > 0
    assert report["v38_readback"]["real_scored_count"] > 0
