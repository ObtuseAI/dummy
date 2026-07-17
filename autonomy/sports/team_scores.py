"""League-isolated score-distribution model for team-sport winners and totals."""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from autonomy.sports.espn import Game

MODEL_VERSION = "team-score-ewma-v1"


@dataclass(frozen=True)
class LeagueScoreConfig:
    prior_team_score: float
    home_edge_points: float
    total_sigma: float
    margin_sigma: float
    ewma_alpha: float = 0.08


LEAGUE_SCORE_CONFIGS = {
    "nba": LeagueScoreConfig(114.0, 3.0, 15.0, 12.0),
    "ncaamb": LeagueScoreConfig(72.0, 3.5, 13.0, 11.0),
    "nfl": LeagueScoreConfig(22.5, 2.0, 10.5, 10.0, 0.12),
    "ncaaf": LeagueScoreConfig(28.0, 3.0, 15.0, 14.0, 0.12),
    "nhl": LeagueScoreConfig(3.1, 0.18, 2.3, 2.0),
    # Wave-12: in-season mid-July, so evidence accrues immediately. ~82 points
    # per team in the current scoring environment; 44-game season -> a faster
    # EWMA than the NBA's 82-game 0.08 but slower than football's 0.12.
    "wnba": LeagueScoreConfig(82.0, 2.5, 13.0, 11.5, 0.10),
}


@dataclass
class TeamScoreState:
    games: int
    score_for_ewma: float
    score_against_ewma: float


@dataclass(frozen=True)
class TeamScorePrediction:
    home_win_probability: float
    expected_home_score: float
    expected_away_score: float
    expected_total: float
    total_sigma: float
    winner_uncertainty: float
    total_uncertainty: float
    sample_games: int
    league: str
    model_version: str = MODEL_VERSION


def normal_over_probability(mean: float, sigma: float, threshold: float) -> float:
    z = (threshold - mean) / max(0.25, sigma)
    cdf = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    return min(0.995, max(0.005, 1.0 - cdf))


@dataclass
class TeamScoreModel:
    league: str
    teams: dict[str, TeamScoreState] = field(default_factory=dict)
    processed_game_ids: set[str] = field(default_factory=set)
    games_seen: int = 0

    @property
    def config(self) -> LeagueScoreConfig:
        return LEAGUE_SCORE_CONFIGS[self.league]

    def _team(self, abbreviation: str) -> TeamScoreState:
        return self.teams.setdefault(abbreviation.upper(), TeamScoreState(
            games=0,
            score_for_ewma=self.config.prior_team_score,
            score_against_ewma=self.config.prior_team_score,
        ))

    def update(self, game: Game) -> bool:
        if (
            game.game_id in self.processed_game_ids
            or game.status != "post"
            or game.home_score is None
            or game.away_score is None
        ):
            return False
        home = self._team(game.home)
        away = self._team(game.away)
        alpha = self.config.ewma_alpha
        home.score_for_ewma = alpha * game.home_score + (1.0 - alpha) * home.score_for_ewma
        home.score_against_ewma = alpha * game.away_score + (1.0 - alpha) * home.score_against_ewma
        away.score_for_ewma = alpha * game.away_score + (1.0 - alpha) * away.score_for_ewma
        away.score_against_ewma = alpha * game.home_score + (1.0 - alpha) * away.score_against_ewma
        home.games += 1
        away.games += 1
        self.games_seen += 1
        self.processed_game_ids.add(game.game_id)
        return True

    def _metric(self, state: TeamScoreState, field_name: str) -> float:
        weight = min(0.85, state.games / 30.0)
        return (
            (1.0 - weight) * self.config.prior_team_score
            + weight * float(getattr(state, field_name))
        )

    def predict(self, game: Game) -> TeamScorePrediction:
        home = self._team(game.home)
        away = self._team(game.away)
        expected_home = 0.5 * (
            self._metric(home, "score_for_ewma") + self._metric(away, "score_against_ewma")
        ) + self.config.home_edge_points / 2.0
        expected_away = 0.5 * (
            self._metric(away, "score_for_ewma") + self._metric(home, "score_against_ewma")
        ) - self.config.home_edge_points / 2.0
        expected_home = max(0.1, expected_home)
        expected_away = max(0.1, expected_away)
        margin = expected_home - expected_away
        home_win = 0.5 * (
            1.0 + math.erf(margin / (self.config.margin_sigma * math.sqrt(2.0)))
        )
        sample = min(home.games, away.games)
        cold = 1.0 / math.sqrt(1.0 + sample / 8.0)
        return TeamScorePrediction(
            home_win_probability=min(0.98, max(0.02, home_win)),
            expected_home_score=expected_home,
            expected_away_score=expected_away,
            expected_total=expected_home + expected_away,
            total_sigma=self.config.total_sigma,
            winner_uncertainty=min(0.42, 0.09 + 0.22 * cold),
            total_uncertainty=min(0.44, 0.12 + 0.22 * cold),
            sample_games=sample,
            league=self.league,
        )

    def total_probability(self, prediction: TeamScorePrediction, threshold: float) -> float:
        return normal_over_probability(
            prediction.expected_total, prediction.total_sigma, threshold,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_version": MODEL_VERSION,
            "league": self.league,
            "teams": {key: asdict(value) for key, value in self.teams.items()},
            "processed_game_ids": sorted(self.processed_game_ids),
            "games_seen": self.games_seen,
        }

    @classmethod
    def from_dict(cls, league: str, data: dict[str, Any]) -> "TeamScoreModel":
        return cls(
            league=league,
            teams={key: TeamScoreState(**value) for key, value in data.get("teams", {}).items()},
            processed_game_ids=set(data.get("processed_game_ids", [])),
            games_seen=int(data.get("games_seen", 0)),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)

    @classmethod
    def load(cls, league: str, path: Path) -> "TeamScoreModel":
        if path.exists():
            try:
                return cls.from_dict(league, json.loads(path.read_text(encoding="utf-8")))
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                pass
        return cls(league=league)
