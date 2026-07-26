from __future__ import annotations

import sqlite3

from desktop import bet_notify, notifier


def test_process_once_emits_only_notify_worthy_rows_and_advances(tmp_path, monkeypatch):
    ledger = tmp_path / "ledger.db"
    state = tmp_path / "notify.json"
    with sqlite3.connect(ledger) as conn:
        conn.execute(
            "CREATE TABLE outcomes("
            "id INTEGER PRIMARY KEY, kind TEXT, market_ticker TEXT, pnl_cents INTEGER)"
        )
        conn.executemany(
            "INSERT INTO outcomes VALUES(?,?,?,?)",
            [
                (1, "BLOCKED_LOCAL", "NO-ORDER", None),
                (2, "FILLED", "KXBTC", None),
                (3, "SETTLED_WIN", "KXBTC", 125),
            ],
        )

    collect = bet_notify.collect_events
    write = bet_notify.write_state
    monkeypatch.setattr(
        bet_notify,
        "collect_events",
        lambda last_id: collect(last_id, ledger=ledger),
    )
    monkeypatch.setattr(bet_notify, "write_state", lambda last_id: write(last_id, state))
    emitted = []

    assert notifier.process_once(0, emit=emitted.append) == 3
    assert [event["title"] for event in emitted] == ["Bet opened", "Bet won +$1.25"]
    assert bet_notify.read_state(state) == 3


def test_toast_script_xml_escapes_untrusted_market_text():
    script = notifier._powershell_toast_script("Bet won", "A'B < C & D")

    assert "A'B < C & D" not in script
    assert "A&#x27;B &lt; C &amp; D" in script


def test_notifier_has_no_broker_network_or_authority_import():
    source = __import__("inspect").getsource(notifier)
    forbidden = (
        "live_firewall",
        "execution.",
        "kalshi.",
        "httpx",
        "requests",
        "urlopen",
        "configs/",
        "operator_authority",
    )
    assert not any(token in source for token in forbidden)
