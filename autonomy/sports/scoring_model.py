"""Phase 2 analytic: expected margin + total from the lake (spreads & totals).

The rating analytics answer "who wins"; this answers "by how much" and "how
many combined" -- what spread and total markets actually settle on. Each team's
offensive and defensive scoring rate is aggregated point-in-time from the lake's
final scores; a matchup's expected home/away scores blend the two, giving an
expected margin (for spreads) and expected total (for totals). Cover / over
probabilities come from a normal around those with a league-calibrated spread.

Pure Python; point-in-time (a team's rates use only strictly-earlier games).
Sigmas are per-league seams the tuner can refine.
"""
from __future__ import annotations

import math
from typing import Any

from autonomy.sports.history_store import SportsHistoryStore

# (home-edge points, margin sigma, total sigma) per league -- reviewable priors.
_LEAGUE_PARAMS: dict[str, tuple[float, float, float]] = {
    "nfl": (2.0, 13.5, 13.0), "ncaaf": (2.5, 16.0, 15.0),
    "nba": (2.8, 12.0, 15.0), "wnba": (2.5, 10.5, 13.0), "ncaamb": (3.5, 11.0, 14.0),
    "nhl": (0.3, 2.0, 2.4), "mlb": (0.2, 4.0, 4.2),
}


def _norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


class LakeScoringModel:
    def __init__(self, store: SportsHistoryStore, league: str) -> None:
        self.store = store
        self.league = league
        self.home_edge, self.sigma_margin, self.sigma_total = _LEAGUE_PARAMS.get(
            league, (2.0, 12.0, 14.0))

    def _rates(self, team: str, as_of: str, n: int = 200) -> tuple[float, float, int] | None:
        """(avg scored, avg allowed, games) from the team's completed games
        before ``as_of``. None if no history."""
        games = self.store.team_form(team, as_of, league=self.league, n=n)
        if not games:
            return None
        scored = allowed = 0.0
        used = 0
        for g in games:
            hs, as_ = g.get("home_score"), g.get("away_score")
            if hs is None or as_ is None:
                continue
            if g.get("home") == team:
                scored += hs; allowed += as_
            else:
                scored += as_; allowed += hs
            used += 1
        if used == 0:
            return None
        return scored / used, allowed / used, used

    def expected_scores(self, home: str, away: str, as_of: str) -> tuple[float, float] | None:
        rh, ra = self._rates(home, as_of), self._rates(away, as_of)
        if rh is None or ra is None:
            return None
        # home points ~ blend of home offense and away defense; + home edge.
        home_pts = (rh[0] + ra[1]) / 2.0 + self.home_edge / 2.0
        away_pts = (ra[0] + rh[1]) / 2.0 - self.home_edge / 2.0
        return home_pts, away_pts

    def expected_margin(self, home: str, away: str, as_of: str) -> float | None:
        exp = self.expected_scores(home, away, as_of)
        return None if exp is None else exp[0] - exp[1]

    def expected_total(self, home: str, away: str, as_of: str) -> float | None:
        exp = self.expected_scores(home, away, as_of)
        return None if exp is None else exp[0] + exp[1]

    def p_home_covers(self, home: str, away: str, as_of: str, home_spread: float) -> float | None:
        """P(home covers). ``home_spread`` is the home line (e.g. -3.5 = favored
        by 3.5). Home covers when actual margin + home_spread > 0."""
        m = self.expected_margin(home, away, as_of)
        if m is None:
            return None
        return _norm_cdf((m + home_spread) / self.sigma_margin)

    def p_over(self, home: str, away: str, as_of: str, line: float) -> float | None:
        t = self.expected_total(home, away, as_of)
        if t is None:
            return None
        return 1.0 - _norm_cdf((line - t) / self.sigma_total)
