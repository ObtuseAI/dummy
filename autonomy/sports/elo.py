"""League-agnostic Elo with home advantage and persistence.

Ratings start at 1500 and diverge as real results replay through the model.
Per-league K-factor and home edge (NBA teams show a much larger home effect
than MLB) come from the config table. Win probability is the standard
logistic on the rating gap plus the home bump.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BASE_RATING = 1500.0
SCALE = 400.0

# (K-factor, home-advantage Elo points) tuned to published per-sport figures.
LEAGUE_PARAMS: dict[str, tuple[float, float]] = {
    "nba": (20.0, 100.0),
    "wnba": (20.0, 90.0),
    "nfl": (20.0, 55.0),
    "mlb": (6.0, 24.0),
    "nhl": (8.0, 50.0),
}


# Starting-pitcher adjustment (baseball). A team's probable starter shifts its
# effective rating by its ERA edge over league average — an ace is worth real
# Elo, a struggling starter costs it. Scale is deliberately moderate (the
# bullpen and offense still decide much of the game) and the learner tunes the
# source's overall trust weight from realized settlements.
LEAGUE_AVG_ERA = 4.10
PITCHER_ELO_PER_ERA = 30.0
PITCHER_ELO_CLAMP = 75.0


def pitcher_elo_adjustment(era: float | None) -> float:
    """Elo points a probable starter adds (lower ERA = better = positive)."""
    if era is None or era <= 0:
        return 0.0
    adj = PITCHER_ELO_PER_ERA * (LEAGUE_AVG_ERA - era)
    return max(-PITCHER_ELO_CLAMP, min(PITCHER_ELO_CLAMP, adj))


def win_probability(rating_a: float, rating_b: float) -> float:
    """P(A beats B) with the home bump already folded into rating_a."""
    return 1.0 / (1.0 + math.pow(10.0, (rating_b - rating_a) / SCALE))


@dataclass
class EloModel:
    league: str
    ratings: dict[str, float] = field(default_factory=dict)
    games_seen: int = 0
    processed_game_ids: set[str] = field(default_factory=set)

    @property
    def _params(self) -> tuple[float, float]:
        return LEAGUE_PARAMS.get(self.league, (20.0, 60.0))

    def rating(self, team: str) -> float:
        return self.ratings.get(team, BASE_RATING)

    def home_edge(self) -> float:
        return self._params[1]

    def predict(self, home_team: str, away_team: str, neutral: bool = False) -> float:
        """P(home_team wins). neutral=True drops the home bump."""
        bump = 0.0 if neutral else self.home_edge()
        return win_probability(self.rating(home_team) + bump, self.rating(away_team))

    def predict_team(
        self,
        subject: str,
        opponent: str,
        subject_home: bool | None,
        subject_pitcher_era: float | None = None,
        opponent_pitcher_era: float | None = None,
    ) -> float:
        """P(subject wins), folding in home edge and starting-pitcher ERA.

        Pitcher terms default to None (no adjustment), so non-baseball callers
        and existing tests are unaffected.
        """
        subj = self.rating(subject) + pitcher_elo_adjustment(subject_pitcher_era)
        opp = self.rating(opponent) + pitcher_elo_adjustment(opponent_pitcher_era)
        bump = self.home_edge()
        if subject_home is True:
            subj += bump
        elif subject_home is False:
            opp += bump
        return win_probability(subj, opp)

    def update(self, home_team: str, away_team: str, home_won: bool, game_id: str | None = None) -> None:
        """Apply one completed result. Idempotent per game_id."""
        if game_id is not None:
            if game_id in self.processed_game_ids:
                return
            self.processed_game_ids.add(game_id)
        k, bump = self._params
        expected_home = win_probability(self.rating(home_team) + bump, self.rating(away_team))
        outcome_home = 1.0 if home_won else 0.0
        delta = k * (outcome_home - expected_home)
        self.ratings[home_team] = self.rating(home_team) + delta
        self.ratings[away_team] = self.rating(away_team) - delta
        self.games_seen += 1

    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "league": self.league,
            "ratings": self.ratings,
            "games_seen": self.games_seen,
            "processed_game_ids": sorted(self.processed_game_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EloModel":
        return cls(
            league=data.get("league", ""),
            ratings={k: float(v) for k, v in data.get("ratings", {}).items()},
            games_seen=int(data.get("games_seen", 0)),
            processed_game_ids=set(data.get("processed_game_ids", [])),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load(cls, league: str, path: Path) -> "EloModel":
        if path.exists():
            try:
                return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                pass
        return cls(league=league)
