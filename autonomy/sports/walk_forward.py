"""Phase 4: walk-forward, point-in-time evaluation of the lake's rating models.

Replay a league's completed games in chronological rating periods. For each
game, predict the outcome using ONLY the ratings learned from strictly-earlier
periods (predict-before-update), then grade against what actually happened. The
result — Brier, hit-rate, log-loss, calibration, edge over a 0.5 coin flip — is
the honest measure of an analytic's edge and the number the recursive tuner
optimizes. No look-ahead: a game never informs its own prediction.

Pure, offline, deterministic. Reads the history lake; touches nothing live.
"""
from __future__ import annotations

import math
from typing import Any

from autonomy.sports.epa import LakeEpa
from autonomy.sports.four_factors import LakeFourFactors
from autonomy.sports.glicko import LakeGlickoRatings
from autonomy.sports.history_store import SportsHistoryStore
from autonomy.sports.mov_elo import LakeMovElo
from autonomy.sports.pythagorean import LakePythagorean
from autonomy.sports.scoring_model import LakeScoringModel

_BASELINE_BRIER = 0.25          # always-predict-0.5


def _grade(preds: list[tuple[float, int]]) -> dict[str, Any]:
    n = len(preds)
    if n == 0:
        return {"n": 0, "brier": None, "hit_rate": None, "log_loss": None,
                "baseline_brier": _BASELINE_BRIER, "edge_vs_baseline": None}
    brier = sum((p - y) ** 2 for p, y in preds) / n
    hits = sum(1 for p, y in preds if (p >= 0.5) == (y == 1))
    eps = 1e-12
    log_loss = -sum(
        y * math.log(min(1 - eps, max(eps, p))) + (1 - y) * math.log(min(1 - eps, max(eps, 1 - p)))
        for p, y in preds
    ) / n
    return {
        "n": n,
        "brier": round(brier, 5),
        "hit_rate": round(hits / n, 5),
        "log_loss": round(log_loss, 5),
        "baseline_brier": _BASELINE_BRIER,
        "edge_vs_baseline": round(_BASELINE_BRIER - brier, 5),
    }


def walk_forward_glicko(
    store: SportsHistoryStore, league: str, *,
    home_advantage: float = 40.0, period_key: str = "day", warmup_periods: int = 1,
) -> dict[str, Any]:
    """Grade Glicko-2 point-in-time over a league's completed games.

    ``warmup_periods`` skips grading the first N periods (ratings are still cold
    priors) but still learns from them — so the score reflects the model once it
    has some information, not its cold start.
    """
    games = store.games(league=league)
    games = [g for g in games if g.get("home_score") is not None and g.get("away_score") is not None]
    periods = LakeGlickoRatings.group_periods(games, period_key)

    ratings = LakeGlickoRatings(store, league=league)
    preds: list[tuple[float, int]] = []
    for i, period in enumerate(periods):
        if i >= warmup_periods:
            for game in period:
                home, away = game.get("home"), game.get("away")
                hs, as_ = game.get("home_score"), game.get("away_score")
                if not home or not away or hs == as_:      # skip ties for a binary grade
                    continue
                p_home = ratings.matchup_prob(home, away, home_advantage=home_advantage)
                preds.append((p_home, 1 if hs > as_ else 0))
        ratings.apply_period(period)                        # only now does the period inform ratings

    report = _grade(preds)
    report["league"] = league
    report["periods"] = len(periods)
    return report


def walk_forward_pythagorean(
    store: SportsHistoryStore, league: str, *,
    home_advantage_prob: float = 0.03, min_games: int = 3,
) -> dict[str, Any]:
    """Grade Pythagenpat point-in-time. Predict each game only once both teams
    have ``min_games`` of prior scoring history (cold strengths are ~0.5)."""
    games = store.games(league=league)
    games = [g for g in games if g.get("home_score") is not None and g.get("away_score") is not None]
    games.sort(key=lambda g: g["start_time"])

    model = LakePythagorean(store, league=league)
    preds: list[tuple[float, int]] = []
    for game in games:
        home, away = game.get("home"), game.get("away")
        hs, as_ = game.get("home_score"), game.get("away_score")
        if home and away and hs != as_ and model.games_seen(home) >= min_games and model.games_seen(away) >= min_games:
            p_home = model.matchup_prob(home, away, home_advantage_prob=home_advantage_prob)
            preds.append((p_home, 1 if hs > as_ else 0))
        model.apply_game(game)

    report = _grade(preds)
    report["league"] = league
    report["model"] = "pythagenpat"
    return report


def walk_forward_mov_elo(
    store: SportsHistoryStore, league: str, *,
    home_advantage: float = 40.0, k: float = 20.0, warmup_games: int = 30,
) -> dict[str, Any]:
    """Grade MOV-Elo point-in-time (predict each game before applying it)."""
    games = store.games(league=league)
    games = [g for g in games if g.get("home_score") is not None and g.get("away_score") is not None]
    games.sort(key=lambda g: g["start_time"])

    model = LakeMovElo(store, league=league, k=k, home_advantage=home_advantage)
    preds: list[tuple[float, int]] = []
    for i, game in enumerate(games):
        home, away = game.get("home"), game.get("away")
        hs, as_ = game.get("home_score"), game.get("away_score")
        if i >= warmup_games and home and away and hs != as_:
            preds.append((model.matchup_prob(home, away), 1 if hs > as_ else 0))
        model.apply_game(game)

    report = _grade(preds)
    report["league"] = league
    report["model"] = "mov_elo"
    return report


def walk_forward_four_factors(
    store: SportsHistoryStore, league: str, *,
    home_advantage_prob: float = 0.03, min_games: int = 5,
) -> dict[str, Any]:
    """Grade Four Factors point-in-time. Predicts a game only once both teams
    have ``min_games`` of prior boxscores (the store enforces the as-of cut)."""
    games = store.games(league=league)
    games = [g for g in games if g.get("home_score") is not None and g.get("away_score") is not None]
    games.sort(key=lambda g: g["start_time"])

    model = LakeFourFactors(store, league=league)
    preds: list[tuple[float, int]] = []
    for game in games:
        home, away, t = game.get("home"), game.get("away"), game["start_time"]
        hs, as_ = game.get("home_score"), game.get("away_score")
        if not home or not away or hs == as_:
            continue
        if model.games_seen(home, t) < min_games or model.games_seen(away, t) < min_games:
            continue
        p = model.matchup_prob(home, away, t, home_advantage_prob=home_advantage_prob)
        if p is not None:
            preds.append((p, 1 if hs > as_ else 0))

    report = _grade(preds)
    report["league"] = league
    report["model"] = "four_factors"
    return report


def walk_forward_scoring(
    store: SportsHistoryStore, league: str, *, min_games: int = 5,
) -> dict[str, Any]:
    """Grade the expected-margin/total model point-in-time: winner probability
    from P(margin > 0), plus the mean absolute error of the predicted margin and
    total (the numbers spreads/totals actually settle on)."""
    games = store.games(league=league)
    games = [g for g in games if g.get("home_score") is not None and g.get("away_score") is not None]
    games.sort(key=lambda g: g["start_time"])

    model = LakeScoringModel(store, league=league)
    preds: list[tuple[float, int]] = []
    margin_err: list[float] = []
    total_err: list[float] = []
    for game in games:
        home, away, t = game.get("home"), game.get("away"), game["start_time"]
        hs, as_ = game.get("home_score"), game.get("away_score")
        if not home or not away:
            continue
        rh, ra = model._rates(home, t), model._rates(away, t)
        if rh is None or ra is None or rh[2] < min_games or ra[2] < min_games:
            continue
        exp = model.expected_scores(home, away, t)
        if exp is None:
            continue
        margin_err.append(abs((exp[0] - exp[1]) - (hs - as_)))
        total_err.append(abs((exp[0] + exp[1]) - (hs + as_)))
        if hs != as_:
            p = model.p_home_covers(home, away, t, 0.0)
            if p is not None:
                preds.append((p, 1 if hs > as_ else 0))

    report = _grade(preds)
    report["league"] = league
    report["model"] = "scoring"
    report["margin_mae"] = round(sum(margin_err) / len(margin_err), 3) if margin_err else None
    report["total_mae"] = round(sum(total_err) / len(total_err), 3) if total_err else None
    return report


def walk_forward_epa(store: SportsHistoryStore, league: str = "nfl", *, min_games: int = 4) -> dict[str, Any]:
    """Grade EPA/play point-in-time (predict each game before it is played)."""
    games = store.games(league=league)
    games = [g for g in games if g.get("home_score") is not None and g.get("away_score") is not None]
    games.sort(key=lambda g: g["start_time"])
    model = LakeEpa(store, league=league)
    preds: list[tuple[float, int]] = []
    for game in games:
        home, away, t = game.get("home"), game.get("away"), game["start_time"]
        hs, as_ = game.get("home_score"), game.get("away_score")
        if not home or not away or hs == as_:
            continue
        if model.games_seen(home, t) < min_games or model.games_seen(away, t) < min_games:
            continue
        p = model.matchup_prob(home, away, t)
        if p is not None:
            preds.append((p, 1 if hs > as_ else 0))
    report = _grade(preds)
    report["league"] = league
    report["model"] = "epa"
    return report
