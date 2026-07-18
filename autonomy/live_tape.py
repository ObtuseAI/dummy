"""Reader for the live play-by-play tape (Wave-17).

The Wave-16 poller appends one JSON line per material game change to
``runtime/autonomy/live_events.jsonl``. This is the consuming side: a
bounded tail read answering one question cheaply -- "did anything happen in
a live game in the last N seconds, and in which games?" -- so the mispricing
monitor can burst sports micro-passes exactly when the field is moving and
stay quiet when it is not.

Fail-closed: a missing tape, malformed line, or unparsable timestamp reads
as "nothing fresh" rather than an error.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

TAPE_PATH = Path("runtime/autonomy/live_events.jsonl")

# Only read this many bytes from the tape's tail: events are ~300 bytes, so
# this comfortably covers any burst window without ever scanning a season of
# history on each check.
_TAIL_BYTES = 64 * 1024


def fresh_events(
    max_age_seconds: float,
    *,
    path: Path | None = None,
    now_fn: Callable[[], datetime] | None = None,
) -> list[dict[str, Any]]:
    """Tape records younger than ``max_age_seconds``, oldest first."""
    tape = path or TAPE_PATH
    now = (now_fn or (lambda: datetime.now(timezone.utc)))()
    try:
        with tape.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - _TAIL_BYTES))
            tail = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    fresh: list[dict[str, Any]] = []
    for line in tail.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue   # possibly a partial first line from the byte seek
        try:
            record = json.loads(line)
            observed = datetime.fromisoformat(str(record.get("observed_at")))
        except (ValueError, TypeError):
            continue
        if observed.tzinfo is None:
            continue
        if (now - observed).total_seconds() <= max_age_seconds:
            fresh.append(record)
    return fresh


def fresh_live_games(
    max_age_seconds: float,
    *,
    path: Path | None = None,
    now_fn: Callable[[], datetime] | None = None,
) -> set[tuple[str, str]]:
    """{(league, event_id)} with events younger than ``max_age_seconds``."""
    return {
        (str(record.get("league")), str(record.get("event_id")))
        for record in fresh_events(max_age_seconds, path=path, now_fn=now_fn)
        if record.get("league") and record.get("event_id")
    }
