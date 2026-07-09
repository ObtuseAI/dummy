from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_source_tier_matrix_report_covers_tiers_by_domain() -> None:
    report = assert_v20_report("source_tier_matrix_v1.json", "matrix", "tiers")
    assert "nasdaq_index_direction" in report["matrix"]
    assert report["tier_0_exchange_native_prioritized"] is True

