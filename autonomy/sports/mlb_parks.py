"""Static MLB park run-factor table (WS-11 / spec §4 item 1).

A park factor is a multiplicative scaling on a game's expected TOTAL runs
relative to a league-average park (1.00). Values here are static, auditable
constants -- NOT live-fetched -- approximating each team's own ballpark's
multi-year run-scoring environment (source: publicly documented multi-year
MLB park-factor rankings as commonly compiled in FanGraphs/ESPN-style park
factor lists; run environment swings roughly Coors-to-Oracle/Petco ~20-30%,
consistent with the two anchor values the WS-11 brief calls out verbatim:
Coors Field (COL) ~1.28, and the pair of pitcher-friendly, marine-layer
parks Petco (SD) and Oracle (SF) ~0.90). The remaining 27 entries are
internally consistent approximations anchored to those three values and
widely-known park character (Fenway's Green Monster and Great American Ball
Park run hot; Comerica/loanDepot/T-Mobile Park run cold), not a precise
current-season recompute -- exactly the "documented, internally-consistent
set" the brief's ambiguity resolution calls for.

Keyed by the HOME team's canonical abbreviation
(``autonomy.sports.espn.canonical_team("mlb", ...)``), since a park factor is
a property of the home team's own ballpark, not the venue's free-text name
(which is noisier to match against ESPN's payload). ATH and OAK both map to
the Athletics' park (the franchise's team code changed over its history);
both keys carry the identical factor so either resolves the same way.

Fail-closed: any team code absent from this table (unknown/expansion/new
park) resolves to 1.0 -- a byte-identical no-op wherever the factor is
applied multiplicatively.
"""
from __future__ import annotations

PARK_FACTORS: dict[str, float] = {
    "ARI": 1.03,
    "ATL": 1.00,
    "BAL": 1.02,
    "BOS": 1.08,
    "CHC": 1.02,
    "CHW": 1.03,
    "CIN": 1.12,
    "CLE": 0.97,
    "COL": 1.28,  # Coors Field -- altitude; brief anchor value
    "DET": 0.95,
    "HOU": 1.01,
    "KC": 0.98,
    "LAA": 0.99,
    "LAD": 0.98,
    "MIA": 0.92,
    "MIL": 1.02,
    "MIN": 0.98,
    "NYM": 0.97,
    "NYY": 1.05,
    "ATH": 0.96,
    "OAK": 0.96,  # alias -- Athletics' team code changed; same park factor
    "PHI": 1.09,
    "PIT": 0.96,
    "SD": 0.90,   # Petco Park -- marine layer; brief anchor value
    "SEA": 0.93,
    "SF": 0.90,   # Oracle Park -- marine layer; brief anchor value
    "STL": 0.97,
    "TB": 0.95,
    "TEX": 1.02,
    "TOR": 1.01,
    "WSH": 0.99,
}


def park_factor_for(home_team: str | None) -> float:
    """Multiplicative run factor for a home team's park; 1.0 if unknown."""
    if not home_team:
        return 1.0
    from autonomy.sports.espn import canonical_team

    return PARK_FACTORS.get(canonical_team("mlb", home_team), 1.0)
