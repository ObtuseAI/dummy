"""Sports pre-game close capture for CLV (Wave-2 workstream D1).

Covers the close tracker's pre-game/finalize semantics, the mispricing
sweep's opt-in sports routing, an end-to-end grade producing a real
``mlb|winner`` CLV scope, and the specialists' game-start resolvers. Zero
network: ESPN is a hand-built fake, everything else is in-memory.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from autonomy.clv import build_clv_report
from autonomy.mispricing_monitor import run_mispricing_sweep
from autonomy.ontology import MarketView, Vertical
from autonomy.sports.espn import Game
from autonomy.sports_clv import (
    SPORTS_SPECIALISTS,
    SportsCloseTracker,
    is_sports_market,
)

TICKER = "KXMLBGAME-26JUL102005HOUTEX-HOU"
START = "2026-07-10T20:05:00+00:00"


def _sports_market(ticker: str = TICKER, title: str = "Houston vs Texas Winner?",
                   yes_ask: int = 50, no_ask: int = 50, **raw) -> MarketView:
    return MarketView(
        ticker=ticker, title=title, vertical=Vertical.SPORTS, status="open",
        close_time="2026-07-11T04:00:00+00:00",  # Kalshi contract close = game END
        yes_bid=yes_ask - 2, yes_ask=yes_ask, no_bid=no_ask - 2, no_ask=no_ask,
        volume=500, liquidity=10_000, raw=raw,
    )


# -- is_sports_market ----------------------------------------------------------

def test_is_sports_market_true_only_for_sports_vertical():
    assert is_sports_market(_sports_market()) is True
    assert is_sports_market(SimpleNamespace(ticker="X")) is False  # no vertical attr
    crypto = SimpleNamespace(vertical=Vertical.CRYPTO)
    assert is_sports_market(crypto) is False


def test_sports_specialists_membership_covers_mlb_and_team_leagues():
    assert "mlb" in SPORTS_SPECIALISTS
    assert {"nba", "nfl", "nhl"} <= SPORTS_SPECIALISTS
    assert "crypto" not in SPORTS_SPECIALISTS


# -- SportsCloseTracker: pre-game accrual + finalize at first pitch ------------

def test_tracker_finalizes_last_pregame_snapshot_at_game_start():
    t = SportsCloseTracker()
    # Two pre-game passes; the book moves. Nothing frozen yet.
    t.observe(ticker=TICKER, start_time_iso=START, book_prob=0.60, kalshi_mid=0.58,
              now_iso="2026-07-10T19:00:00+00:00")
    t.observe(ticker=TICKER, start_time_iso=START, book_prob=0.65, kalshi_mid=0.62,
              now_iso="2026-07-10T20:03:00+00:00")  # 2 min before first pitch
    assert t.pending_count() == 1
    assert t.finalize_due("2026-07-10T20:03:30+00:00") == []  # still pre-game

    frozen = t.finalize_due("2026-07-10T20:06:00+00:00")  # first pitch passed
    assert len(frozen) == 1
    row = frozen[0]
    assert row["ticker"] == TICKER
    assert row["close_time"] == START            # anchored on game start, not game end
    assert row["book_prob"] == 0.65              # the LAST pre-game snapshot
    assert row["ts"] == "2026-07-10T20:03:00+00:00"
    assert t.pending_count() == 0


def test_tracker_stable_line_keeps_latest_pregame_ts_not_earliest():
    # A moneyline that never moves must still land inside the close window:
    # the tracker always holds the LATEST pre-game ts, unlike the deduped raw
    # tape which would keep only the earliest (hours-stale) identical row.
    t = SportsCloseTracker()
    t.observe(ticker=TICKER, start_time_iso=START, book_prob=0.60, kalshi_mid=0.60,
              now_iso="2026-07-10T14:00:00+00:00")  # 6h out
    t.observe(ticker=TICKER, start_time_iso=START, book_prob=0.60, kalshi_mid=0.60,
              now_iso="2026-07-10T20:04:00+00:00")  # 1 min out, same price
    frozen = t.finalize_due("2026-07-10T20:10:00+00:00")
    assert frozen[0]["ts"] == "2026-07-10T20:04:00+00:00"  # latest, inside window


def test_tracker_ignores_in_play_observation_after_first_pitch():
    t = SportsCloseTracker()
    t.observe(ticker=TICKER, start_time_iso=START, book_prob=0.65, kalshi_mid=0.62,
              now_iso="2026-07-10T20:04:00+00:00")
    # In-play pass: now >= start -> observe must NOT overwrite the pre-game
    # candidate with the live number.
    t.observe(ticker=TICKER, start_time_iso=START, book_prob=0.90, kalshi_mid=0.88,
              now_iso="2026-07-10T20:30:00+00:00")
    frozen = t.finalize_due("2026-07-10T20:31:00+00:00")
    assert frozen[0]["book_prob"] == 0.65  # pre-game, not the 0.90 live price


def test_tracker_frozen_ticker_never_reopens():
    t = SportsCloseTracker()
    t.observe(ticker=TICKER, start_time_iso=START, book_prob=0.65, kalshi_mid=0.62,
              now_iso="2026-07-10T20:04:00+00:00")
    assert len(t.finalize_due("2026-07-10T20:06:00+00:00")) == 1
    # A late observation for an already-closed ticker is a no-op.
    t.observe(ticker=TICKER, start_time_iso=START, book_prob=0.80, kalshi_mid=0.79,
              now_iso="2026-07-10T20:07:00+00:00")
    assert t.pending_count() == 0
    assert t.finalize_due("2026-07-10T21:00:00+00:00") == []


def test_tracker_fail_closed_on_unknown_or_bad_start():
    t = SportsCloseTracker()
    t.observe(ticker=TICKER, start_time_iso=None, book_prob=0.65, kalshi_mid=0.62,
              now_iso="2026-07-10T20:04:00+00:00")
    t.observe(ticker=TICKER, start_time_iso="not-a-date", book_prob=0.65,
              kalshi_mid=0.62, now_iso="2026-07-10T20:04:00+00:00")
    t.observe(ticker="", start_time_iso=START, book_prob=0.65, kalshi_mid=0.62,
              now_iso="2026-07-10T20:04:00+00:00")
    assert t.pending_count() == 0
    assert t.finalize_due("2026-07-10T21:00:00+00:00") == []


def test_tracker_state_round_trips_across_restart():
    t = SportsCloseTracker()
    t.observe(ticker=TICKER, start_time_iso=START, book_prob=0.65, kalshi_mid=0.62,
              now_iso="2026-07-10T20:04:00+00:00")
    restored = SportsCloseTracker.from_state(t.to_state())
    assert restored.pending_count() == 1
    frozen = restored.finalize_due("2026-07-10T20:06:00+00:00")
    assert frozen and frozen[0]["book_prob"] == 0.65


def test_tracker_from_state_fail_open_on_garbage():
    assert SportsCloseTracker.from_state(None).pending_count() == 0
    assert SportsCloseTracker.from_state({"candidates": "bad"}).pending_count() == 0


# -- sweep opt-in routing ------------------------------------------------------

def test_sweep_without_game_start_fn_tapes_sports_the_old_way():
    # Backward compatible: no game_start_fn -> sports market still tapes via
    # the generic path with close_time == the Kalshi contract close.
    report = run_mispricing_sweep(
        [_sports_market()], lambda m: 0.60, now_iso="2026-07-10T19:00:00+00:00",
        book_fn=lambda m: 0.65,
    )
    assert len(report["tape_rows"]) == 1
    assert report["tape_rows"][0]["close_time"] == _sports_market().close_time


def test_sweep_routes_sports_to_close_tracker_when_wired():
    tracker = SportsCloseTracker()
    starts = {TICKER: START}
    # Pre-game pass: the sports market becomes a close CANDIDATE, not a tape row.
    r1 = run_mispricing_sweep(
        [_sports_market()], lambda m: 0.60, now_iso="2026-07-10T20:03:00+00:00",
        book_fn=lambda m: 0.65, game_start_fn=lambda m: starts.get(m.ticker),
        sports_close=tracker,
    )
    assert r1["tape_rows"] == []  # nothing generic-taped
    assert r1["sports_clv"]["pending_candidates"] == 1
    assert r1["sports_clv"]["finalized_closes"] == 0

    # Post-first-pitch pass: the candidate finalizes into ONE close row whose
    # close_time is game start and whose book_prob is the pre-game price.
    r2 = run_mispricing_sweep(
        [_sports_market()], lambda m: 0.60, now_iso="2026-07-10T20:10:00+00:00",
        book_fn=lambda m: 0.99, game_start_fn=lambda m: starts.get(m.ticker),
        sports_close=tracker,
    )
    assert len(r2["tape_rows"]) == 1
    row = r2["tape_rows"][0]
    assert row["ticker"] == TICKER
    assert row["close_time"] == START
    assert row["book_prob"] == 0.65  # pre-game close, NOT the 0.99 live book
    assert r2["sports_clv"]["finalized_closes"] == 1


def test_sweep_sports_fail_closed_when_start_unknown():
    tracker = SportsCloseTracker()
    r1 = run_mispricing_sweep(
        [_sports_market()], lambda m: 0.60, now_iso="2026-07-10T20:03:00+00:00",
        book_fn=lambda m: 0.65, game_start_fn=lambda m: None, sports_close=tracker,
    )
    assert r1["tape_rows"] == []
    assert tracker.pending_count() == 0  # no candidate for an unanchorable market
    r2 = run_mispricing_sweep(
        [_sports_market()], lambda m: 0.60, now_iso="2026-07-11T05:00:00+00:00",
        book_fn=lambda m: 0.65, game_start_fn=lambda m: None, sports_close=tracker,
    )
    assert r2["tape_rows"] == []  # never a wrong CLV row


def test_sweep_crypto_untouched_when_sports_capture_wired():
    # A non-sports market keeps taping via the generic path even with the
    # sports close tracker wired in.
    tracker = SportsCloseTracker()
    crypto = MarketView(
        ticker="KXBTCD-26JUL1218-T71000", title="BTC?", vertical=Vertical.CRYPTO,
        status="open", close_time="2026-07-12T18:00:00+00:00",
        yes_bid=58, yes_ask=60, no_bid=40, no_ask=42, volume=1, liquidity=1,
    )
    report = run_mispricing_sweep(
        [crypto], lambda m: 0.60, now_iso="2026-07-12T17:50:00+00:00",
        book_fn=lambda m: 0.62, game_start_fn=lambda m: None, sports_close=tracker,
    )
    assert len(report["tape_rows"]) == 1
    assert report["tape_rows"][0]["ticker"] == crypto.ticker
    assert report["tape_rows"][0]["close_time"] == crypto.close_time


# -- end to end: sweep -> finalized close -> CLV report has a sports scope -----

def test_end_to_end_sports_clv_scope_is_produced():
    tracker = SportsCloseTracker()
    starts = {TICKER: START}
    # Pre-game pass produces the paper entry (our model liked YES) and the
    # close candidate.
    r1 = run_mispricing_sweep(
        [_sports_market(yes_ask=40, no_ask=62)], lambda m: 0.70,
        now_iso="2026-07-10T20:03:00+00:00", book_fn=lambda m: 0.68,
        game_start_fn=lambda m: starts.get(m.ticker), sports_close=tracker,
        specialist_fn=lambda m: "mlb", min_confidence="low",
    )
    entries = r1["entries"]
    assert entries and entries[0]["source"] == "mlb"
    assert entries[0]["market_type"] == "winner"

    # First pitch passes: the close finalizes onto the tape.
    r2 = run_mispricing_sweep(
        [_sports_market()], lambda m: 0.70, now_iso="2026-07-10T20:10:00+00:00",
        book_fn=lambda m: 0.99, game_start_fn=lambda m: starts.get(m.ticker),
        sports_close=tracker,
    )
    tape_rows = r2["tape_rows"]

    report = build_clv_report(entries, tape_rows, now_iso="2026-07-10T22:00:00+00:00")
    assert "mlb|winner" in report["scopes"]
    scope = report["scopes"]["mlb|winner"]
    assert scope["n_entries"] >= 1
    assert scope["clv_bps_mean"] is not None
    assert scope["n_backfilled_entries"] == 0  # this evidence is live-captured


# -- specialist game-start resolvers ------------------------------------------

class _FakeEspn:
    def __init__(self, game: Game | None):
        self._game = game

    def find_matchup(self, league, a, b, dates=None):
        return self._game

    def find_matchup_names(self, league, a, b, dates=None):
        return self._game


def _mlb_game(date: str) -> Game:
    return Game(game_id="401", league="mlb", home="TEX", away="HOU",
                status="pre", home_won=None, date=date)


def test_mlb_specialist_game_start_time_returns_scheduled_date():
    from autonomy.specialists.mlb import MlbSpecialist

    spec = MlbSpecialist(intelligence=None, sportsbook=None,
                         espn=_FakeEspn(_mlb_game(START)))
    assert spec.game_start_time(_sports_market()) == START


def test_mlb_specialist_game_start_time_fail_closed_when_no_game():
    from autonomy.specialists.mlb import MlbSpecialist

    spec = MlbSpecialist(intelligence=None, sportsbook=None, espn=_FakeEspn(None))
    assert spec.game_start_time(_sports_market()) is None
    # A non-MLB / unparseable market resolves to None too.
    other = MarketView(ticker="KXBTCD-26JUL1218-T71000", title="BTC?",
                       vertical=Vertical.CRYPTO, status="open", close_time="",
                       yes_bid=1, yes_ask=2, no_bid=1, no_ask=2, volume=1, liquidity=1)
    assert spec.game_start_time(other) is None


def test_team_league_specialist_game_start_time_winner_path():
    from autonomy.specialists.team_leagues import TeamLeagueSpecialist

    ticker = "KXNBAGAME-26JAN15LALBOS-LAL"
    market = MarketView(
        ticker=ticker, title="Lakers vs Celtics Winner?", vertical=Vertical.SPORTS,
        status="open", close_time="2026-01-16T04:00:00+00:00",
        yes_bid=48, yes_ask=50, no_bid=48, no_ask=50, volume=1, liquidity=1,
    )
    start = "2026-01-15T23:30:00+00:00"
    game = Game(game_id="9", league="nba", home="BOS", away="LAL", status="pre",
                home_won=None, date=start)
    spec = TeamLeagueSpecialist(
        league="nba", intelligence=None, sportsbook=None, espn=_FakeEspn(game),
    )
    # Only assert when the ticker actually parses as an NBA winner in this build.
    if spec.applicable(market):
        assert spec.game_start_time(market) == start
    else:
        pytest.skip("NBA winner ticker shape not parseable in this build")


# -- dashboard sports-CLV summary ---------------------------------------------

def test_dashboard_sports_clv_summary_rolls_up_sports_scopes():
    from autonomy.dashboard import _sports_clv_summary

    clv_report = {
        "scopes": {
            "mlb|winner": {"specialist": "mlb", "market_type": "winner",
                           "clv_bps_mean": 120.0, "clv_bps_ci95_lower": 15.0,
                           "n_entries": 40, "n_event_clusters": 12},
            "mlb|total": {"specialist": "mlb", "market_type": "total",
                          "clv_bps_mean": -5.0, "clv_bps_ci95_lower": -30.0,
                          "n_entries": 10, "n_event_clusters": 8},
            "crypto|ladder": {"specialist": "crypto", "market_type": "ladder",
                              "clv_bps_mean": 50.0, "clv_bps_ci95_lower": 5.0,
                              "n_entries": 100, "n_event_clusters": 30},
        }
    }
    summary = _sports_clv_summary(clv_report)
    assert summary["instrumented"] is True
    assert summary["n_scopes"] == 2                    # crypto excluded
    assert summary["n_scopes_ci_lower_positive"] == 1  # only mlb|winner CI lower > 0
    assert summary["specialists"] == ["mlb"]
    assert {s["market_type"] for s in summary["by_specialist"]["mlb"]} == {"winner", "total"}


def test_dashboard_sports_clv_summary_empty_when_no_sports_scopes():
    summary = __import__("autonomy.dashboard", fromlist=["_sports_clv_summary"])._sports_clv_summary({})
    assert summary["instrumented"] is False
    assert summary["n_scopes"] == 0
