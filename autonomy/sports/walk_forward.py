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
from datetime import datetime
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
                "baseline_brier": _BASELINE_BRIER, "edge_vs_baseline": None,
                "ece": None, "mce": None}
    brier = sum((p - y) ** 2 for p, y in preds) / n
    hits = sum(1 for p, y in preds if (p >= 0.5) == (y == 1))
    eps = 1e-12
    log_loss = -sum(
        y * math.log(min(1 - eps, max(eps, p))) + (1 - y) * math.log(min(1 - eps, max(eps, 1 - p)))
        for p, y in preds
    ) / n
    bins: list[list[tuple[float, int]]] = [[] for _ in range(10)]
    for probability, outcome in preds:
        bins[min(9, int(probability * 10))].append((probability, outcome))
    weighted_gaps: list[float] = []
    raw_gaps: list[float] = []
    for bucket in bins:
        if not bucket:
            continue
        confidence = sum(item[0] for item in bucket) / len(bucket)
        frequency = sum(item[1] for item in bucket) / len(bucket)
        gap = abs(confidence - frequency)
        raw_gaps.append(gap)
        weighted_gaps.append(gap * len(bucket) / n)
    return {
        "n": n,
        "brier": round(brier, 5),
        "hit_rate": round(hits / n, 5),
        "log_loss": round(log_loss, 5),
        "baseline_brier": _BASELINE_BRIER,
        "edge_vs_baseline": round(_BASELINE_BRIER - brier, 5),
        "ece": round(sum(weighted_gaps), 5),
        "mce": round(max(raw_gaps), 5) if raw_gaps else None,
    }


def _timestamp(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"naive timestamp is not point-in-time safe: {value!r}")
    return parsed


def _training_available_at(game: dict[str, Any]) -> datetime:
    """The result is usable only after both publication and local receipt."""
    return max(_timestamp(game["result_available_at"]), _timestamp(game["received_at"]))


def _replay_batches(
    games: list[dict[str, Any]],
) -> list[tuple[int, list[dict[str, Any]], list[dict[str, Any]]]]:
    """Decision batches paired with results safely released before each batch.

    Games sharing a start timestamp are predicted from the same frozen state.
    A result whose receipt overlaps a later game's start remains pending, even
    when the earlier game itself has already started or finished.
    """
    ordered = sorted(games, key=lambda game: (game["start_time"], str(game["game_id"])))
    by_start: dict[str, list[dict[str, Any]]] = {}
    for game in ordered:
        by_start.setdefault(str(game["start_time"]), []).append(game)
    pending = sorted(
        ordered,
        key=lambda game: (
            _training_available_at(game), game["start_time"], str(game["game_id"]),
        ),
    )
    cursor = 0
    released_ids: set[str] = set()
    batches: list[tuple[int, list[dict[str, Any]], list[dict[str, Any]]]] = []
    for decision_index, (start_time, batch) in enumerate(by_start.items()):
        decision_at = _timestamp(start_time)
        newly_released: list[dict[str, Any]] = []
        while cursor < len(pending) and _training_available_at(pending[cursor]) < decision_at:
            prior = pending[cursor]
            cursor += 1
            game_id = str(prior["game_id"])
            if game_id not in released_ids:
                released_ids.add(game_id)
                newly_released.append(prior)
        batches.append((decision_index, batch, newly_released))
    return batches


def glicko_prediction_records(
    store: SportsHistoryStore, league: str, *, home_advantage: float = 40.0,
    games: list[dict[str, Any]] | None = None,
    score_game_ids: set[str] | None = None,
    include_training_ids: bool = False,
) -> list[dict[str, Any]]:
    """Availability-ordered Glicko predictions with an auditable training set."""
    eligible = list(games) if games is not None else store.evaluation_games(league=league)
    ratings = LakeGlickoRatings(store, league=league)
    records: list[dict[str, Any]] = []
    for decision_index, batch, newly_released in _replay_batches(eligible):
        if newly_released:
            ratings.apply_period(newly_released)
        training_count = len(ratings._seen)
        for game in batch:
            game_id = str(game["game_id"])
            if score_game_ids is not None and game_id not in score_game_ids:
                continue
            home, away = game.get("home"), game.get("away")
            home_score, away_score = game.get("home_score"), game.get("away_score")
            if not home or not away or home_score == away_score:
                continue
            records.append({
                "game_id": game_id,
                "season": game.get("season"),
                "decision_at": game["start_time"],
                "probability": ratings.matchup_prob(
                    home, away, home_advantage=home_advantage
                ),
                "outcome": 1 if home_score > away_score else 0,
                "training_count": training_count,
                **({"training_game_ids": sorted(ratings._seen)}
                   if include_training_ids else {}),
                "decision_period_index": decision_index,
            })
    return records


def walk_forward_glicko(
    store: SportsHistoryStore, league: str, *,
    home_advantage: float = 40.0, period_key: str = "day", warmup_periods: int = 1,
) -> dict[str, Any]:
    """Grade Glicko-2 point-in-time over a league's completed games.

    ``warmup_periods`` skips grading the first N periods (ratings are still cold
    priors) but still learns from them — so the score reflects the model once it
    has some information, not its cold start.
    """
    games = store.evaluation_games(league=league)
    records = glicko_prediction_records(
        store, league, home_advantage=home_advantage, games=games,
    )
    records = [
        record for record in records
        if int(record["decision_period_index"]) >= warmup_periods
    ]
    preds = [(float(row["probability"]), int(row["outcome"])) for row in records]

    report = _grade(preds)
    report["league"] = league
    report["periods"] = len({row["decision_period_index"] for row in records})
    report["point_in_time_policy"] = "result_and_receipt_strictly_before_decision"
    eligibility = store.evaluation_eligibility(league=league)
    report["eligible_games"] = eligibility["eligible"]
    report["excluded_games"] = eligibility["excluded"]
    report["exclusion_reasons"] = eligibility["rejection_reasons"]
    return report


def walk_forward_pythagorean(
    store: SportsHistoryStore, league: str, *,
    home_advantage_prob: float = 0.03, min_games: int = 3,
) -> dict[str, Any]:
    """Grade Pythagenpat point-in-time. Predict each game only once both teams
    have ``min_games`` of prior scoring history (cold strengths are ~0.5)."""
    games = store.evaluation_games(league=league)
    model = LakePythagorean(store, league=league)
    preds: list[tuple[float, int]] = []
    for _decision_index, batch, newly_released in _replay_batches(games):
        for prior in newly_released:
            model.apply_game(prior)
        for game in batch:
            home, away = game.get("home"), game.get("away")
            hs, as_ = game.get("home_score"), game.get("away_score")
            if home and away and hs != as_ and model.games_seen(home) >= min_games and model.games_seen(away) >= min_games:
                p_home = model.matchup_prob(home, away, home_advantage_prob=home_advantage_prob)
                preds.append((p_home, 1 if hs > as_ else 0))

    report = _grade(preds)
    report["league"] = league
    report["model"] = "pythagenpat"
    return report


def walk_forward_mov_elo(
    store: SportsHistoryStore, league: str, *,
    home_advantage: float = 40.0, k: float = 20.0, warmup_games: int = 30,
) -> dict[str, Any]:
    """Grade MOV-Elo point-in-time (predict each game before applying it)."""
    games = store.evaluation_games(league=league)
    model = LakeMovElo(store, league=league, k=k, home_advantage=home_advantage)
    preds: list[tuple[float, int]] = []
    applied_games = 0
    for _decision_index, batch, newly_released in _replay_batches(games):
        for prior in newly_released:
            model.apply_game(prior)
            applied_games += 1
        for game in batch:
            home, away = game.get("home"), game.get("away")
            hs, as_ = game.get("home_score"), game.get("away_score")
            if applied_games >= warmup_games and home and away and hs != as_:
                preds.append((model.matchup_prob(home, away), 1 if hs > as_ else 0))

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
    games = store.evaluation_games(league=league)

    model = LakeFourFactors(store, league=league, require_known_availability=True)
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
    games = store.evaluation_games(league=league)

    model = LakeScoringModel(store, league=league, require_known_availability=True)
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
    games = store.evaluation_games(league=league)
    model = LakeEpa(store, league=league, require_known_availability=True)
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
