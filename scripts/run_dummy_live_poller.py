#!/usr/bin/env python
"""Bounded live-game poll session (Wave-16): mounts the Wave-3 poller.

Each invocation is one crash-isolated session, built for a scheduled task
firing every ~5 minutes (the same fire-and-exit shape as every other loop):

  * no live games -> exits within seconds (one scoreboard read per league);
  * live games   -> event-driven polling for up to ``--budget-seconds``
    (default 270, under a 5-minute cadence so sessions never overlap the
    next fire), reacting to real plays at the poller's fast interval.

Every material change (score, lead change, inning/period flip, base-out
turnover, game start/final) is:
  * appended to ``runtime/autonomy/live_events.jsonl`` -- the durable
    play-by-play tape (the autoresearch lab's point-in-time evidence);
  * recorded as a deduplicated ledger external observation (best-effort;
    the busy single-writer ledger must never wedge a poll tick).

``runtime/autonomy/live_poller_status.json`` carries the dashboard surface.

Read/observe only: no session, execution, or capital authority. Doubly
gated: the constructor flag AND the ``DUMMY_LIVE_POLLER`` env switch must
both be on (the Wave-3 fail-closed contract), so an unset box stays inert.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.live_poller import LiveGamePoller  # noqa: E402

RUNTIME_DIR = Path("runtime/autonomy")
EVENTS_PATH = RUNTIME_DIR / "live_events.jsonl"
STATUS_PATH = RUNTIME_DIR / "live_poller_status.json"
LOCK_PATH = RUNTIME_DIR / "live_poller.lock"

DEFAULT_LEAGUES = ("mlb", "wnba", "nba", "nfl", "nhl", "ncaaf", "ncaamb")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _acquire_lock(stale_seconds: float) -> bool:
    """Single instance per box: a fresh lock file means another session is
    mid-poll (sessions are bounded, so a stale lock is a crash -- reclaim)."""
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    try:
        if LOCK_PATH.exists():
            age = time.time() - LOCK_PATH.stat().st_mtime
            if age < stale_seconds:
                return False
        LOCK_PATH.write_text(json.dumps({"pid": os.getpid(), "at": _now_iso()}),
                             encoding="utf-8")
        return True
    except OSError:
        return False


def _release_lock() -> None:
    try:
        LOCK_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def _write_status(payload: dict) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    temporary = STATUS_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True),
                         encoding="utf-8")
    temporary.replace(STATUS_PATH)


def _make_sink(ledger_factory=None):
    """The change-event sink: JSONL append always; ledger observation
    best-effort (busy writer -> skip this one, never block the tick)."""
    holder: dict = {"ledger": None, "failed": False}

    def sink(record: dict) -> None:
        stamped = {**record, "observed_at": _now_iso()}
        with EVENTS_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(stamped, sort_keys=True) + "\n")
        if holder["failed"]:
            return
        try:
            if holder["ledger"] is None:
                if ledger_factory is None:
                    from autonomy.ledger import AutonomyLedger

                    holder["ledger"] = AutonomyLedger()
                else:
                    holder["ledger"] = ledger_factory()
            home = record.get("home_score") or 0
            away = record.get("away_score") or 0
            holder["ledger"].record_external_observation(
                source="live_poller",
                series_id=f"{record.get('league')}|{record.get('event_id')}|{record.get('kind')}",
                observed_at=stamped["observed_at"],
                value=float(home - away),
                unit="score_margin",
                features=record,
            )
        except Exception:
            # One busy/locked write must not cost the tape or the session;
            # stop retrying the ledger for this session, keep the JSONL.
            holder["failed"] = True

    return sink


def run_session(
    *,
    budget_seconds: float,
    leagues: tuple[str, ...],
    poller: LiveGamePoller | None = None,
    sleep_fn=time.sleep,
    now_fn=time.monotonic,
) -> dict:
    """One bounded poll session; returns the summary written to status."""
    poller = poller or LiveGamePoller(
        leagues, enabled=True, record_event=_make_sink())
    started = now_fn()
    events_total = 0
    polls = 0
    live_ids: tuple[str, ...] = ()

    while True:
        result = poller.poll_once()
        polls += 1
        events_total += len(result.events)
        live_ids = result.live_event_ids
        elapsed = now_fn() - started
        remaining = budget_seconds - elapsed
        if not poller.enabled:
            status = "DISABLED"
            break
        if not live_ids:
            # Idle fast-exit: nothing live anywhere; the next task fire
            # re-checks. Never burn the budget sleeping on an empty slate.
            status = "IDLE_NO_LIVE_GAMES" if polls == 1 else "SESSION_COMPLETE"
            break
        if remaining <= 0:
            status = "BUDGET_EXHAUSTED"
            break
        sleep_fn(min(result.next_interval, remaining))

    summary = {
        "at": _now_iso(),
        "status": status,
        "polls": polls,
        "events_recorded": events_total,
        "live_games": len(live_ids),
        "live_event_ids": list(live_ids),
        "leagues": list(leagues),
        "budget_seconds": budget_seconds,
    }
    _write_status(summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget-seconds", type=float, default=270.0)
    parser.add_argument("--leagues", default=",".join(DEFAULT_LEAGUES))
    parser.add_argument("--lock-stale-seconds", type=float, default=420.0)
    args = parser.parse_args()

    if not _acquire_lock(args.lock_stale_seconds):
        print(json.dumps({"status": "LOCKED_ANOTHER_SESSION"}))
        return 0
    try:
        leagues = tuple(t.strip() for t in args.leagues.split(",") if t.strip())
        summary = run_session(budget_seconds=args.budget_seconds, leagues=leagues)
        print(json.dumps(summary, sort_keys=True))
        return 0
    finally:
        _release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
