"""Best-effort sports CLV backfill (Wave-2 workstream D1).

Exercises the pure reconstruction core with an injected start resolver (no
ESPN network) plus the grader propagating the ``backfilled`` flag.
"""
from __future__ import annotations

import json
import sys

from autonomy.clv import build_clv_report
from autonomy.sports.espn import Game

import scripts.run_dummy_sports_clv_backfill as backfill
from scripts.run_dummy_sports_clv_backfill import (
    EspnStartResolver,
    build_backfilled_tape,
    reconstruct_closes,
)

TICKER = "KXMLBGAME-26JUL102005HOUTEX-HOU"
START = "2026-07-10T20:05:00+00:00"


def _tape(ticker, ts, book_prob, kalshi_mid, close_time="2026-07-11T04:00:00+00:00"):
    return {"ticker": ticker, "ts": ts, "book_prob": book_prob,
            "kalshi_mid": kalshi_mid, "close_time": close_time}


def test_reconstruct_picks_last_pregame_snapshot_within_window():
    rows = [
        _tape(TICKER, "2026-07-10T14:00:00+00:00", 0.60, 0.58),  # 6h out
        _tape(TICKER, "2026-07-10T20:00:00+00:00", 0.66, 0.63),  # 5 min pre -> the close
        _tape(TICKER, "2026-07-10T20:30:00+00:00", 0.90, 0.88),  # in-play -> ignored
    ]
    out = reconstruct_closes(rows, lambda t: START)
    assert len(out) == 1
    assert out[0]["book_prob"] == 0.66
    assert out[0]["close_time"] == START
    assert out[0]["backfilled"] is True


def test_reconstruct_fail_closed_when_start_unresolved():
    rows = [_tape(TICKER, "2026-07-10T20:00:00+00:00", 0.66, 0.63)]
    assert reconstruct_closes(rows, lambda t: None) == []


def test_reconstruct_fail_closed_when_no_snapshot_in_window():
    rows = [_tape(TICKER, "2026-07-10T18:00:00+00:00", 0.66, 0.63)]  # ~2h out
    assert reconstruct_closes(rows, lambda t: START) == []


def test_reconstruct_skips_snapshot_missing_book_prob():
    rows = [
        _tape(TICKER, "2026-07-10T20:00:00+00:00", None, 0.63),
        _tape(TICKER, "2026-07-10T19:50:00+00:00", 0.64, 0.62),  # 15 min pre, has book
    ]
    out = reconstruct_closes(rows, lambda t: START)
    assert out[0]["book_prob"] == 0.64


def test_build_backfilled_tape_drops_original_sports_rows_keeps_crypto():
    crypto = _tape("KXBTCD-26JUL1218-T71000", "2026-07-12T17:50:00+00:00", 0.61, 0.59,
                   close_time="2026-07-12T18:00:00+00:00")
    sports = _tape(TICKER, "2026-07-10T20:00:00+00:00", 0.66, 0.63)
    sports_live = _tape(TICKER, "2026-07-10T20:30:00+00:00", 0.90, 0.88)

    def resolver(t):
        return START if t == TICKER else None

    grader_tape, reconstructed = build_backfilled_tape(
        [crypto, sports, sports_live], resolver,
    )
    tickers_close = {(r["ticker"], r["close_time"]) for r in grader_tape}
    # Crypto row passes through untouched; the reconstructed sports close
    # (anchored on game start) replaces BOTH original sports rows.
    assert ("KXBTCD-26JUL1218-T71000", "2026-07-12T18:00:00+00:00") in tickers_close
    assert (TICKER, START) in tickers_close
    assert (TICKER, "2026-07-11T04:00:00+00:00") not in tickers_close  # game-end row gone
    assert len(reconstructed) == 1


def test_backfilled_flag_flows_through_grader_into_report():
    reconstructed = reconstruct_closes(
        [_tape(TICKER, "2026-07-10T20:00:00+00:00", 0.66, 0.63)], lambda t: START,
    )
    entry = {"ticker": TICKER, "side": "YES", "entry_kalshi_prob": 0.55,
             "source": "mlb", "market_type": "winner"}
    report = build_clv_report([entry], reconstructed, now_iso="2026-07-10T22:00:00+00:00")
    scope = report["scopes"]["mlb|winner"]
    assert scope["n_entries"] == 1
    assert scope["n_backfilled_entries"] == 1  # honest disclosure of approximation


# -- ESPN start resolver (injected fake client, no network) -------------------

class _FakeEspn:
    def __init__(self, game):
        self._game = game

    def find_matchup(self, league, a, b, dates=None):
        return self._game

    def find_matchup_names(self, league, a, b, dates=None):
        return self._game


def test_espn_start_resolver_winner_from_ticker():
    game = Game(game_id="1", league="mlb", home="TEX", away="HOU", status="pre",
                home_won=None, date=START)
    resolver = EspnStartResolver(espn_factory=lambda: _FakeEspn(game))
    assert resolver(TICKER) == START


def test_espn_start_resolver_fail_closed_on_unparseable_ticker():
    resolver = EspnStartResolver(espn_factory=lambda: _FakeEspn(None))
    assert resolver("KXBTCD-26JUL1218-T71000") is None  # crypto, not a sports contract
    assert resolver("garbage") is None


def test_main_writes_grader_ready_tape(tmp_path, monkeypatch):
    in_path = tmp_path / "book_tape.jsonl"
    out_path = tmp_path / "backfill.jsonl"
    rows = [
        _tape("KXBTCD-26JUL1218-T71000", "2026-07-12T17:50:00+00:00", 0.61, 0.59,
              close_time="2026-07-12T18:00:00+00:00"),
        _tape(TICKER, "2026-07-10T20:00:00+00:00", 0.66, 0.63),
    ]
    in_path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    # Deterministic resolver in place of the live ESPN one.
    monkeypatch.setattr(backfill, "EspnStartResolver",
                        lambda: (lambda t: START if t == TICKER else None))
    monkeypatch.setattr(sys, "argv",
                        ["backfill", "--tape", str(in_path), "--out", str(out_path)])
    assert backfill.main() == 0

    written = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines() if line]
    by_ticker = {r["ticker"]: r for r in written}
    assert by_ticker["KXBTCD-26JUL1218-T71000"]["close_time"] == "2026-07-12T18:00:00+00:00"
    assert by_ticker[TICKER]["close_time"] == START
    assert by_ticker[TICKER]["backfilled"] is True
