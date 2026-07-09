from __future__ import annotations

from v19_test_helpers import DOMAINS


def test_domain_watchlist_tracks_scan_and_forecast_readiness_per_domain() -> None:
    from predator_mesh.v19.watchlist import DomainWatchlist

    report = DomainWatchlist().to_report()
    assert report["verdict"] == "PASS"
    assert set(report["domains"]) == DOMAINS
    assert report["watch_item_count"] == 5
