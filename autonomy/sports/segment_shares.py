"""Per-sport segment share tables (Wave-18).

One place answering: what fraction of a game's expected points does each
registered segment carry, and how does sigma scale? The stationary-process
approximation from the Wave-13 basketball half kernel, generalized: a
segment carrying share ``s`` of expected scoring gets ``s`` of the mean and
``sqrt(s)`` of the sigma (independent-increments variance).

Shares are deliberately NOT 1/N: second halves and fourth quarters run hot
(garbage time, intentional fouling, two-minute drills), first quarters run
cold (feeling-out possessions), and the NHL third period is inflated by
empty-net goals. League-parity refinement (possession-level modeling) can
replace these constants later; they are honest first-order priors, and every
consumer stays challenger-only.

``sport_of`` maps league -> share family (NBA/WNBA/NCAAMB share basketball
mechanics; NFL/NCAAF share football's).
"""
from __future__ import annotations

# segment -> share of expected total points. Each family's full-game
# segments sum to 1.0 by construction.
SEGMENT_SHARES: dict[str, dict[str, float]] = {
    "basketball": {
        "h1": 0.49, "h2": 0.51,
        "q1": 0.24, "q2": 0.25, "q3": 0.245, "q4": 0.265,
    },
    "football": {
        "h1": 0.475, "h2": 0.525,
        "q1": 0.20, "q2": 0.275, "q3": 0.22, "q4": 0.305,
    },
    "hockey": {
        "p1": 0.31, "p2": 0.33, "p3": 0.36,
    },
}

_LEAGUE_SPORT: dict[str, str] = {
    "nba": "basketball",
    "wnba": "basketball",
    "ncaamb": "basketball",
    "nfl": "football",
    "ncaaf": "football",
    "nhl": "hockey",
}


def sport_of(league: str) -> str | None:
    return _LEAGUE_SPORT.get(league)


def segment_share(league: str, segment: str) -> float | None:
    """Share of expected points for ``segment`` in ``league``; None when the
    sport has no such segment (callers fail closed)."""
    sport = sport_of(league)
    if sport is None:
        return None
    return SEGMENT_SHARES[sport].get(segment)
