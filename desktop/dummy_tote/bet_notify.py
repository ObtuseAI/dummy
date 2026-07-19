"""Wave-54: bet-event notifications for the Tote app's tray.

Native toasts when a bet OPENS or SETTLES. The event source is the ledger's
small ``outcomes`` table, read INCREMENTALLY (``id > last-seen``) and READ-ONLY
each poll -- a sub-millisecond bounded read on a ~7k-row table keyed by its
integer primary key, nothing like the heavy scans the dashboard avoids. The
last-seen id is persisted so notifications never repeat across restarts, and the
first run seeds silently (no backlog blast).

Pure + Qt-free so it unit-tests without a GUI toolkit; the app wires
``collect_events`` to ``QSystemTrayIcon.showMessage``.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

RUNTIME_DIR = Path(os.environ.get("DUMMY_RUNTIME_DIR") or r"D:\DummyRuntime\autonomy")
LEDGER_PATH = RUNTIME_DIR / "ledger.db"
STATE_PATH = RUNTIME_DIR / "bet_notify_state.json"

# Notify-worthy outcome kinds. BLOCKED_LOCAL (gate-blocked, never opened) and
# EXPIRED (never filled) are deliberately silent.
_OPENED = {"FILLED", "SHADOW"}
_SETTLED = {"SETTLED_WIN", "SETTLED_LOSS"}


def _usd(cents: Any) -> str:
    try:
        c = int(cents)
    except (TypeError, ValueError):
        return ""
    return ("-" if c < 0 else "+") + "$" + f"{abs(c) / 100:.2f}"


def format_event(kind: str, ticker: str, pnl_cents: Any) -> dict[str, Any] | None:
    """A notify-worthy outcome -> {title, body, warning}; None if not notify-worthy."""
    ticker = str(ticker or "")
    if kind in _OPENED:
        tag = "Shadow bet opened" if kind == "SHADOW" else "Bet opened"
        return {"title": tag, "body": ticker, "warning": False}
    if kind in _SETTLED:
        won = kind == "SETTLED_WIN"
        pnl = _usd(pnl_cents)
        title = ("Bet won " if won else "Bet lost ") + pnl if pnl else ("Bet won" if won else "Bet lost")
        return {"title": title, "body": ticker, "warning": not won}
    return None


def fetch_new(conn: sqlite3.Connection, last_id: int, limit: int = 40) -> list[dict[str, Any]]:
    """Outcomes with id greater than ``last_id`` (oldest first)."""
    rows = conn.execute(
        "SELECT id, kind, market_ticker, pnl_cents FROM outcomes "
        "WHERE id > ? ORDER BY id LIMIT ?",
        (int(last_id), int(limit)),
    ).fetchall()
    return [{"id": int(r[0]), "kind": str(r[1]), "ticker": r[2], "pnl_cents": r[3]} for r in rows]


def max_outcome_id(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COALESCE(MAX(id), 0) FROM outcomes").fetchone()
    return int(row[0]) if row else 0


def read_state(path: Path | None = None) -> int:
    target = path or STATE_PATH
    try:
        return int(json.loads(target.read_text(encoding="utf-8")).get("last_outcome_id", 0))
    except (OSError, ValueError, TypeError):
        return 0


def write_state(last_id: int, path: Path | None = None) -> None:
    target = path or STATE_PATH
    try:
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"last_outcome_id": int(last_id)}), encoding="utf-8")
        tmp.replace(target)
    except OSError:
        pass


def connect_ro(path: Path | None = None) -> sqlite3.Connection | None:
    """Read-only ledger connection; None if unavailable. mode=ro can never
    upgrade to a write lock, so it never blocks the writer beyond a brief read."""
    ledger = path or LEDGER_PATH
    if not ledger.exists():
        return None
    try:
        conn = sqlite3.connect("file:" + ledger.as_posix() + "?mode=ro", uri=True, timeout=5.0)
        conn.execute("PRAGMA busy_timeout=4000")
        return conn
    except sqlite3.Error:
        return None


def collect_events(last_id: int, *, ledger: Path | None = None) -> tuple[list[dict[str, Any]], int]:
    """(notify-worthy events, new last_id). Skip-on-lock: on any DB error the
    caller's last_id is returned unchanged so nothing is missed or double-sent."""
    conn = connect_ro(ledger)
    if conn is None:
        return [], last_id
    try:
        rows = fetch_new(conn, last_id)
    except sqlite3.Error:
        return [], last_id
    finally:
        conn.close()
    events: list[dict[str, Any]] = []
    new_last = last_id
    for row in rows:
        new_last = max(new_last, row["id"])
        ev = format_event(row["kind"], row["ticker"], row["pnl_cents"])
        if ev:
            events.append(ev)
    return events, new_last


def seed_silently(*, ledger: Path | None = None, state: Path | None = None) -> None:
    """On first ever run adopt the current max id so we don't blast a toast for
    every historical settlement."""
    target = state or STATE_PATH
    if target.exists():
        return
    conn = connect_ro(ledger)
    if conn is None:
        return
    try:
        write_state(max_outcome_id(conn), target)
    except sqlite3.Error:
        pass
    finally:
        conn.close()
