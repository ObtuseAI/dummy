from __future__ import annotations

from scripts.generate_v13_reports import generate_v12_liquidity_replay_status_report_v13


def test_v12_liquidity_replay_still_passes_or_partial_expected_v13() -> None:
    report = generate_v12_liquidity_replay_status_report_v13()

    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report["partial_expected"] in {True, False}
