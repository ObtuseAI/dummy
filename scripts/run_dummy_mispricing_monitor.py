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
        # consensus pre-game); unrouted sports markets keep the consensus book.
        try:
            specialist = council.route(market)
            if specialist is not None:
                book_prob = specialist.book(market)
                if book_prob is not None:
                    return book_prob
                if specialist.name == "crypto":
                    return None  # no crypto book until Phase 1 (DVOL)
            if fallback_book.applicable(market):
                signal = fallback_book.generate(market)
                return signal.probability_yes if signal else None
            return None
        except Exception:
            return None

    return brain, council, forecast_fn, book_fn


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Buy-low / opportunist monitor pass.")
    parser.add_argument("--loop", action="store_true", help="run continuously")
    parser.add_argument("--interval", type=int, default=90, help="seconds between passes in --loop")
    args = parser.parse_args()

    brain, council, forecast_fn, book_fn = _build()
    opportunist = OpportunistEngine()  # stateful across passes within this process

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

    if args.loop:
        interval = max(15, int(args.interval))
        while True:
            _tick()
            time.sleep(interval)
    else:
        _tick()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
