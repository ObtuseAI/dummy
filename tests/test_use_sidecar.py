"""Wave-22: the Universal Sports Engine sidecar bridge + challenger signal."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.use_sim import UseSimSignal
from autonomy.sports.espn import Game
from autonomy.sports.team_scores import TeamScoreModel
from autonomy.use_bridge import (
    LEAGUE_TO_USE,
    append_outcomes,
    load_predictions,
    team_strengths,
)

NOW = datetime(2026, 7, 18, 16, 0, tzinfo=timezone.utc)


def _row(league="mlb", home="NYY", away="BOS", p_home=0.58,
         total=8.9, total_sd=4.1, margin=0.6, margin_sd=3.9):
    return {
        "league": league, "home": home, "away": away,
        "home_win_probability": p_home,
        "total_mean": total, "total_sd": total_sd,
        "margin_mean": margin, "margin_sd": margin_sd,
        "home_mean": (total + margin) / 2, "away_mean": (total - margin) / 2,
        "provenance": "reference_ensemble",
    }


def _rows(*rows):
    return {f"{r['league']}|{r['home']}|{r['away']}": r for r in rows}


def _market(ticker, title, **raw):
    payload = {"event_ticker": ticker.rsplit("-", 1)[0], **raw}
    return MarketView(
        ticker=ticker, title=title, vertical=Vertical.SPORTS, status="open",
        close_time=(NOW + timedelta(hours=6)).isoformat(),
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56,
        volume=500, liquidity=1_000, raw=payload,
    )


def _signal(rows):
    signal = UseSimSignal(predictions_loader=lambda: rows)
    signal.on_cycle_start()
    return signal


def test_signal_prices_winner_total_spread_team_total():
    signal = _signal(_rows(_row()))

    winner = signal.generate(_market(
        "KXMLBGAME-26JUL18NYYBOS-NYY", "Yankees vs Red Sox Winner?"))
    assert winner is not None
    assert winner.source == "use_sim_mlb"
    assert winner.probability_yes == 0.58
    assert winner.features["challenger_only"] is True

    away_side = signal.generate(_market(
        "KXMLBGAME-26JUL18NYYBOS-BOS", "Yankees vs Red Sox Winner?"))
    assert abs(away_side.probability_yes - 0.42) < 1e-9

    total = signal.generate(_market(
        "KXMLBTOTAL-26JUL18NYYBOS-T85", "Yankees vs Red Sox Total?",
        floor_strike=8.5))
    assert total is not None and total.source == "use_sim_mlb"
    assert 0.5 < total.probability_yes < 0.6      # mean 8.9 vs line 8.5

    spread = signal.generate(_market(
        "KXMLBSPREAD-26JUL18NYYBOS-NYY15", "Yankees vs Red Sox Spread?",
        floor_strike=1.5))
    assert spread is not None
    assert spread.probability_yes < 0.5           # margin mean 0.6 < 1.5

    team_total = signal.generate(_market(
        "KXMLBTEAMTOTAL-26JUL18NYYBOS-NYY45", "Will NYY score over 4.5?",
        floor_strike=4.5))
    assert team_total is not None
    assert 0.3 < team_total.probability_yes < 0.7


def test_signal_prices_segments_via_share_tables():
    signal = _signal(_rows(_row(
        league="wnba", home="LVA", away="NYL",
        total=165.0, total_sd=13.0, margin=4.0, margin_sd=11.5)))
    h1 = signal.generate(_market(
        "KXWNBA1HTOTAL-26JUL18LVANYL-T80",
        "Aces vs Liberty: First Half Total?", floor_strike=80.5))
    assert h1 is not None and h1.source == "use_sim_wnba"
    assert 0.4 < h1.probability_yes < 0.6         # 165*0.49 ~ 80.9 vs 80.5


def test_signal_inert_without_artifact_and_fail_closed_on_unmatched():
    empty = _signal({})
    market = _market("KXMLBGAME-26JUL18NYYBOS-NYY", "Yankees vs Red Sox Winner?")
    assert empty.applicable(market) is False
    assert empty.generate(market) is None

    unmatched = _signal(_rows(_row(home="HOU", away="TEX")))
    assert unmatched.generate(market) is None


def test_bridge_strengths_center_on_one(tmp_path):
    model = TeamScoreModel("wnba")
    final = Game("w0", "wnba", "LVA", "NYL", "post", True, "2026-07-15T23:00Z",
                 home_score=95, away_score=70)
    model.update(final)
    strengths = team_strengths("wnba", model=model)
    assert strengths["LVA"] > 1.0 > strengths["NYL"]
    assert abs(team_strengths("wnba", model=TeamScoreModel("wnba")).get("X", 1.0) - 1.0) < 1e-9


def test_outcomes_tape_appends_and_dedupes(tmp_path):
    path = tmp_path / "use_outcomes.jsonl"
    finals = {"mlb": [Game(
        "g1", "mlb", "NYY", "BOS", "post", True, "2026-07-18T00:00Z",
        home_score=5, away_score=3)]}
    assert append_outcomes(finals, path=path) == 1
    assert append_outcomes(finals, path=path) == 0       # dedupe by game_id
    record = json.loads(path.read_text().strip())
    assert record["home_score"] == 5 and record["league"] == "mlb"
    assert record["home_strength"] >= 0.0


def test_load_predictions_freshness_gate(tmp_path):
    path = tmp_path / "use_predictions.json"
    fresh = {"generated_at": datetime.now(timezone.utc).isoformat(),
             "status": "OK", "rows": [_row()]}
    path.write_text(json.dumps(fresh), encoding="utf-8")
    assert len(load_predictions(path)) == 1

    stale = dict(fresh)
    stale["generated_at"] = (
        datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    path.write_text(json.dumps(stale), encoding="utf-8")
    assert load_predictions(path) == {}

    absent_engine = dict(fresh)
    absent_engine["status"] = "ENGINE_ABSENT"
    path.write_text(json.dumps(absent_engine), encoding="utf-8")
    assert load_predictions(path) == {}


def test_taxonomy_and_league_map():
    from autonomy.taxonomy import specialist_for

    for league in LEAGUE_TO_USE:
        assert specialist_for(f"use_sim_{league}") == league
    assert specialist_for("use_sim") == "use_sim"
