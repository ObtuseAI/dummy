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

from autonomy.council_snapshot import build_council_snapshot  # noqa: E402
from autonomy.forecaster import EnsembleForecaster  # noqa: E402
from autonomy.mispricing_monitor import (  # noqa: E402
    persist_book_tape,
    persist_paper_entries,
    run_mispricing_sweep,
)
from autonomy.opportunist import OpportunistEngine  # noqa: E402
from autonomy.session import SessionMode, build_brain  # noqa: E402
from autonomy.signals.sportsbook import SportsbookConsensusSignal  # noqa: E402

OUT_PATH = Path("runtime/autonomy/mispricing_monitor_latest.json")
# WS-8 (spec section 3.2): evidence artifacts the CLV grader
# (scripts/run_dummy_clv_grader.py) reads. Appended, never overwritten.
BOOK_TAPE_PATH = Path("runtime/autonomy/book_tape.jsonl")
PAPER_ENTRIES_PATH = Path("runtime/autonomy/paper_entries.jsonl")
# WS-13: council health + open-opportunities snapshot for the dashboard's
# read-only council panel. Read-only reporting artifact -- see
# autonomy/council_snapshot.py for the fail-closed contract.
COUNCIL_SNAPSHOT_PATH = Path("runtime/autonomy/council_snapshot.json")


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

    def specialist_fn(market):
        # WS-8: tag each paper entry with the council's own routing label
        # (Specialist.name -- "mlb", "crypto", ...) so the CLV grader's
        # autonomy.taxonomy.specialist_for() resolves it. None (unrouted,
        # e.g. WNBA) persists as "unknown" -- untagged, not miscategorized.
        try:
            specialist = council.route(market)
            return specialist.name if specialist is not None else None
        except Exception:
            return None

    def ejection_fn(market):
        # Raw ESPN play observations only. The sweep adds its own receipt
        # timestamp and carries them as evidence; they never reprice a game or
        # change opportunist gating (the live score already reflects absence).
        try:
            specialist = council.route(market)
            return specialist.ejection_events(market) if specialist is not None else ()
        except Exception:
            return ()

    # CF1: the single power-ratings source instance, resolved once. divergence_fn
    # queries ONLY this source rather than re-running the whole registry (which
    # forecast_fn already did this pass) -- a full re-run would re-execute every
    # source's generate() and double-count failures toward its circuit breaker.
    power_signal = next(
        (s for s in brain.registry.sources() if getattr(s, "name", "") == "power_ratings"),
        None,
    )

    def divergence_fn(market):
        # The power-ratings challenger's own divergence evidence for this market
        # (None unless the external-ratings ensemble disagreed with our engine
        # while the ratings sources agreed). Surfaced as buy-low evidence only;
        # power_ratings stays an unpromoted challenger, so this never gates a
        # strike. Fail-closed: no source / unrouted / crypto / any error -> None.
        if power_signal is None:
            return None
        try:
            if not power_signal.applicable(market):
                return None
            signal = power_signal.generate(market)
            return (signal.features or {}).get("power_divergence") if signal else None
        except Exception:
            return None

    return brain, council, forecast_fn, book_fn, specialist_fn, divergence_fn, ejection_fn


FAST_OUT_PATH = Path("runtime/autonomy/mispricing_monitor_fast_latest.json")


def _persist_evidence(report: dict, tape_state: dict) -> None:
    """WS-8: append this pass's book-tape rows + paper entries (best-effort).

    ``tape_state`` is a single mutable dict the caller carries across passes
    (avoids re-reading the whole tape file every 90 seconds); a persistence
    failure is printed as a status line and swallowed -- evidence capture
    must never take the monitor down.
    """
    try:
        updated = persist_book_tape(BOOK_TAPE_PATH, report, last_by_ticker=tape_state.get("last"))
        tape_state["last"] = updated
        persist_paper_entries(PAPER_ENTRIES_PATH, report)
    except Exception as exc:
        print(json.dumps({"status": f"WS8_PERSIST_ERROR:{type(exc).__name__}", "error": str(exc)[:200]}))


def _persist_council_snapshot(council, report, ticker_specialist, now_iso) -> None:
    """WS-13: best-effort council snapshot write (never takes the pass down).

    Read-only reporting artifact only -- this touches no pricing, allocator,
    executor, or risk path, and a failure here is swallowed exactly like the
    other evidence-persistence helpers in this script.
    """
    try:
        snapshot = build_council_snapshot(council, report, ticker_specialist, now_iso)
        _atomic_json(COUNCIL_SNAPSHOT_PATH, snapshot)
    except Exception as exc:
        print(json.dumps({
            "status": f"COUNCIL_SNAPSHOT_ERROR:{type(exc).__name__}", "error": str(exc)[:200],
        }))


def _one_pass(
    brain, council, forecast_fn, book_fn, specialist_fn, divergence_fn,
    ejection_fn, opportunist, tape_state,
) -> dict:
    brain.registry.on_cycle_start()  # warm/refresh source caches for this pass
    council.on_cycle_start()  # per-specialist warmup (isolated; failures skip)
    markets = brain.scanner.scan()
    now_iso = datetime.now(timezone.utc).isoformat()
    # WS-13: this pass's ticker -> routed-specialist-name map, built the same
    # way run_mispricing_sweep's own source_by_ticker is (a raising
    # specialist_fn is caught per-market) -- used only to tag the council
    # snapshot's open-opportunities counts, never fed back into pricing.
    ticker_specialist: dict[str, str | None] = {}
    for market in markets:
        try:
            ticker_specialist[market.ticker] = specialist_fn(market) if specialist_fn else None
        except Exception:
            ticker_specialist[market.ticker] = None
    report = run_mispricing_sweep(
        markets, forecast_fn, now_iso=now_iso, book_fn=book_fn, opportunist=opportunist,
        specialist_fn=specialist_fn, divergence_fn=divergence_fn,
        ejection_fn=ejection_fn,
    )
    _persist_evidence(report, tape_state)
    _persist_council_snapshot(council, report, ticker_specialist, now_iso)
    # tape_rows/entries are now durably appended to their own JSONL files
    # (the CLV grader's real inputs); drop them from the dashboard-facing
    # snapshot so OUT_PATH stays the small "latest pass" summary it always
    # was -- one row per assessed market every 90s would otherwise bloat it.
    report.pop("tape_rows", None)
    report.pop("entries", None)
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


def crypto_micro_pass(
    crypto_scanner, forecast_fn, book_fn, opportunist, *, now_iso: str,
    specialist_fn=None, tape_state: dict | None = None,
) -> dict:
    """Crypto-only buy-low micro-pass: fresh Kalshi quotes, WARM model cache.

    Deliberately does NOT warm the registry/council -- the crypto hub cache
    persists from the last full pass, so the model reuses recent spot/vol with
    zero new candle/Deribit fetches. Only Kalshi quotes for the crypto
    universe are re-read, catching intra-contract dips on the fast (15m/hourly)
    markets a full pass is too slow to see. Shared opportunist state carries
    the locked candidates across passes.

    ``specialist_fn``/``tape_state`` (WS-8, both optional) wire the same
    book-tape persistence the full sweep does; omitting them (as callers
    that predate WS-8 do) just skips persistence -- the returned report is
    unaffected either way.
    """
    markets = crypto_scanner.scan()
    report = run_mispricing_sweep(
        markets, forecast_fn, now_iso=now_iso, book_fn=book_fn, opportunist=opportunist,
        specialist_fn=specialist_fn,
    )
    if tape_state is not None:
        _persist_evidence(report, tape_state)  # WS-8: fast lane feeds the tape too
    report.pop("tape_rows", None)
    report.pop("entries", None)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Buy-low / opportunist monitor pass.")
    parser.add_argument("--loop", action="store_true", help="run continuously")
    parser.add_argument("--interval", type=int, default=90, help="seconds between passes in --loop")
    parser.add_argument("--crypto-fast", action="store_true",
                        help="run crypto-only micro-passes between full sweeps")
    parser.add_argument("--fast-interval", type=int, default=30,
                        help="seconds between crypto micro-passes (with --crypto-fast)")
    args = parser.parse_args()

    (
        brain, council, forecast_fn, book_fn, specialist_fn, divergence_fn,
        ejection_fn,
    ) = _build()
    opportunist = OpportunistEngine()  # stateful across passes within this process
    crypto_scanner = _crypto_scanner(brain)
    # WS-8: last-row-per-ticker tape index, carried across passes (both the
    # full sweep and the crypto fast lane share it) so a --loop run never
    # re-reads the whole tape file to dedup; a fresh process warm-starts it
    # from disk on the first pass (persist_book_tape's default).
    tape_state: dict = {}

    def _tick() -> None:
        try:
            report = _one_pass(
                brain, council, forecast_fn, book_fn, specialist_fn, divergence_fn,
                ejection_fn, opportunist, tape_state)
            print(json.dumps({
                "status": "OK",
                "scanned": report["scanned"],
                "shortlist": report["shortlist_count"],
                "opportunities": report["opportunity_count"],
                # WS-5: per-game lattice conviction tiers (grouped inside the
                # sweep itself via autonomy.coherence -- nothing to assemble
                # here, the report already carries them through).
                "structural": report.get("structural_count", 0),
                "cross_confirmed": report.get("cross_confirmed_count", 0),
            }))
        except Exception as exc:  # a monitor must never wedge on a bad pass
            print(json.dumps({"status": f"ERROR:{type(exc).__name__}", "error": str(exc)[:200]}))

    def _fast_tick() -> None:
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            report = crypto_micro_pass(
                crypto_scanner, forecast_fn, book_fn, opportunist, now_iso=now_iso,
                specialist_fn=specialist_fn, tape_state=tape_state)
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
