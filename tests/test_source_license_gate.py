from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_source_license_gate_blocks_licensed_sources_without_allowlist() -> None:
    report = assert_v20_report("source_license_gate_report_v1.json", "licensed_sources")
    assert report["licensed_source_count"] > 0
    assert report["activated_licensed_sources"] == []

