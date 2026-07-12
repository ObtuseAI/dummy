"""WS-19 liquidity edge floors + crypto fast-lane micro-pass."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from autonomy.mispricing import (
    MispricingMonitor,
    assess_mispricing,
    liquidity_edge_floor,
)


# -- liquidity edge floors -----------------------------------------------------

def test_liquidity_edge_floor_tiers():
    # Thresholds are CENTS ($50 = 5000c, $200 = 20000c).
    assert liquidity_edge_floor(None) == 0.0        # unknown depth -> neutral
    assert liquidity_edge_floor(0) == 0.04          # reported empty -> most restrictive
    assert liquidity_edge_floor(3_000) == 0.04      # < $50
    assert liquidity_edge_floor(4_999) == 0.04
    assert liquidity_edge_floor(5_000) == 0.02      # [$50, $200)
    assert liquidity_edge_floor(19_999) == 0.02
    assert liquidity_edge_floor(20_000) == 0.0      # deep
    assert liquidity_edge_floor(500_000) == 0.0     # $5k, deep
    assert liquidity_edge_floor("garbage") == 0.0


def test_marginal_edge_survives_deep_book_but_not_thin():
    # Model 0.60, YES ask 55c -> 5% raw edge. Clears the 4% base threshold.
    deep = assess_mispricing("KXBTCD-x-T1", 0.60, 55, 47, liquidity=500_000)  # $5k
    assert deep.side == "YES" and deep.edge == pytest.approx(0.05)
    # Same market, ~$30 of depth needs 4%+4%=8% -> the 5% edge no longer clears.
    thin = assess_mispricing("KXBTCD-x-T1", 0.60, 55, 47, liquidity=3_000)
    assert thin.side == "NONE"
    # Mid-tier ~$100 (needs 6%) also rejects the 5% edge.
    mid = assess_mispricing("KXBTCD-x-T1", 0.60, 55, 47, liquidity=10_000)
    assert mid.side == "NONE"


def test_monitor_passes_market_liquidity_through():
    class _Market:
        ticker = "KXBTCD-x-T1"
        yes_ask = 55
        no_ask = 47
        liquidity = 2_000  # ~$20, thin

    monitor = MispricingMonitor(forecast_fn=lambda m: 0.60, book_fn=None)
    assessment = monitor.assess_market(_Market())
    assert assessment is not None and assessment.side == "NONE"  # thin-book floor applied
    # A deep book on the same numbers is actionable.
    class _Deep(_Market):
        liquidity = 500_000
    assert monitor.assess_market(_Deep()).side == "YES"
    # A market whose liquidity attr is present but None -> neutral (no floor).
    class _UnknownDepth(_Market):
        liquidity = None
    assert monitor.assess_market(_UnknownDepth()).side == "YES"


# -- crypto fast-lane micro-pass ----------------------------------------------

def _load_runner():
    path = Path(__file__).resolve().parent.parent / "scripts" / "run_dummy_mispricing_monitor.py"
    spec = importlib.util.spec_from_file_location("_mp_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeCryptoMarket:
    def __init__(self, ticker):
        self.ticker = ticker
        self.yes_ask = 55
        self.no_ask = 47
        self.liquidity = 5000


def test_crypto_micro_pass_runs_sweep_without_warming_registry():
    runner = _load_runner()

    class _Scanner:
        def __init__(self):
            self.scans = 0

        def scan(self):
            self.scans += 1
            return [_FakeCryptoMarket("KXBTCD-26JUL0917-T70000")]

    scanner = _Scanner()
    # The micro-pass takes NO brain/registry -- it structurally cannot warm the
    # hub (proving "reuse the warm cache, zero new candle/Deribit fetches").
    report = runner.crypto_micro_pass(
        scanner, forecast_fn=lambda m: 0.62, book_fn=None,
        opportunist=None, now_iso="2026-07-12T00:00:00+00:00")
    assert scanner.scans == 1
    assert report["scanned"] == 1
    assert "shortlist" in report and "opportunities" in report


def test_crypto_scanner_filters_to_crypto_series_only():
    runner = _load_runner()
    from autonomy.ontology import Vertical
    from autonomy.scanner import classify_vertical

    class _Brain:
        class scanner:
            watchlist = ["KXBTC15M", "KXETHD", "KXMLBGAME", "KXNFLGAME", "KXSOLD"]
            fetch_series = staticmethod(lambda s: {"markets": []})

    crypto = runner._crypto_scanner(_Brain())
    assert all(classify_vertical(series) is Vertical.CRYPTO for series in crypto.watchlist)
    assert "KXMLBGAME" not in crypto.watchlist and "KXNFLGAME" not in crypto.watchlist
    assert "KXBTC15M" in crypto.watchlist and "KXETHD" in crypto.watchlist
