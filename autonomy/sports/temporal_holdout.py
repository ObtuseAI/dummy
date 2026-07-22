"""Research-only, one-shot temporal holdout gate for sports history.

The gate is intentionally separate from the recursive sports lab and executor.
It selects a fixed Glicko home-advantage candidate on a validation season, then
atomically consumes a later confirmed-complete season exactly once.  Holdout
outcomes never enter candidate selection and no result can train a prediction
until both its source-availability and local-receipt timestamps are strictly
earlier than that prediction's decision time.
"""
from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from autonomy.sports.history_store import SportsHistoryStore
from autonomy.sports.walk_forward import _grade, glicko_prediction_records

HOLDOUT_VERSION = "sports-temporal-holdout-v1"
DEFAULT_HOME_ADVANTAGE_CANDIDATES = (0.0, 20.0, 40.0, 60.0)


class HoldoutIntegrityError(RuntimeError):
    """Raised when a requested holdout would violate the sealed protocol."""


class HoldoutAlreadyConsumed(HoldoutIntegrityError):
    """Raised when code tries to inspect the same sealed holdout twice."""


def _game_ids_hash(games: Iterable[dict[str, Any]]) -> str:
    game_ids = sorted(str(game["game_id"]) for game in games)
    return hashlib.sha256("\n".join(game_ids).encode("utf-8")).hexdigest()


def _seal_key(league: str, season: int, holdout_ids_hash: str) -> str:
    material = f"{HOLDOUT_VERSION}|{league}|glicko|{season}|{holdout_ids_hash}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _split_summary(games: list[dict[str, Any]], seasons: list[int]) -> dict[str, Any]:
    ordered = sorted(games, key=lambda game: (game["start_time"], str(game["game_id"])))
    return {
        "seasons": seasons,
        "games": len(ordered),
        "game_ids_sha256": _game_ids_hash(ordered),
        "first_start": ordered[0]["start_time"] if ordered else None,
        "last_start": ordered[-1]["start_time"] if ordered else None,
    }


def _metrics(
    records: list[dict[str, Any]], *, bootstrap_samples: int = 1000, seed: int = 0,
) -> dict[str, Any]:
    """Grade rows and bootstrap whole dependency/event clusters.

    A sports event can emit multiple correlated records (for example, several
    market views of one game).  Those records must enter or leave a resample as
    a unit.  Explicit ``event_cluster``/``dependency_cluster`` identities take
    precedence; Glicko's one-row-per-game records safely fall back to
    ``game_id``.  Missing cluster identity is an integrity error rather than an
    invitation to pretend each row is independent.
    """
    predictions = [
        (float(record["probability"]), int(record["outcome"])) for record in records
    ]
    report = _grade(predictions)
    if not predictions:
        report["brier_ci95"] = {"lower": None, "upper": None}
        report["edge_vs_coin_ci95"] = {"lower": None, "upper": None}
        report["uncertainty"] = {
            "method": "dependency_event_cluster_bootstrap_95",
            "resampling_unit": "event_cluster",
            "event_clusters": 0,
            "correlated_records": 0,
            "resamples": 0,
        }
        return report
    clustered_briers: dict[str, list[float]] = {}
    for record, (probability, outcome) in zip(records, predictions, strict=True):
        cluster = next(
            (
                str(record[key]).strip()
                for key in ("event_cluster", "dependency_cluster", "game_id")
                if record.get(key) not in (None, "") and str(record[key]).strip()
            ),
            None,
        )
        if cluster is None:
            raise HoldoutIntegrityError(
                "uncertainty requires an event_cluster, dependency_cluster, or game_id"
            )
        clustered_briers.setdefault(cluster, []).append((probability - outcome) ** 2)
    aggregates = [
        (sum(values), len(values)) for values in clustered_briers.values() if values
    ]
    rng = random.Random(seed)
    briers: list[float] = []
    resamples = max(100, int(bootstrap_samples))
    for _ in range(resamples):
        total = 0.0
        count = 0
        for _cluster in aggregates:
            cluster_total, cluster_count = aggregates[rng.randrange(len(aggregates))]
            total += cluster_total
            count += cluster_count
        briers.append(total / count)
    briers.sort()
    lower = briers[int(0.025 * (len(briers) - 1))]
    upper = briers[int(0.975 * (len(briers) - 1))]
    report["brier_ci95"] = {"lower": round(lower, 6), "upper": round(upper, 6)}
    report["edge_vs_coin_ci95"] = {
        "lower": round(0.25 - upper, 6),
        "upper": round(0.25 - lower, 6),
    }
    report["uncertainty"] = {
        "method": "dependency_event_cluster_bootstrap_95",
        "resampling_unit": "event_cluster",
        "event_clusters": len(aggregates),
        "correlated_records": len(predictions),
        "resamples": resamples,
    }
    return report


def _base_report(
    *, league: str, holdout_season: int, generated_at: str,
    eligibility: dict[str, Any], artifact_path: Path,
) -> dict[str, Any]:
    return {
        "artifact_type": HOLDOUT_VERSION,
        "generated_at": generated_at,
        "league": league,
        "model": "glicko",
        "requested_holdout_season": int(holdout_season),
        "artifact_path": str(artifact_path),
        "research_only": True,
        "execution_authority": False,
        "capital_authority": False,
        "promotion_authority": False,
        "automatic_promotion": False,
        "live_authority_mutated": False,
        "point_in_time_policy": {
            "candidate_rows_require_result_available_at": True,
            "candidate_rows_require_received_at": True,
            "unknown_availability_excluded": True,
            "training_release_rule": "result_available_at_and_received_at_strictly_before_decision",
            "same_start_batch_is_frozen": True,
        },
        "data_quality": eligibility,
    }


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def run_temporal_holdout_gate(
    store: SportsHistoryStore, *, league: str, holdout_season: int,
    artifact_path: Path | str, confirm_completed_season: bool,
    candidate_home_advantages: Iterable[float] = DEFAULT_HOME_ADVANTAGE_CANDIDATES,
    generated_at: str | None = None, bootstrap_samples: int = 1000, seed: int = 0,
) -> dict[str, Any]:
    """Select on pre-holdout evidence and consume a sealed season once.

    ``confirm_completed_season`` is deliberately mandatory. Season completion
    differs by league and cannot be inferred safely from a few final rows.
    Blocked data-quality reports are written but do not consume the holdout.
    """
    if not confirm_completed_season:
        raise HoldoutIntegrityError(
            "holdout season must be explicitly confirmed complete before evaluation"
        )
    output = Path(artifact_path)
    stamp = generated_at or datetime.now(timezone.utc).isoformat()
    eligibility = store.evaluation_eligibility(league=league)
    report = _base_report(
        league=league, holdout_season=holdout_season, generated_at=stamp,
        eligibility=eligibility, artifact_path=output,
    )
    eligible = [
        game for game in store.evaluation_games(league=league)
        if game.get("season") is not None and int(game["season"]) <= int(holdout_season)
    ]
    seasons = sorted({int(game["season"]) for game in eligible})
    earlier_seasons = [season for season in seasons if season < int(holdout_season)]
    if int(holdout_season) not in seasons or len(earlier_seasons) < 2:
        report.update({
            "status": "BLOCKED_INSUFFICIENT_POINT_IN_TIME_SEASONS",
            "reason": (
                "strict evaluation needs a training season, a later validation season, "
                "and the explicitly confirmed holdout season"
            ),
            "available_strict_seasons": seasons,
            "sealed_holdout": {"consumed": False, "metrics": None},
        })
        _atomic_json(output, report)
        return report

    validation_season = earlier_seasons[-1]
    training_seasons = earlier_seasons[:-1]
    training = [game for game in eligible if int(game["season"]) in training_seasons]
    validation = [game for game in eligible if int(game["season"]) == validation_season]
    holdout = [game for game in eligible if int(game["season"]) == int(holdout_season)]
    train_ids = {str(game["game_id"]) for game in training}
    validation_ids = {str(game["game_id"]) for game in validation}
    holdout_ids = {str(game["game_id"]) for game in holdout}
    overlaps = {
        "train_validation": len(train_ids & validation_ids),
        "train_holdout": len(train_ids & holdout_ids),
        "validation_holdout": len(validation_ids & holdout_ids),
    }
    if any(overlaps.values()):
        raise HoldoutIntegrityError(f"temporal split reused game ids: {overlaps}")

    selection_games = training + validation
    candidate_reports: list[dict[str, Any]] = []
    candidates = sorted({float(value) for value in candidate_home_advantages})
    if not candidates:
        raise HoldoutIntegrityError("at least one validation candidate is required")
    for index, candidate in enumerate(candidates):
        records = glicko_prediction_records(
            store, league, home_advantage=candidate, games=selection_games,
            score_game_ids=validation_ids,
        )
        candidate_reports.append({
            "home_advantage": candidate,
            "metrics": _metrics(
                records, bootstrap_samples=bootstrap_samples, seed=seed + index,
            ),
        })
    viable = [item for item in candidate_reports if item["metrics"]["brier"] is not None]
    split = {
        "training": _split_summary(training, training_seasons),
        "validation": _split_summary(validation, [validation_season]),
        "holdout": _split_summary(holdout, [int(holdout_season)]),
        "overlap_counts": overlaps,
        "all_splits_disjoint": not any(overlaps.values()),
    }
    if not viable:
        report.update({
            "status": "BLOCKED_NO_VALIDATION_PREDICTIONS",
            "split": split,
            "candidate_selection": {"candidates": candidate_reports, "selected": None},
            "sealed_holdout": {"consumed": False, "metrics": None},
        })
        _atomic_json(output, report)
        return report

    selected = min(
        viable,
        key=lambda item: (
            float(item["metrics"]["brier"]), abs(float(item["home_advantage"])),
            float(item["home_advantage"]),
        ),
    )
    selection_hash = _game_ids_hash(selection_games)
    holdout_hash = _game_ids_hash(holdout)
    seal_key = _seal_key(league, int(holdout_season), holdout_hash)
    # Claim before any holdout prediction/metric is computed. A failed artifact
    # write burns the holdout rather than silently permitting another look.
    claimed = store.claim_research_holdout(
        seal_key=seal_key, league=league, holdout_season=int(holdout_season),
        model="glicko", holdout_ids_hash=holdout_hash,
        selection_ids_hash=selection_hash, consumed_at=stamp,
    )
    if not claimed:
        raise HoldoutAlreadyConsumed(
            f"sealed holdout already consumed for {league} season {holdout_season}"
        )

    holdout_records = glicko_prediction_records(
        store, league, home_advantage=float(selected["home_advantage"]),
        games=selection_games + holdout, score_game_ids=holdout_ids,
    )
    report.update({
        "status": "EVALUATED_RESEARCH_ONLY",
        "split": split,
        "candidate_selection": {
            "input_game_ids_sha256": selection_hash,
            "input_seasons": training_seasons + [validation_season],
            "holdout_season_present_in_selection": False,
            "candidates": candidate_reports,
            "selected": selected,
        },
        "sealed_holdout": {
            "season": int(holdout_season),
            "game_ids_sha256": holdout_hash,
            "seal_key": seal_key,
            "consumed": True,
            "one_shot": True,
            "used_for_candidate_selection": False,
            "selected_home_advantage": float(selected["home_advantage"]),
            "metrics": _metrics(
                holdout_records, bootstrap_samples=bootstrap_samples, seed=seed + 10_000,
            ),
        },
    })
    _atomic_json(output, report)
    return report
