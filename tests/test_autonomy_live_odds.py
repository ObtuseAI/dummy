"""Tests for the live ESPN-summary sportsbook odds."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from autonomy.live_odds import (
    EspnSummaryBook,
    devig_summary_home_probability,
    devig_summary_spread_probability,
    devig_summary_total_probability,
    parse_base_out_state,
    parse_ejection_events,
    project_summary_spread_probability,
    project_summary_total_probability,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _summary(home_ml, away_ml, books=2):
    book = {"homeTeamOdds": {"moneyLine": home_ml}, "awayTeamOdds": {"moneyLine": away_ml}}
    return {"pickcenter": [dict(book) for _ in range(books)]}


def _summary_with_lines(
    *, home_line=-1.5, home_odds=163, away_line=1.5, away_odds=-198,
    total_line=8.5, over_odds=-103, under_odds=-117,
):
    return {"pickcenter": [{
        "overUnder": total_line,
        "overOdds": over_odds,
        "underOdds": under_odds,
        "pointSpread": {
            "home": {"close": {"line": f"{home_line:+g}", "odds": f"{home_odds:+d}"}},
            "away": {"close": {"line": f"{away_line:+g}", "odds": f"{away_odds:+d}"}},
        },
    }]}


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


def test_devig_summary_total_requires_exact_line_and_two_sided_odds():
    summary = _summary_with_lines()
    expected = 103.0 / 203.0
    other = 117.0 / 217.0
    assert devig_summary_total_probability(summary, 8.5) == expected / (expected + other)
    assert devig_summary_total_probability(summary, 9.5) is None
    assert devig_summary_total_probability(
        {"pickcenter": [{"overUnder": 8.5, "overOdds": -110}]}, 8.5,
    ) is None


def test_devig_summary_total_averages_only_books_at_matching_line():
    first = _summary_with_lines(over_odds=-110, under_odds=-110)["pickcenter"][0]
    second = _summary_with_lines(over_odds=120, under_odds=-140)["pickcenter"][0]
    mismatched = _summary_with_lines(total_line=9.5, over_odds=-500, under_odds=300)["pickcenter"][0]
    p1 = devig_summary_total_probability({"pickcenter": [first]}, 8.5)
    p2 = devig_summary_total_probability({"pickcenter": [second]}, 8.5)
    assert devig_summary_total_probability(
        {"pickcenter": [first, second, mismatched]}, 8.5,
    ) == (p1 + p2) / 2.0


def test_devig_summary_spread_maps_kalshi_margin_to_subject_handicap():
    summary = _summary_with_lines()
    home = devig_summary_spread_probability(
        summary, subject_is_home=True, threshold=1.5,
    )
    assert home is not None and 0.30 < home < 0.45
    # Away is +1.5 in this book, which corresponds to "away wins by > -1.5".
    away = devig_summary_spread_probability(
        summary, subject_is_home=False, threshold=-1.5,
    )
    assert away is not None and abs(home + away - 1.0) < 1e-12
    assert devig_summary_spread_probability(
        summary, subject_is_home=False, threshold=1.5,
    ) is None


def test_devig_summary_spread_rejects_noncomplementary_or_one_sided_rows():
    malformed = _summary_with_lines(away_line=2.5)
    assert devig_summary_spread_probability(
        malformed, subject_is_home=True, threshold=1.5,
    ) is None
    one_sided = {"pickcenter": [{
        "pointSpread": {"home": {"close": {"line": "-1.5", "odds": "+160"}}},
    }]}
    assert devig_summary_spread_probability(
        one_sided, subject_is_home=True, threshold=1.5,
    ) is None


def test_summary_book_line_methods_reuse_cached_summary():
    calls = []

    def fetch(league, event_id):
        calls.append((league, event_id))
        return _summary_with_lines()

    book = EspnSummaryBook(league="mlb", fetch_summary=fetch)
    assert book.total_over_probability("g1", 8.5) is not None
    assert book.spread_cover_probability(
        "g1", subject_is_home=True, threshold=1.5,
    ) is not None
    assert book.total_over_probability(None, 8.5) is None
    assert calls == [("mlb", "g1")]


def test_alternate_total_projection_is_anchored_and_monotone():
    summary = _summary_with_lines(total_line=216.5, over_odds=-105, under_odds=-115)
    exact = devig_summary_total_probability(summary, 216.5)
    projected_exact = project_summary_total_probability(summary, 216.5, sigma=18.0)
    lower = project_summary_total_probability(summary, 210.5, sigma=18.0)
    higher = project_summary_total_probability(summary, 222.5, sigma=18.0)
    assert projected_exact == pytest.approx(exact)
    assert lower > exact > higher


def test_alternate_spread_projection_is_anchored_and_monotone():
    summary = _summary_with_lines(home_line=-3.5, away_line=3.5)
    exact = devig_summary_spread_probability(
        summary, subject_is_home=True, threshold=3.5)
    projected_exact = project_summary_spread_probability(
        summary, subject_is_home=True, threshold=3.5, sigma=12.0)
    easier = project_summary_spread_probability(
        summary, subject_is_home=True, threshold=1.5, sigma=12.0)
    harder = project_summary_spread_probability(
        summary, subject_is_home=True, threshold=7.5, sigma=12.0)
    assert projected_exact == pytest.approx(exact)
    assert easier > exact > harder


def test_summary_book_projects_unmatched_alt_lines_but_unknown_league_abstains():
    summary = _summary_with_lines(total_line=216.5, home_line=-3.5, away_line=3.5)
    nba = EspnSummaryBook(league="nba", fetch_summary=lambda _league, _event: summary)
    assert nba.total_over_probability("g1", 222.5) is not None
    assert nba.spread_cover_probability(
        "g1", subject_is_home=True, threshold=7.5) is not None
    unknown = EspnSummaryBook(league="unknown", fetch_summary=lambda _league, _event: summary)
    assert unknown.total_over_probability("g1", 222.5) is None


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
