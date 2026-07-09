from __future__ import annotations


def test_domain_scan_cycle_is_bounded_and_report_generator_driven() -> None:
    from predator_mesh.v19.watchlist import DomainScanCycle

    report = DomainScanCycle().to_report()
    assert report["verdict"] == "PASS"
    assert report["background_daemon_started"] is False
    assert report["bounded_scan_count"] is True
