"""Tests for MLB injury/availability awareness."""
from __future__ import annotations

from autonomy.sports.injuries import (
    InjuryBook,
    injury_burden,
    parse_team_injuries,
)


def _payload():
    return {"injuries": [
        {"displayName": "Arizona Diamondbacks", "injuries": [
            {"status": "Day-To-Day"}, {"status": "Out"},
            {"status": "60-Day-IL"}, {"status": "15-Day-IL"},  # long-term: ignored
        ]},
        {"displayName": "Texas Rangers", "injuries": [
            {"status": "60-Day-IL"},  # only long-term -> zero questionable
        ]},
    ]}


def test_parse_counts_only_short_term_availability():
    counts = parse_team_injuries(_payload())
    assert counts["arizonadiamondbacks"] == 2   # Day-To-Day + Out
    assert counts["texasrangers"] == 0           # IL excluded


def test_parse_none_and_empty_are_safe():
    assert parse_team_injuries(None) == {}
    assert parse_team_injuries({}) == {}


def test_injury_burden_is_bounded():
    assert injury_burden(0) == 0.0
    assert 0.0 < injury_burden(3) < 1.0
    assert injury_burden(6) == 1.0
    assert injury_burden(20) == 1.0  # saturates


def test_book_is_zero_until_refreshed_no_network():
    calls = []

    def fetch():
        calls.append(1)
        return _payload()

    book = InjuryBook(fetch_fn=fetch)
    # No implicit fetch: burden is zero and the feed is never hit until refresh.
    assert book.burden_for("Arizona Diamondbacks") == 0.0
    assert calls == []
    book.refresh()
    assert calls == [1]
    assert book.burden_for("Arizona Diamondbacks") > 0.0


def test_book_matches_by_normalized_name_and_is_fail_closed():
    book = InjuryBook(fetch_fn=_payload)
    book.refresh()
    assert book.burden_for("arizona diamondbacks") == book.burden_for("Arizona Diamondbacks")
    assert book.burden_for("Unknown Team") == 0.0     # unknown -> 0
    assert book.burden_for(None) == 0.0


def test_book_refresh_is_fail_closed_on_fetch_error():
    def boom():
        raise RuntimeError("espn down")
    book = InjuryBook(fetch_fn=boom)
    book.refresh()
    assert book.burden_for("Arizona Diamondbacks") == 0.0
