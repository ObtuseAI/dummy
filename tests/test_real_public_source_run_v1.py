from __future__ import annotations

from tests.v39_test_helpers import assert_current_test_report, v39_enabled_reports


def test_real_public_source_run_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["real_public_source_run_status"] == "PARTIAL_BLOCKED_MISSING_EXACT_GATE"
    assert report["sports_excluded"] is True
    assert report["max_total_requests"] <= 4
    assert report["real_probe_run_count"] == 0


def test_real_public_source_run_enabled_path_attempts_public_families() -> None:
    report = v39_enabled_reports()["real_public_source_run_v1_report.json"]
    assert report["real_public_source_run_status"] == "PASS_REAL_PUBLIC_SOURCE_RUN"
    assert report["real_probe_run_count"] > 0
    assert set(["weather", "crypto", "public_event", "kalshi_readonly"]).issubset(set(report["source_families"]))
    assert report["kalshi_readonly_status"] == "READONLY_ACCESS_UNAVAILABLE"

