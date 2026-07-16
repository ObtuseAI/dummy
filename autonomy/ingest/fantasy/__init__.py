"""Fantasy-data intake leg of the triangulation layer.

Leg #1 is FanGraphs projection consensus (``fangraphs``). Player-prop and
ESPN fantasy (flb) legs land in later waves; this package is the shared home
for those keyless, fail-closed fantasy fetchers.
"""

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
]
