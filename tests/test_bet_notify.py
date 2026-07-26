"""Read-only event collection for the lightweight desktop notifier."""
from __future__ import annotations

import sqlite3

from desktop import bet_notify


def _ledger(tmp_path, rows):
    p = tmp_path / "ledger.db"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE outcomes(id INTEGER PRIMARY KEY, kind TEXT, market_ticker TEXT, pnl_cents INTEGER)")
    c.executemany("INSERT INTO outcomes(id,kind,market_ticker,pnl_cents) VALUES(?,?,?,?)", rows)
    c.commit()
    c.close()
    return p


def test_format_event_opened_settled_and_ignored():
    assert bet_notify.format_event("FILLED", "KXBTCD-A", None)["title"] == "Bet opened"
    assert bet_notify.format_event("SHADOW", "KXBTCD-A", None)["title"] == "Shadow bet opened"
    won = bet_notify.format_event("SETTLED_WIN", "KXMLB-B", 120)
    assert won["title"] == "Bet won +$1.20" and won["warning"] is False
    lost = bet_notify.format_event("SETTLED_LOSS", "KXMLB-C", -80)
    assert lost["title"] == "Bet lost -$0.80" and lost["warning"] is True
    # gate-blocked / never-filled are silent
    assert bet_notify.format_event("BLOCKED_LOCAL", "X", None) is None
    assert bet_notify.format_event("EXPIRED", "X", None) is None
    titled = bet_notify.format_event("SETTLED_LOSS", "KXMLB-C", -80, "Royals at Cubs")
    assert titled["body"] == "Royals at Cubs"


def test_collect_events_incremental_and_filtered(tmp_path):
    led = _ledger(tmp_path, [
        (1, "BLOCKED_LOCAL", "X", None),
        (2, "FILLED", "KXBTCD-A", None),
        (3, "SETTLED_WIN", "KXMLB-B", 200),
        (4, "EXPIRED", "Y", None),
        (5, "SETTLED_LOSS", "KXMLB-C", -50),
    ])
    events, new_last = bet_notify.collect_events(0, ledger=led)
    assert new_last == 5                                   # advances past every row seen
    titles = [e["title"] for e in events]
    assert titles == ["Bet opened", "Bet won +$2.00", "Bet lost -$0.50"]  # blocked/expired filtered
    # incremental: from id 3, only 5 is notify-worthy (4 is expired)
    events2, last2 = bet_notify.collect_events(3, ledger=led)
    assert last2 == 5 and [e["title"] for e in events2] == ["Bet lost -$0.50"]


def test_missing_ledger_is_safe(tmp_path):
    events, last = bet_notify.collect_events(7, ledger=tmp_path / "nope.db")
    assert events == [] and last == 7                      # unchanged -> nothing missed


def test_state_roundtrip_and_seed(tmp_path):
    state = tmp_path / "s.json"
    assert bet_notify.read_state(state) == 0
    bet_notify.write_state(42, state)
    assert bet_notify.read_state(state) == 42
    # seed_silently on a fresh state adopts the ledger's max id (no backlog blast)
    state2 = tmp_path / "s2.json"
    led = _ledger(tmp_path, [(1, "FILLED", "A", None), (2, "SETTLED_WIN", "B", 10)])
    bet_notify.seed_silently(ledger=led, state=state2)
    assert bet_notify.read_state(state2) == 2
    # existing state is left untouched
    bet_notify.seed_silently(ledger=led, state=state)
    assert bet_notify.read_state(state) == 42
