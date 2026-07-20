"""Phase 2 analytic: Dean Oliver's Four Factors, point-in-time from the lake.

The four factors of basketball success -- shooting (eFG%), turnovers (TOV%),
rebounding (ORB%), and free throws (FT rate) -- explain most of the variance in
who wins, and (unlike win/loss or scoring-margin ratings) they say *how* a team
is good, which travels to spreads and totals. Computed from persisted boxscores
for both offense (own) and defense (opponents allowed), strictly point-in-time.

Pure Python. Win probability comes from the net four-factor efficiency
differential through a logistic; the scale is a seam the tuner can set (hit-rate
is scale-invariant, so the walk-forward validates direction before calibration).
"""
from __future__ import annotations

import math

from autonomy.sports.history_store import SportsHistoryStore

# Oliver's approximate weights on the offensive factors (shooting dominates).
_W = {"efg": 0.40, "tov": 0.25, "orb": 0.20, "ftr": 0.15}
_LOGISTIC_SCALE = 9.0        # net-efficiency -> win-prob steepness (tuner seam)


def four_factors(stats: dict[str, float]) -> dict[str, float] | None:
    """The four factors from a bundle of summed boxscore stats. None if no shots."""
    fgm = stats.get("fieldGoalsMade", 0.0)
    fga = stats.get("fieldGoalsAttempted", 0.0)
    fg3 = stats.get("threePointFieldGoalsMade", 0.0)
    ftm = stats.get("freeThrowsMade", 0.0)
    fta = stats.get("freeThrowsAttempted", 0.0)
    tov = stats.get("turnovers", 0.0)
    orb = stats.get("offensiveRebounds", 0.0)
    if fga <= 0:
        return None
    poss = fga + 0.44 * fta + tov
    missed = max(1e-9, fga - fgm + orb)      # own missed FGs available for an ORB
    return {
        "efg": (fgm + 0.5 * fg3) / fga,
        "tov": (tov / poss) if poss > 0 else 0.14,
        "orb": orb / missed,
        "ftr": ftm / fga,
    }


def net_rating(off: dict[str, float], deff: dict[str, float]) -> float:
    """Offense's four-factor quality minus what the defense allows. TOV enters
    negatively (fewer is better), so an offense that shoots well + protects the
    ball + rebounds + gets to the line, against a defense that doesn't force
    those, nets positive."""
    def _score(ff: dict[str, float]) -> float:
        return (_W["efg"] * ff["efg"] - _W["tov"] * ff["tov"]
                + _W["orb"] * ff["orb"] + _W["ftr"] * ff["ftr"])
    return _score(off) - _score(deff)


class LakeFourFactors:
    """Point-in-time Four-Factors strength + matchup probability from the lake."""

    def __init__(self, store: SportsHistoryStore, league: str) -> None:
        self.store = store
        self.league = league

    def strength(self, team: str, as_of: str) -> float | None:
        sums = self.store.four_factor_sums_before(team, as_of, self.league)
        if not sums:
            return None
        off, deff = four_factors(sums["off"]), four_factors(sums["def"])
        if off is None or deff is None:
            return None
        return net_rating(off, deff)

    def games_seen(self, team: str, as_of: str) -> int:
        sums = self.store.four_factor_sums_before(team, as_of, self.league)
        return int(sums["games"]) if sums else 0

    def matchup_prob(
        self, home: str, away: str, as_of: str, *, home_advantage_prob: float = 0.03,
        scale: float = _LOGISTIC_SCALE,
    ) -> float | None:
        sh, sa = self.strength(home, as_of), self.strength(away, as_of)
        if sh is None or sa is None:
            return None
        p = 1.0 / (1.0 + math.exp(-(sh - sa) * scale)) + home_advantage_prob
        return min(0.98, max(0.02, p))
