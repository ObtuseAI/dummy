from __future__ import annotations


def test_settlement_status_probe_has_bounded_readonly_timeouts() -> None:
    from predator_mesh.v17.observer import SettlementStatusProbe

    report = SettlementStatusProbe().to_report()

    assert report["max_request_timeout_s"] <= 10
    assert report["total_timeout_s"] <= 45
    assert report["read_only_only"] is True
