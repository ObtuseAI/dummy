"""Tests for the live ESPN-summary sportsbook odds."""
from __future__ import annotations

from autonomy.live_odds import EspnSummaryBook, devig_summary_home_probability


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
    assert EspnSummaryBook(fetch_summary=lambda l, e: _summary(-150, 130)).home_win_probability(None) is None


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
