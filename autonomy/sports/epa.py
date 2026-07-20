"""Phase 2 analytic: EPA/play team strength, point-in-time from the lake.

Expected Points Added per play is the NFL analytics gold standard: it credits
each play by how much it changed the team's expected points, so it captures
efficiency the box score misses. nflfastR computes it; we aggregate offense
(EPA/play generated) minus defense (EPA/play allowed) into a single net rating,
strictly point-in-time. The sharpest signal available for NFL/NCAAF once the
play-by-play lake is backfilled.

Pure Python; matchup win probability from the net-EPA differential through a
logistic (scale + home-edge are tuner seams; hit-rate is scale-invariant).
"""
from __future__ import annotations

import math
from typing import Any

from autonomy.sports.history_store import SportsHistoryStore


class LakeEpa:
    def __init__(self, store: SportsHistoryStore, league: str = "nfl", *,
                 home_edge_epa: float = 0.06, min_plays: int = 120, min_games: int = 3) -> None:
        self.store = store
        self.league = league
        self.home_edge_epa = home_edge_epa
        self.min_plays = min_plays
        self.min_games = min_games

    def strength(self, team: str, as_of: str) -> float | None:
        """Net EPA/play = offensive EPA/play minus defensive EPA/play allowed."""
        agg = self.store.team_stat_sums_before(team, as_of, self.league)
        if not agg or agg["games"] < self.min_games:
            return None
        s = agg["sums"]
        off_plays, def_plays = s.get("off_plays", 0.0), s.get("def_plays", 0.0)
        if off_plays < self.min_plays or def_plays < self.min_plays:
            return None
        off_epa = s.get("off_epa", 0.0) / off_plays
        def_epa = s.get("def_epa", 0.0) / def_plays
        return off_epa - def_epa

    def games_seen(self, team: str, as_of: str) -> int:
        agg = self.store.team_stat_sums_before(team, as_of, self.league)
        return int(agg["games"]) if agg else 0

    def matchup_prob(self, home: str, away: str, as_of: str, *, scale: float = 8.0,
                     home_advantage: float | None = None) -> float | None:
        sh, sa = self.strength(home, as_of), self.strength(away, as_of)
        if sh is None or sa is None:
            return None
        edge = self.home_edge_epa if home_advantage is None else home_advantage
        return 1.0 / (1.0 + math.exp(-((sh - sa) + edge) * scale))
