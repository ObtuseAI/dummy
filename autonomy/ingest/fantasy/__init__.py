"""Fantasy-data intake leg of the triangulation layer.

Leg #1 is FanGraphs projection consensus (``fangraphs``); leg #3 is ESPN fantasy
baseball ownership/ADP/projections + scratch feed (``espn_fantasy``). The
player-prop leg (#2) lands in a later wave; this package is the shared home for
those keyless, fail-closed fantasy fetchers.
"""

from autonomy.ingest.fantasy.espn_fantasy import (
    ESPN_FLB_PRO_TEAMS,
    FantasyBook,
    FantasyPlayer,
    ScratchEvent,
    TeamFantasyAggregate,
    aggregate_team_fantasy,
    availability_class,
    default_fetch_players,
    detect_scratch_events,
    parse_players,
    proteam_to_canonical,
)
from autonomy.ingest.fantasy.fangraphs import (
    DEFAULT_SYSTEM,
    PROJECTION_SYSTEMS,
    PlayerProjection,
    ProjectionBook,
    TeamProjection,
    canonical_mlb_team,
    default_fetch_projections,
    parse_projections,
)

__all__ = [
    "DEFAULT_SYSTEM",
    "PROJECTION_SYSTEMS",
    "PlayerProjection",
    "ProjectionBook",
    "TeamProjection",
    "canonical_mlb_team",
    "default_fetch_projections",
    "parse_projections",
    # ESPN fantasy (flb) leg #3
    "ESPN_FLB_PRO_TEAMS",
    "FantasyBook",
    "FantasyPlayer",
    "ScratchEvent",
    "TeamFantasyAggregate",
    "aggregate_team_fantasy",
    "availability_class",
    "default_fetch_players",
    "detect_scratch_events",
    "parse_players",
    "proteam_to_canonical",
]
