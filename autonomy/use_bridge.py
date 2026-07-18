"""Bridge to the Universal Sports Engine sidecar (Wave-22).

The operator's ``ObtuseAI/universal-sports-engine`` (USE) is a deterministic,
self-calibrating multi-league simulation engine with its OWN recursive
champion governance (bounded population search, prequential calibration,
drift quarantine, content-addressed champions). Integration verdict: fuse at
the EVIDENCE layer, run in parallel at the process layer. USE stays its own
repo and checkout, improving itself; dummy and USE couple through exactly
three artifacts:

  strengths OUT   dummy's warmed per-team EWMA state -> relative strengths
  predictions IN  USE's champion ensemble ForecastMoments per upcoming game
                  -> priced as a challenger source family (use_sim_<league>)
                  through dummy's unchanged two-door promotion ladder
  outcomes OUT    settled finals (the same scoreboard truth dummy's own
                  models warm on) -> USE's HistoricalGame training format,
                  so its recursive tuner + shadow calibration improve on the
                  exact games dummy graded

Fail-closed everywhere: sidecar absent -> no predictions artifact -> the
signal is inert; USE's drift quarantine refuses adaptive simulation -> the
sidecar falls back to its reference ensemble and says so in the artifact.
Neither system's governance can touch the other's.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autonomy.sports.espn import canonical_team
from autonomy.sports.team_scores import LEAGUE_SCORE_CONFIGS, TeamScoreModel

RUNTIME_DIR = Path("runtime/autonomy")
PREDICTIONS_PATH = RUNTIME_DIR / "use_predictions.json"
OUTCOMES_PATH = RUNTIME_DIR / "use_outcomes.jsonl"
ENGINE_PATH_ENV = "DUMMY_USE_ENGINE_PATH"
DEFAULT_ENGINE_PATH = Path(r"C:\src\engine\universal-sports-engine")

# dummy league key -> USE league pack key (USE uses sport-family league names).
LEAGUE_TO_USE: dict[str, str] = {
    "mlb": "mlb",
    "nba": "nba",
    "wnba": "wnba",
    "nfl": "nfl",
    "ncaaf": "ncaaf",
    "ncaamb": "ncaamb",
    "nhl": "nhl",
}

PREDICTION_FRESH_HOURS = 30.0


def engine_src() -> Path | None:
    """The sidecar's ``src`` dir, or None when the checkout is absent."""
    root = Path(os.environ.get(ENGINE_PATH_ENV) or DEFAULT_ENGINE_PATH)
    src = root / "src"
    return src if (src / "universal_sports_engine").exists() else None


def _ensure_engine_on_path() -> bool:
    src = engine_src()
    if src is None:
        return False
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    return True


def team_strengths(league: str, model: TeamScoreModel | None = None) -> dict[str, float]:
    """Relative team strengths from dummy's warmed EWMA state.

    Strength = blended scoring metric / league prior, so 1.0 is league
    average and the scale matches USE's strength-response exponents. A team
    with no games sits at exactly 1.0 (the prior).
    """
    if model is None and league not in LEAGUE_SCORE_CONFIGS:
        # No generic score model for this league (MLB runs its own run
        # model); neutral strengths until a per-league exporter is wired.
        return {}
    model = model or TeamScoreModel.load(
        league, Path("runtime/autonomy") / f"team_scores_{league}.json")
    prior = model.config.prior_team_score
    strengths: dict[str, float] = {}
    for team, state in model.teams.items():
        metric = model._metric(state, "score_for_ewma")
        strengths[canonical_team(league, team)] = (
            round(metric / prior, 4) if prior > 0 else 1.0)
    return strengths


def _moments_for(league: str, home_strength: float, away_strength: float):
    """USE champion ForecastMoments (reference ensemble until a tuned champion
    exists on disk -- the artifact discloses which)."""
    from universal_sports_engine.adaptive import (
        create_ensemble,
        ensemble_moments,
        reference_profile,
    )

    use_league = LEAGUE_TO_USE[league]
    profile = reference_profile(use_league)
    ensemble = create_ensemble(
        use_league, (profile,), (1.0,), "reference_anchor")
    moments = ensemble_moments(ensemble, (1.0,), home_strength, away_strength)
    return moments, "reference_ensemble"


def generate_predictions(
    games_by_league: dict[str, list[Any]],
    *,
    path: Path | None = None,
    now_iso: str | None = None,
) -> dict[str, Any]:
    """Price every upcoming matchup through USE; write the artifact.

    ``games_by_league`` maps a dummy league key to ESPN ``Game`` objects
    (status ``pre``). Returns the artifact payload (also written atomically).
    """
    if not _ensure_engine_on_path():
        payload = {
            "generated_at": now_iso or datetime.now(timezone.utc).isoformat(),
            "status": "ENGINE_ABSENT",
            "rows": [],
        }
        _write(path or PREDICTIONS_PATH, payload)
        return payload

    rows: list[dict[str, Any]] = []
    for league, games in games_by_league.items():
        if league not in LEAGUE_TO_USE:
            continue
        strengths = team_strengths(league)
        for game in games:
            if getattr(game, "status", None) != "pre":
                continue
            home = canonical_team(league, str(game.home))
            away = canonical_team(league, str(game.away))
            try:
                moments, provenance = _moments_for(
                    league,
                    strengths.get(home, 1.0),
                    strengths.get(away, 1.0),
                )
            except Exception as exc:
                rows.append({"league": league, "home": home, "away": away,
                             "error": f"{type(exc).__name__}: {exc}"[:120]})
                continue
            rows.append({
                "league": league,
                "home": home,
                "away": away,
                "date": getattr(game, "date", None),
                "game_id": getattr(game, "game_id", None),
                "home_win_probability": round(moments.home_win_probability, 4),
                "total_mean": round(moments.total_mean, 3),
                "total_sd": round(moments.total_sd, 3),
                "margin_mean": round(moments.margin_mean, 3),
                "margin_sd": round(moments.margin_sd, 3),
                "home_mean": round(moments.home_mean, 3),
                "away_mean": round(moments.away_mean, 3),
                "provenance": provenance,
            })
    payload = {
        "generated_at": now_iso or datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "rows": rows,
    }
    _write(path or PREDICTIONS_PATH, payload)
    return payload


def append_outcomes(
    finals_by_league: dict[str, list[Any]],
    *,
    path: Path | None = None,
) -> int:
    """Append settled finals in USE's HistoricalGame vocabulary (JSONL).

    Chronological accumulation is USE's training fuel; splits are assigned at
    tune time (chronological train/calibration/test), never here. Dedupes by
    (league, game_id) against the existing tail.
    """
    target = path or OUTCOMES_PATH
    seen: set[tuple[str, str]] = set()
    try:
        with target.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    record = json.loads(line)
                    seen.add((str(record.get("league")), str(record.get("game_id"))))
                except (ValueError, TypeError):
                    continue
    except OSError:
        pass

    appended = 0
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        for league, games in finals_by_league.items():
            if league not in LEAGUE_TO_USE:
                continue
            strengths = team_strengths(league)
            for game in games:
                if getattr(game, "status", None) != "post":
                    continue
                if game.home_score is None or game.away_score is None:
                    continue
                key = (league, str(game.game_id))
                if key in seen:
                    continue
                seen.add(key)
                fh.write(json.dumps({
                    "league": league,
                    "game_id": str(game.game_id),
                    "decision_time": getattr(game, "date", None),
                    "home": canonical_team(league, str(game.home)),
                    "away": canonical_team(league, str(game.away)),
                    "home_strength": strengths.get(canonical_team(league, str(game.home)), 1.0),
                    "away_strength": strengths.get(canonical_team(league, str(game.away)), 1.0),
                    "home_score": int(game.home_score),
                    "away_score": int(game.away_score),
                }, sort_keys=True) + "\n")
                appended += 1
    return appended


def load_predictions(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """{(league|HOME|AWAY): row} from a FRESH artifact; {} otherwise."""
    try:
        payload = json.loads((path or PREDICTIONS_PATH).read_text(encoding="utf-8"))
        generated = datetime.fromisoformat(str(payload.get("generated_at")))
        age_hours = (datetime.now(timezone.utc) - generated).total_seconds() / 3600.0
        if age_hours > PREDICTION_FRESH_HOURS or payload.get("status") != "OK":
            return {}
    except (OSError, ValueError, TypeError):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in payload.get("rows") or []:
        if not isinstance(row, dict) or "error" in row:
            continue
        out[f"{row.get('league')}|{row.get('home')}|{row.get('away')}"] = row
    return out


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True),
                         encoding="utf-8")
    temporary.replace(path)
