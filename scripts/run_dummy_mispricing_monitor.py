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
    """Assemble the read-only forecast + book providers from the shadow brain."""
    brain = build_brain(SessionMode.SHADOW)
    forecaster = EnsembleForecaster(brain.ledger)
    book_signal = SportsbookConsensusSignal()

    def forecast_fn(market):
        # Our fused model probability. fuse() excludes challenger_only sources,
        # so this is the execution-grade model view, not the challengers.
        try:
            signals = list(brain.registry.signals_for(market))
            forecast = forecaster.fuse(market, signals)
            return forecast.probability_yes if forecast else None
        except Exception:
            return None

    def book_fn(market):
        # De-vigged sportsbook consensus (winner markets only); None otherwise.
        try:
            if not book_signal.applicable(market):
                return None
            signal = book_signal.generate(market)
            return signal.probability_yes if signal else None
        except Exception:
            return None

    return brain, forecast_fn, book_fn


def _one_pass(brain, forecast_fn, book_fn, opportunist) -> dict:
    brain.registry.on_cycle_start()  # warm/refresh source caches for this pass
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

    brain, forecast_fn, book_fn = _build()
    opportunist = OpportunistEngine()  # stateful across passes within this process

    def _tick() -> None:
        try:
            report = _one_pass(brain, forecast_fn, book_fn, opportunist)
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
