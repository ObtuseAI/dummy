"""Tests for the live ESPN-summary sportsbook odds."""
from __future__ import annotations

import json
from pathlib import Path

from autonomy.live_odds import (
    EspnSummaryBook,
    devig_summary_home_probability,
    parse_base_out_state,
    parse_ejection_events,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _summary(home_ml, away_ml, books=2):
    book = {"homeTeamOdds": {"moneyLine": home_ml}, "awayTeamOdds": {"moneyLine": away_ml}}
    return {"pickcenter": [dict(book) for _ in range(books)]}


def test_devig_summary_removes_vig_and_averages_books():
    # -150 home / +130 away -> de-vigged home ~0.58.
    p = devig_summary_home_probability(_summary(-150, 130))
    assert p is not None
    assert abs(p - (0.60 / (0.60 + 100.0 / 230.0))) < 1e-6
    assert 0.5 < p < 0.62


def test_devig_summary_none_without_pickcenter():
    assert devig_summary_home_probability({}) is None
    assert devig_summary_home_probability(None) is None
    assert devig_summary_home_probability({"pickcenter": [{}]}) is None


def test_summary_book_provider_returns_home_prob():
    book = EspnSummaryBook(fetch_summary=lambda lg, eid: _summary(-150, 130))
    p = book.home_win_probability("401234")
    assert p is not None and 0.5 < p < 0.62


def test_summary_book_provider_fail_closed():
    def boom(_lg, _eid):
        raise RuntimeError("espn down")
    assert EspnSummaryBook(fetch_summary=boom).home_win_probability("x") is None
    # No event id -> None, no fetch.
    assert EspnSummaryBook(
        fetch_summary=lambda _league, _event: _summary(-150, 130)
    ).home_win_probability(None) is None


def test_summary_book_caches_per_event():
    calls = []

    def fetch(_lg, eid):
        calls.append(eid)
        return _summary(-150, 130)

    book = EspnSummaryBook(fetch_summary=fetch)
    book.home_win_probability("g1")
    book.home_win_probability("g1")
    assert calls == ["g1"]  # cached
    book.clear()
    book.home_win_probability("g1")
    assert calls == ["g1", "g1"]


def test_parse_ejection_events_reads_point_in_time_play_fields():
    summary = {"plays": [{
        "id": "40158567750",
        "sequenceNumber": "50",
        "type": {"id": "517", "text": "Ejection"},
        "text": "Draymond Green ejected",
        "awayScore": 6,
        "homeScore": 6,
        "period": {"number": 1, "displayValue": "1st Quarter"},
        "clock": {"displayValue": "8:24"},
        "team": {"id": "9"},
        "participants": [{"athlete": {"id": "6589"}}],
        "wallclock": "2024-03-27T23:17:20Z",
    }]}

    events = parse_ejection_events(summary)

    assert len(events) == 1
    assert events[0] == {
        "event_type": "ejection",
        "source": "espn_summary_plays",
        "play_id": "40158567750",
        "sequence_number": "50",
        "source_event_time": "2024-03-27T23:17:20Z",
        "text": "Draymond Green ejected",
        "team_id": "9",
        "participant_ids": ("6589",),
        "period": 1,
        "clock": "8:24",
        "home_score": 6,
        "away_score": 6,
    }


def test_parse_ejections_ignores_postgame_article_and_malformed_plays():
    summary = {
        "article": {"story": "A manager was ejected after arguing."},
        "plays": [None, "bad", {"type": {"text": "Pitch"}, "text": "called strike"}],
    }
    assert parse_ejection_events(summary) == ()
    assert parse_ejection_events(None) == ()


def test_summary_book_ejection_events_reuse_the_cached_summary():
    calls = []

    def fetch(league, event_id):
        calls.append((league, event_id))
        return {"plays": [{"id": "1", "type": {"text": "Ejection"}, "text": "Player ejected"}]}

    book = EspnSummaryBook(league="nba", fetch_summary=fetch)
    assert book.home_win_probability("g1") is None
    assert len(book.ejection_events("g1")) == 1
    assert book.ejection_events(None) == ()
    assert calls == [("nba", "g1")]


# -- WS-11: live base-out state (plays[].onFirst/onSecond/onThird + outs) --

def test_parse_base_out_state_none_without_plays():
    assert parse_base_out_state(None) is None
    assert parse_base_out_state({}) is None
    assert parse_base_out_state({"plays": []}) is None


def test_parse_base_out_state_reads_runners_and_outs_from_last_play():
    # Bases loaded, 0 outs, as the (only, thus last) play in the list.
    summary = {"plays": [
        {"outs": 0, "onFirst": {"athlete": {"id": "1"}},
         "onSecond": {"athlete": {"id": "2"}}, "onThird": {"athlete": {"id": "3"}}},
    ]}
    assert parse_base_out_state(summary) == ("loaded", 0)


def test_parse_base_out_state_empty_bases_key_absence_not_boolean_false():
    # ESPN omits onFirst/onSecond/onThird entirely when a base is empty --
    # confirmed by the WS-11 probe (event 401816130). A play with no runner
    # keys at all must parse to "empty", not error.
    summary = {"plays": [{"outs": 1}]}
    assert parse_base_out_state(summary) == ("empty", 1)


def test_parse_base_out_state_unparseable_outs_is_none():
    assert parse_base_out_state({"plays": [{"onFirst": {}}]}) is None  # no "outs"
    assert parse_base_out_state({"plays": [{"outs": 3}]}) == ("empty", 3)  # 3 is valid int, just not in RE24


def test_parse_base_out_state_from_probed_live_fixture():
    """WS-11 build-time probe fixture: event 401816130 (MIL @ PIT, 2026-07-12),
    trimmed from the real ESPN summary endpoint. See autonomy/live_odds.py's
    module docstring for the full probe writeup (no live "in" game was in
    progress at probe time; keys were confirmed via a completed game's
    ``plays`` array instead, which carries the identical per-play schema)."""
    fixture = json.loads((FIXTURES / "mlb_summary_401816130_baseout.json").read_text())
    plays = fixture["plays"]

    # Each representative play parses to the expected (base_state, outs).
    assert parse_base_out_state({"plays": [plays[0]]}) == ("empty", 0)   # start-inning
    assert parse_base_out_state({"plays": [plays[1]]}) == ("1st", 1)     # runner on first
    assert parse_base_out_state({"plays": [plays[2]]}) == ("loaded", 0)  # bases loaded
    assert parse_base_out_state({"plays": [plays[3]]}) == ("empty", 2)   # 2 outs, empty

    # parse_base_out_state always reads the LAST play (the current state);
    # this fixture's last recorded play happens to be the game's final out
    # (outs=3), which is honestly outside the RE24 table's domain (0/1/2)
    # and is fail-closed to a 0.0 adjustment by base_out_delta.
    assert parse_base_out_state(fixture) == ("empty", 3)
