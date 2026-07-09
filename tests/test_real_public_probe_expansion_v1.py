from __future__ import annotations

from tests.v40_test_helpers import assert_current_test_report, v40_enabled_reports


def test_real_public_probe_expansion_v1_default_has_no_network() -> None:
    report = assert_current_test_report(__file__)
    assert report["real_public_probe_expansion_status"] == "PARTIAL_BLOCKED_MISSING_EXACT_GATE"
    assert report["v40_new_real_probe_count"] == 0
    assert report["sports_excluded"] is True
    assert report["sports_source_activated"] is False


def test_real_public_probe_expansion_v1_enabled_is_bounded() -> None:
    report = v40_enabled_reports()["real_public_probe_expansion_v1_report.json"]
    assert report["real_public_probe_expansion_status"] == "PASS_REAL_PUBLIC_PROBE_EXPANSION"
    assert 0 < report["v40_new_real_probe_count"] <= report["max_total_requests"]
    assert report["max_total_requests"] <= 5
    assert report["kalshi_blocks_other_public_families"] is False
