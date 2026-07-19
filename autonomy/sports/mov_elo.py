"""Phase 2 analytic: margin-of-victory Elo, point-in-time from the lake.

Plain Elo only sees win/loss; this variant scales each update by *how much* a
team won by, with FiveThirtyEight's margin multiplier -- a blowout moves ratings
more than a squeaker, but the multiplier is dampened when a heavy favorite wins
(so running up the score against a cupcake doesn't over-credit them). Recency-
weighted, unlike Pythagenpat's season cumulative, so it tracks current form.

A third independent rating voice (Glicko = W/L, Pythagenpat = season margin,
MOV-Elo = recency-weighted margin) -- diversity the ensemble can exploit. Uses
only final scores, already in the lake, so no per-game fetch. Point-in-time via
chronological replay; pure Python.
"""
from __future__ import annotations

import math
from typing import Any

from autonomy.sports.history_store import SportsHistoryStore

_BASE = 1500.0
_SCALE = 400.0


class MovElo:
    def __init__(self, k: float = 20.0) -> None:
        self.k = k

    def expected(self, r_home: float, r_away: float, hfa: float = 0.0) -> float:
        return 1.0 / (1.0 + 10.0 ** (-((r_home + hfa) - r_away) / _SCALE))

    @staticmethod
    def mov_multiplier(margin: float, rating_diff_winner: float) -> float:
        # 538: log dampener on margin, autocorrelation dampener on winner favouredness.
        return math.log(abs(margin) + 1.0) * (2.2 / (abs(rating_diff_winner) * 0.001 + 2.2))

    def update(
        self, r_home: float, r_away: float, home_score: float, away_score: float, hfa: float = 0.0,
    ) -> tuple[float, float]:
        e = self.expected(r_home, r_away, hfa)
        margin = home_score - away_score
        s = 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5
        if margin > 0:
            rdw = (r_home + hfa) - r_away
        elif margin < 0:
            rdw = r_away - (r_home + hfa)
        else:
            rdw = 0.0
        mult = self.mov_multiplier(margin, rdw) if margin != 0 else 1.0
        delta = self.k * mult * (s - e)
        return r_home + delta, r_away - delta


class LakeMovElo:
    """Point-in-time MOV-Elo team ratings warmed from the lake."""

    def __init__(self, store: SportsHistoryStore, league: str, *, k: float = 20.0,
                 home_advantage: float = 40.0) -> None:
        self.store = store
        self.league = league
        self.engine = MovElo(k=k)
        self.home_advantage = home_advantage
        self._r: dict[str, float] = {}
        self._seen: set[str] = set()

    def rating(self, team: str) -> float:
        return self._r.get(team, _BASE)

    def apply_game(self, game: dict[str, Any]) -> None:
        gid = game.get("game_id")
        if gid in self._seen:
            return
        home, away = game.get("home"), game.get("away")
        hs, as_ = game.get("home_score"), game.get("away_score")
        if not home or not away or hs is None or as_ is None:
            return
        r_h, r_a = self.rating(home), self.rating(away)
        self._r[home], self._r[away] = self.engine.update(r_h, r_a, float(hs), float(as_), self.home_advantage)
        if gid is not None:
            self._seen.add(gid)

    def warm(self, as_of: str) -> "LakeMovElo":
        games = self.store.games_before(as_of, league=self.league)
        for game in sorted(games, key=lambda g: g["start_time"]):
            self.apply_game(game)
        return self

    def matchup_prob(self, home: str, away: str, *, home_advantage: float | None = None) -> float:
        hfa = self.home_advantage if home_advantage is None else home_advantage
        return self.engine.expected(self.rating(home), self.rating(away), hfa)
