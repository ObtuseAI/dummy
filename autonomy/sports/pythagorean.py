"""Phase 2 analytic: Pythagenpat team strength, point-in-time from the lake.

Pythagorean expectation estimates a team's true strength from how much it
*outscores* opponents, not just its win/loss record -- so it sees a team that
wins close but loses blowouts as weaker than its record, and vice versa. The
Pythagenpat refinement sets the exponent from the game's own scoring
environment (``exp = RPG**0.287``), which travels across sports (runs, points,
goals) without a hand-tuned constant per league.

Independent of Glicko-2 (which only reads W/L), so it's a genuinely diversifying
ensemble source. Pure Python; point-in-time (a team's strength as-of an instant
uses only its strictly-earlier games); fail-closed to 0.5 with no history.
"""
from __future__ import annotations

from typing import Any

from autonomy.sports.history_store import SportsHistoryStore

_PYTHAGENPAT_POWER = 0.287


def pythagenpat_exponent(scored: float, allowed: float, games: int) -> float:
    if games <= 0:
        return 2.0
    rpg = (scored + allowed) / games
    return max(0.5, rpg) ** _PYTHAGENPAT_POWER


def win_expectation(scored: float, allowed: float, games: int) -> float:
    """Pythagenpat expected win rate from cumulative scored/allowed."""
    if scored <= 0 and allowed <= 0:
        return 0.5
    x = pythagenpat_exponent(scored, allowed, games)
    s, a = scored ** x, allowed ** x
    return s / (s + a) if (s + a) > 0 else 0.5


def log5(a: float, b: float) -> float:
    """Bill James log5: P(A beats B) from each side's win expectation."""
    denom = a + b - 2.0 * a * b
    return 0.5 if denom == 0 else (a - a * b) / denom


class LakePythagorean:
    """Point-in-time Pythagenpat team strength accumulated from the lake."""

    def __init__(self, store: SportsHistoryStore, league: str) -> None:
        self.store = store
        self.league = league
        self._scored: dict[str, float] = {}
        self._allowed: dict[str, float] = {}
        self._games: dict[str, int] = {}

    def _acc(self, team: str, scored: float, allowed: float) -> None:
        self._scored[team] = self._scored.get(team, 0.0) + scored
        self._allowed[team] = self._allowed.get(team, 0.0) + allowed
        self._games[team] = self._games.get(team, 0) + 1

    def apply_game(self, game: dict[str, Any]) -> None:
        home, away = game.get("home"), game.get("away")
        hs, as_ = game.get("home_score"), game.get("away_score")
        if not home or not away or hs is None or as_ is None:
            return
        self._acc(home, float(hs), float(as_))
        self._acc(away, float(as_), float(hs))

    def warm(self, as_of: str) -> "LakePythagorean":
        games = self.store.games_before(as_of, league=self.league)
        for game in sorted(games, key=lambda g: g["start_time"]):
            self.apply_game(game)
        return self

    def games_seen(self, team: str) -> int:
        return self._games.get(team, 0)

    def strength(self, team: str) -> float:
        return win_expectation(self._scored.get(team, 0.0), self._allowed.get(team, 0.0),
                               self._games.get(team, 0))

    def matchup_prob(self, home: str, away: str, *, home_advantage_prob: float = 0.03) -> float:
        """Home win probability = log5 of the two strengths, plus a small home
        bump (probability space, clamped)."""
        p = log5(self.strength(home), self.strength(away)) + home_advantage_prob
        return min(0.98, max(0.02, p))
