from __future__ import annotations

from tests.v16_test_helpers import real_snapshot


def test_readonly_only_kalshi_terrain_v16_report_passes() -> None:
    from scripts.generate_v16_reports import generate_readonly_only_kalshi_terrain_report_v16

    report = generate_readonly_only_kalshi_terrain_report_v16(real_snapshot())

    assert report["read_only_only"] is True
    assert report["verdict"] == "PASS"
