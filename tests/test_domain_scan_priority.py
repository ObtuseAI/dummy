from __future__ import annotations


def test_domain_scan_priority_contains_v19_priority_lanes() -> None:
    from predator_mesh.v19.watchlist import DomainScanPriority

    report = DomainScanPriority.report()
    assert report["verdict"] == "PASS"
    assert "settlement_clarity" in report["priorities"]
    assert "source_promotion_review" in report["priorities"]
