"""Wave-31: the Odds API budget rebalance -- a raised, env-tunable daily cap,
a game-line reservation props cannot exhaust, and a monthly plan guard."""
from __future__ import annotations

from autonomy.odds_api_budget import LINE_CLASS, OddsApiBudget


def _budget(tmp_path, **kw):
    return OddsApiBudget(
        budget_path=tmp_path / "budget.json",
        cache_dir=tmp_path / "cache",
        archive_dir=tmp_path / "archive",
        now_fn=lambda: 1_000_000.0,
        **kw)


def test_line_class_spends_full_cap_props_yield_the_reserve(tmp_path):
    b = _budget(tmp_path, daily_credits=100, line_reserve=40, monthly_credits=10_000)
    b.record_spend(60)                                   # props consume their ceiling
    # A prop fetch is now blocked (60 + 10 > 100 - 40), but a game-line fetch
    # still has the reserved 40 to spend.
    assert not b.can_spend(10, "prop")
    assert not b.can_spend(10, "other")                  # default class == prop ceiling
    assert b.can_spend(10, LINE_CLASS)
    assert b.can_spend(40, LINE_CLASS) and not b.can_spend(41, LINE_CLASS)


def test_env_overrides_daily_reserve_and_monthly(tmp_path, monkeypatch):
    monkeypatch.setenv("DUMMY_ODDS_DAILY_CREDITS", "800")
    monkeypatch.setenv("DUMMY_ODDS_LINE_RESERVE", "300")
    monkeypatch.setenv("DUMMY_ODDS_MONTHLY_CREDITS", "25000")
    b = _budget(tmp_path)                                # no explicit args -> env
    assert b.daily_credits == 800 and b.line_reserve == 300 and b.monthly_credits == 25_000
    # garbage env falls back to the default, never crashes
    monkeypatch.setenv("DUMMY_ODDS_DAILY_CREDITS", "not-a-number")
    assert _budget(tmp_path).daily_credits == 640


def test_monthly_cap_guards_the_plan(tmp_path):
    b = _budget(tmp_path, daily_credits=640, line_reserve=0, monthly_credits=100)
    b.record_spend(95)
    assert b.can_spend(5, LINE_CLASS) and not b.can_spend(6, LINE_CLASS)  # month, not day


def test_reserve_is_clamped_below_the_cap(tmp_path):
    b = _budget(tmp_path, daily_credits=100, line_reserve=250)
    assert b.line_reserve == 100                         # clamped
    assert not b.can_spend(1, "prop")                    # prop ceiling collapses to 0
    assert b.can_spend(100, LINE_CLASS)


def test_line_fetch_survives_prop_exhaustion(tmp_path):
    b = _budget(tmp_path, daily_credits=100, line_reserve=40, monthly_credits=10_000)
    calls = {"n": 0}

    def _fetch():
        calls["n"] += 1
        return [{"ok": True}], None

    # Exhaust the prop ceiling (60) with prop-class fetches.
    for i in range(20):
        b.budgeted_fetch(f"props|{i}", _fetch, cost=3, ttl=0.0)
    spent_props = b.status()["spent_today"]
    assert spent_props <= 60                              # props stopped at their ceiling
    # A game-line fetch still goes live -- the reserve protected the feed.
    payload, source = b.budgeted_fetch("odds|mlb", _fetch, cost=3, ttl=0.0,
                                       reserve_class=LINE_CLASS)
    assert source == "live" and payload == [{"ok": True}]


def test_status_reports_reserve_and_monthly(tmp_path):
    b = _budget(tmp_path, daily_credits=640, line_reserve=256, monthly_credits=20_000)
    b.record_spend(100)
    s = b.status()
    assert s["daily_credits"] == 640 and s["line_reserve"] == 256
    assert s["prop_remaining"] == 640 - 256 - 100
    assert s["monthly_remaining"] == 20_000 - 100
