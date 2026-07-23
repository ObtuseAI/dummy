"""Referee / official tendency model for totals (challenger support).

Officials measurably shift game environment: an NBA crew that calls more fouls
lifts the total; an MLB home-plate umpire with a tight zone lifts runs. ESPN's
game summary exposes the assigned officials (``gameInfo.officials``). This
module aggregates, per referee, the average game total of the games they
worked, and exposes the crew's total delta versus the league baseline so a
challenger can nudge the scoring model's expected total.

Everything here is bounded, point-in-time-safe (aggregates are built only from
settled games), and fail-closed: an unknown crew or a referee with too few
games yields no adjustment.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

TENDENCIES_PATH = Path("runtime/autonomy/referee_tendencies.json")
ARTIFACT_VERSION = "referee_tendencies_v1"
MIN_REFEREE_GAMES = 25
# Clamp on the crew total delta (points for basketball, runs for baseball) so
# a noisy referee sample can never dominate the quantitative total model.
MAX_CREW_TOTAL_DELTA = {"nba": 6.0, "wnba": 6.0, "ncaamb": 6.0, "mlb": 1.2, "nhl": 1.0}
DEFAULT_MAX_DELTA = 4.0


def parse_officials(summary: dict[str, Any]) -> list[str]:
    """Referee full names from an ESPN game summary; [] when absent."""
    officials = ((summary or {}).get("gameInfo") or {}).get("officials") or []
    names: list[str] = []
    for official in officials:
        if not isinstance(official, dict):
            continue
        name = official.get("fullName") or official.get("displayName")
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return names


def summary_total(summary: dict[str, Any]) -> int | None:
    """Final combined score from an ESPN summary's header competitors."""
    competitions = ((summary or {}).get("header") or {}).get("competitions") or []
    if not competitions:
        return None
    competitors = (competitions[0] or {}).get("competitors") or []
    total = 0
    seen = 0
    for competitor in competitors:
        if not isinstance(competitor, dict):
            continue
        try:
            total += int(float(competitor.get("score")))
            seen += 1
        except (TypeError, ValueError):
            return None
    return total if seen == 2 else None


class RefereeTendencies:
    """Per-referee average game total, loaded from / saved to a JSON artifact."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else TENDENCIES_PATH
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        try:
            doc = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"artifact_version": ARTIFACT_VERSION, "leagues": {}}
        if not isinstance(doc, dict) or doc.get("artifact_version") != ARTIFACT_VERSION:
            return {"artifact_version": ARTIFACT_VERSION, "leagues": {}}
        return doc

    def observe(self, league: str, referees: list[str], game_total: int) -> int:
        """Fold one settled game's officials + total into the aggregates."""
        leagues = self._data.setdefault("leagues", {})
        block = leagues.setdefault(str(league).lower(), {"referees": {}, "league_total_sum": 0.0, "league_games": 0})
        recorded = 0
        for name in referees:
            ref = block["referees"].setdefault(name, {"games": 0, "total_sum": 0.0})
            ref["games"] += 1
            ref["total_sum"] += float(game_total)
            recorded += 1
        # The league baseline counts each GAME once (not once per referee).
        block["league_total_sum"] += float(game_total)
        block["league_games"] += 1
        return recorded

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(self._data, stream, indent=2, sort_keys=True)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def league_mean_total(self, league: str) -> float | None:
        block = (self._data.get("leagues") or {}).get(str(league).lower())
        if not block or not block.get("league_games"):
            return None
        return block["league_total_sum"] / block["league_games"]

    def referee_mean_total(self, league: str, name: str) -> float | None:
        block = (self._data.get("leagues") or {}).get(str(league).lower())
        ref = ((block or {}).get("referees") or {}).get(name)
        if not ref or ref.get("games", 0) < MIN_REFEREE_GAMES:
            return None
        return ref["total_sum"] / ref["games"]

    def crew_total_delta(self, league: str, crew: list[str]) -> dict[str, Any] | None:
        """Mean (referee mean total - league mean total) over qualified crew.

        Positive = an over-leaning crew. None when the league baseline is
        missing or no crew member has enough games (fail-closed).
        """
        baseline = self.league_mean_total(league)
        if baseline is None:
            return None
        deltas = []
        qualified = []
        for name in crew:
            mean = self.referee_mean_total(league, name)
            if mean is not None:
                deltas.append(mean - baseline)
                qualified.append(name)
        if not deltas:
            return None
        cap = MAX_CREW_TOTAL_DELTA.get(str(league).lower(), DEFAULT_MAX_DELTA)
        delta = sum(deltas) / len(deltas)
        return {
            "delta": round(max(-cap, min(cap, delta)), 4),
            "raw_delta": round(delta, 4),
            "league_mean_total": round(baseline, 3),
            "qualified_referees": qualified,
        }
