#!/usr/bin/env python
"""Dedicated buy-low / opportunist monitor pass (arsenal P2b).

Read-only. Scans public Kalshi markets, prices each with our fused model,
de-vigs the sportsbook (sports winners), triangulates for mispricing, and
drives the patience/opportunist engine across passes. Writes
``runtime/autonomy/mispricing_monitor_latest.json`` for the dashboard.

This is a monitor, not a trader: it has no session, execution, or capital
authority and never places an order. It surfaces the mispricing shortlist and
the opportunist strikes as challenger/paper evidence for review.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.forecaster import EnsembleForecaster  # noqa: E402
from autonomy.mispricing_monitor import run_mispricing_sweep  # noqa: E402
from autonomy.opportunist import OpportunistEngine  # noqa: E402
from autonomy.session import SessionMode, build_brain  # noqa: E402
from autonomy.signals.sportsbook import SportsbookConsensusSignal  # noqa: E402

OUT_PATH = Path("runtime/autonomy/mispricing_monitor_latest.json")


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _build():
    """Assemble the read-only forecast + book providers from the shadow brain.

    Council routing (autonomy/specialists): each market is dispatched to its
    vertical's specialist for the live view and the sharp book, with the
    pre-council sportsbook-consensus path kept as a fallback for markets no
    specialist claims (e.g. WNBA) -- byte-identical behavior to the
    hand-wired closures this replaces.
    """
    from autonomy.specialists import build_specialist_registry

    brain = build_brain(SessionMode.SHADOW)
    forecaster = EnsembleForecaster(brain.ledger)
    council = build_specialist_registry(brain.registry)
    fallback_book = SportsbookConsensusSignal()

    def forecast_fn(market):
        try:
            # For an in-progress game, prefer the specialist's live view (the
            # monitor never trades, so live evidence is fair game); else the
            # execution-grade fused model (fuse() excludes challenger_only).
            specialist = council.route(market)
            if specialist is not None:
                live = specialist.live_forecast(market)
                if live is not None:
                    return live.probability_yes
            signals = list(brain.registry.signals_for(market))
            forecast = forecaster.fuse(market, signals)
            return forecast.probability_yes if forecast else None
        except Exception:
            return None

    def book_fn(market):
        # The specialist's book (live ESPN-summary de-vig in play, sportsbook
        # consensus pre-game); a routed specialist owns the book decision, so
        # only unrouted sports markets (e.g. WNBA) keep the consensus book.
        try:
            specialist = council.route(market)
            if specialist is not None:
                return specialist.book(market)
            if fallback_book.applicable(market):
                signal = fallback_book.generate(market)
                return signal.probability_yes if signal else None
            return None
        except Exception:
            return None

    return brain, council, forecast_fn, book_fn


FAST_OUT_PATH = Path("runtime/autonomy/mispricing_monitor_fast_latest.json")


def _one_pass(brain, council, forecast_fn, book_fn, opportunist) -> dict:
    brain.registry.on_cycle_start()  # warm/refresh source caches for this pass
    council.on_cycle_start()  # per-specialist warmup (isolated; failures skip)
    markets = brain.scanner.scan()
    now_iso = datetime.now(timezone.utc).isoformat()
    report = run_mispricing_sweep(
        markets, forecast_fn, now_iso=now_iso, book_fn=book_fn, opportunist=opportunist,
    )
    _atomic_json(OUT_PATH, report)
    return report


def _crypto_scanner(brain):
    """A crypto-only scanner over the brain's watchlist (fresh Kalshi quotes)."""
    from autonomy.ontology import Vertical
    from autonomy.scanner import MarketScanner, classify_vertical

    crypto_series = [
        series for series in brain.scanner.watchlist
        if classify_vertical(series) is Vertical.CRYPTO
    ]
    return MarketScanner(
        fetch_series=brain.scanner.fetch_series,
        watchlist=crypto_series,
        verticals={Vertical.CRYPTO},
    )


def crypto_micro_pass(crypto_scanner, forecast_fn, book_fn, opportunist, *, now_iso: str) -> dict:
    """Crypto-only buy-low micro-pass: fresh Kalshi quotes, WARM model cache.

    Deliberately does NOT warm the registry/council -- the crypto hub cache
    persists from the last full pass, so the model reuses recent spot/vol with
    zero new candle/Deribit fetches. Only Kalshi quotes for the crypto
    universe are re-read, catching intra-contract dips on the fast (15m/hourly)
    markets a full pass is too slow to see. Shared opportunist state carries
    the locked candidates across passes.
    """
    markets = crypto_scanner.scan()
    return run_mispricing_sweep(
        markets, forecast_fn, now_iso=now_iso, book_fn=book_fn, opportunist=opportunist,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Buy-low / opportunist monitor pass.")
    parser.add_argument("--loop", action="store_true", help="run continuously")
    parser.add_argument("--interval", type=int, default=90, help="seconds between passes in --loop")
    parser.add_argument("--crypto-fast", action="store_true",
                        help="run crypto-only micro-passes between full sweeps")
    parser.add_argument("--fast-interval", type=int, default=30,
                        help="seconds between crypto micro-passes (with --crypto-fast)")
    args = parser.parse_args()

    brain, council, forecast_fn, book_fn = _build()
    opportunist = OpportunistEngine()  # stateful across passes within this process
    crypto_scanner = _crypto_scanner(brain)

    def _tick() -> None:
        try:
            report = _one_pass(brain, council, forecast_fn, book_fn, opportunist)
            print(json.dumps({
                "status": "OK",
                "scanned": report["scanned"],
                "shortlist": report["shortlist_count"],
                "opportunities": report["opportunity_count"],
            }))
        except Exception as exc:  # a monitor must never wedge on a bad pass
            print(json.dumps({"status": f"ERROR:{type(exc).__name__}", "error": str(exc)[:200]}))

    def _fast_tick() -> None:
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            report = crypto_micro_pass(
                crypto_scanner, forecast_fn, book_fn, opportunist, now_iso=now_iso)
            _atomic_json(FAST_OUT_PATH, report)
            print(json.dumps({
                "status": "FAST_OK",
                "scanned": report["scanned"],
                "opportunities": report["opportunity_count"],
            }))
        except Exception as exc:
            print(json.dumps({"status": f"FAST_ERROR:{type(exc).__name__}", "error": str(exc)[:200]}))

    if args.loop:
        interval = max(15, int(args.interval))
        if args.crypto_fast:
            fast_interval = max(10, int(args.fast_interval))
            while True:
                _tick()  # full sweep also warms the crypto hub cache
                # Micro-passes until the next full sweep is due. Sequential
                # execution is itself the skip-if-still-running guard: a slow
                # micro-pass simply delays the next, never overlaps it.
                next_full = time.monotonic() + interval
                while time.monotonic() + fast_interval <= next_full:
                    time.sleep(fast_interval)
                    _fast_tick()
                remaining = next_full - time.monotonic()
                if remaining > 0:
                    time.sleep(remaining)
        else:
            while True:
                _tick()
                time.sleep(interval)
    else:
        _tick()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
