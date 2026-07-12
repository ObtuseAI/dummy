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
    from autonomy.live_odds import EspnSummaryBook
    from autonomy.signals.sports_intelligence import parse_sports_contract
    from autonomy.sports.espn import EspnClient, canonical_team

    brain = build_brain(SessionMode.SHADOW)
    forecaster = EnsembleForecaster(brain.ledger)
    book_signal = SportsbookConsensusSignal()
    espn = EspnClient()
    live_book = EspnSummaryBook(league="mlb")
    # The live MLB challenger already prices in-progress games (mlb_live_winner);
    # the monitor is paper/evidence, so it may consume that live view directly.
    mlb_signal = next(
        (s for s in brain.registry.sources() if getattr(s, "name", "") == "mlb_intelligence"),
        None,
    )

    def _live_mlb_game(market):
        """Resolve an in-progress MLB game for a winner market, else None."""
        parsed = parse_sports_contract(market)
        if parsed is None or parsed.sport != "mlb" or parsed.market_type != "winner":
            return None
        if not parsed.competitors:
            return None
        game = espn.find_matchup(
            "mlb", parsed.competitors[0], parsed.competitors[1], parsed.date_yyyymmdd)
        if game is None or game.status != "in":
            return None
        return parsed, game

    def forecast_fn(market):
        try:
            # For an in-progress MLB winner, prefer the live challenger view (the
            # monitor never trades, so live evidence is fair game); else the
            # execution-grade fused model (fuse() excludes challenger_only).
            if mlb_signal is not None and _live_mlb_game(market) is not None:
                live = mlb_signal.generate(market)
                if live is not None and live.features.get("live"):
                    return live.probability_yes
            signals = list(brain.registry.signals_for(market))
            forecast = forecaster.fuse(market, signals)
            return forecast.probability_yes if forecast else None
        except Exception:
            return None

    def book_fn(market):
        # De-vigged sportsbook consensus. For an in-progress MLB winner, the live
        # ESPN-summary book overrides the pre-game scoreboard line.
        try:
            resolved = _live_mlb_game(market)
            if resolved is not None:
                parsed, game = resolved
                home_prob = live_book.home_win_probability(game.game_id)
                if home_prob is not None:
                    subject = canonical_team("mlb", parsed.subject or "")
                    yes_is_home = subject == canonical_team("mlb", game.home)
                    return home_prob if yes_is_home else 1.0 - home_prob
            if book_signal.applicable(market):
                signal = book_signal.generate(market)
                return signal.probability_yes if signal else None
            return None
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
