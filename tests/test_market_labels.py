"""Human-readable market labels: raw tickers -> "SD vs ATL · 1st-inning run"."""
from __future__ import annotations

import autonomy.market_labels as ml


def _teams(monkeypatch):
    monkeypatch.setattr(ml, "_team_sets", lambda: {
        "mlb": frozenset({"SD", "ATL", "NYY", "BOS", "BAL", "PIT", "CIN", "SEA"}),
        "wnba": frozenset({"CONN", "PHX", "NYL", "LV"}),
    })
    ml.humanize_ticker.cache_clear() if hasattr(ml.humanize_ticker, "cache_clear") else None


def test_matchup_split_and_market_phrase(monkeypatch):
    _teams(monkeypatch)
    cases = {
        "KXMLBRFI-26JUL211915SDATL": "SD vs ATL · 1st-inning run",
        "KXWNBA2HTOTAL-26JUL19CONNPHX-76": "CONN vs PHX · 2H total 76",
        "KXMLBF5TOTAL-26JUL201910BALBOS-3": "BAL vs BOS · 1st 5 total 3",
        "KXMLBGAME-26JUL19NYYBOS-NYY": "NYY vs BOS · winner (NYY)",
        "KXMLBSPREAD-26JUL201905PITNYY-NYY3": "PIT vs NYY · spread 3",
        "KXMLBTEAMTOTAL-26JUL202140CINSEA-CIN4": "CIN vs SEA · team total (CIN) 4",
        "KXWNBA1HWINNER-26JUL17CONNPHX-TIE": "CONN vs PHX · 1H winner (tie)",
    }
    for ticker, expected in cases.items():
        assert ml.market_label(ticker) == expected, ticker


def test_pieces_are_populated(monkeypatch):
    _teams(monkeypatch)
    h = ml.humanize_ticker("KXWNBA2HTOTAL-26JUL19CONNPHX-76")
    assert h["matchup"] == "CONN vs PHX"
    assert h["market"] == "2H total 76"
    assert h["date"] == "Jul 19"
    assert h["event_date"] == "2026-07-19"
    assert h["event_id"] == "26JUL19CONNPHX"
    assert h["line"] == "76"


def test_unknown_teams_fall_back_to_raw_token_never_raises(monkeypatch):
    # A league with no team set -> the matchup is the raw token, not a crash,
    # and the market phrase still resolves from the registry.
    monkeypatch.setattr(ml, "_team_sets", lambda: {})
    h = ml.humanize_ticker("KXMLBGAME-26JUL19NYYBOS-NYY")
    assert h["matchup"] == "NYYBOS"          # unsplit, but present
    assert h["market"] == "winner (NYY)"     # still readable
    # a totally unknown ticker never blanks out
    assert ml.market_label("GARBAGE") == "GARBAGE"


def test_crypto_ticker_has_no_matchup_but_never_crashes(monkeypatch):
    _teams(monkeypatch)
    # crypto isn't in the sports registry -> label falls back to the raw ticker
    lbl = ml.market_label("KXBTCD-26JUL1922-B64350")
    assert isinstance(lbl, str) and lbl


def test_prop_title_preserves_player_and_threshold(monkeypatch):
    _teams(monkeypatch)
    h = ml.humanize_market(
        "KXMLBHIT-26JUL211910BALBOS-BALPALONSO25-1",
        "Pete Alonso: 1+ hits?",
    )
    assert h["subject"] == "Pete Alonso"
    assert h["subject_team"] == "BAL"
    assert h["market"] == "Pete Alonso · 1+ hits"
    assert h["label"] == "BAL vs BOS · Pete Alonso · 1+ hits"


def test_prop_without_title_uses_ticker_player_abbreviation(monkeypatch):
    _teams(monkeypatch)
    h = ml.humanize_market("KXMLBHIT-26JUL211910BALBOS-BALPALONSO25-1")
    assert h["subject"] == "P Alonso"
    assert h["subject_team"] == "BAL"
    assert h["market"] == "P Alonso · 1+ hits"


def test_compound_ticker_player_abbreviation_is_readable(monkeypatch):
    _teams(monkeypatch)
    h = ml.humanize_market(
        "KXMLBHIT-26JUL221540CINSEA-CINEDELACRUZ44-3"
    )
    assert h["subject"] == "E De La Cruz"
    assert h["subject_team"] == "CIN"


def test_recommend_side_is_unambiguous_per_market():
    from autonomy.market_labels import recommend_side

    # Winner
    assert recommend_side("KXMLBGAME-26JUL26LADNYM-NYM", "yes") == "NYM to win"
    assert recommend_side("KXMLBGAME-26JUL26LADNYM-NYM", "no") == "NYM NOT to win"
    # Total over/under
    assert recommend_side("KXMLBTOTAL-26JUL26LADNYM-T8", "yes").startswith("OVER")
    assert recommend_side("KXMLBTOTAL-26JUL26LADNYM-T8", "no").startswith("UNDER")
    # YRFI as YES / NO (with NRFI clarification)
    assert recommend_side("KXMLBRFI-26JUL26LADNYM", "yes") == "YES — a run in the 1st"
    assert recommend_side("KXMLBRFI-26JUL26LADNYM", "no") == "NO — no run in the 1st (NRFI)"
    # Unknown side -> None
    assert recommend_side("KXMLBRFI-26JUL26LADNYM", None) is None
    assert recommend_side("KXMLBRFI-26JUL26LADNYM", "") is None
