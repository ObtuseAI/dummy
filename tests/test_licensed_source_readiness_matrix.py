from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_licensed_source_readiness_matrix_is_all_blocked_by_default() -> None:
    report = assert_v20_report("licensed_source_readiness_matrix_v1.json", "readiness")
    assert report["ready_count"] == 0
    assert report["blocked_license_required_count"] == report["source_count"]
