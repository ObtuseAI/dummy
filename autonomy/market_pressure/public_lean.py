"""The public-lean model: P(the square crowd is on this side).

Reverse line movement is impossible to read without knowing where the public
is. Ticket% is proprietary (Wave-31 scrapes it), but the public leans
PREDICTABLY, and that predictability is itself a usable estimate:

  * favorites -- the public lays chalk and over-backs heavy favorites;
  * overs -- the public roots for scoring and hammers the over;
  * marquee brands -- the public bets the Cowboys / Lakers / Yankees;
  * home teams -- a mild bias toward the home side;
  * primetime -- a nationally-televised game concentrates casual money on the
    popular side (an amplifier, off by default until schedule metadata feeds
    it).

This is a transparent heuristic prior (documented weights) whose only job is
to say which side the sheep are on and how hard. A later wave refits these
weights from settled reverse-line-movement behaviour; until then the numbers
are deliberately conservative. When Wave-31's scraped ticket% is available it
SUPERSEDES this estimate -- this model is the floor, not the ceiling.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Marquee franchises the betting public over-backs, matched by substring
# against a full team name ("New York Yankees" -> Yankees). Not exhaustive;
# the clearly-public brands per league.
POPULAR_FRANCHISES: dict[str, tuple[str, ...]] = {
    "mlb": ("Yankees", "Dodgers", "Red Sox", "Cubs", "Mets", "Braves",
            "Cardinals", "Phillies", "Giants"),
    "nfl": ("Cowboys", "Packers", "Steelers", "Chiefs", "Eagles", "49ers",
            "Patriots", "Bills", "Ravens", "Bears"),
    "ncaaf": ("Alabama", "Ohio State", "Georgia", "Michigan", "Texas",
              "Notre Dame", "USC", "Oregon"),
    "nba": ("Lakers", "Celtics", "Warriors", "Knicks", "Bulls", "Heat"),
    "ncaamb": ("Duke", "Kentucky", "Kansas", "North Carolina", "UCLA"),
    "nhl": ("Rangers", "Bruins", "Maple Leafs", "Red Wings", "Blackhawks"),
    "wnba": ("Aces", "Liberty", "Sky", "Fever"),
}

# Logistic weights (logit space). Deliberately conservative; favorite pull and
# the over bias dominate, brand and home are secondary.
_W_INTERCEPT = 0.0
_W_FAVORITE = 1.6      # x (devig_prob - 0.5) * 2  -> a pick'em adds 0, a big fav adds ~+1.6
_W_OVER = 0.55         # totals: the over
_W_POPULAR = 0.7       # marquee brand
_W_HOME = 0.2          # mild home lean
_W_PRIMETIME = 0.4     # amplifier on the popular direction


@dataclass(frozen=True)
class PublicLeanRead:
    lean: float                       # P(public is on this side), 0..1
    drivers: tuple[str, ...]          # which factors pushed it (for the audit trail)


def is_popular(league: str, team_name: str | None) -> bool:
    if not team_name:
        return False
    brands = POPULAR_FRANCHISES.get(league.lower(), ())
    name = team_name.lower()
    return any(brand.lower() in name for brand in brands)


def estimate_public_lean(
    *,
    league: str,
    devig_prob: float | None,
    is_home: bool = False,
    team_name: str | None = None,
    is_over: bool | None = None,
    primetime: bool = False,
) -> PublicLeanRead:
    """Public lean toward THIS side. ``devig_prob`` is the side's fair win/cover
    probability; ``is_over`` set only for totals (True on the Over side)."""
    logit = _W_INTERCEPT
    drivers: list[str] = []

    if devig_prob is not None:
        fav = (devig_prob - 0.5) * 2.0     # -1..+1
        logit += _W_FAVORITE * fav
        if fav > 0.1:
            drivers.append("favorite")
        elif fav < -0.1:
            drivers.append("underdog")

    if is_over is True:
        logit += _W_OVER
        drivers.append("over")
    elif is_over is False:
        logit -= _W_OVER * 0.6             # the public leans off the under, but weakly

    if is_popular(league, team_name):
        logit += _W_POPULAR
        drivers.append("marquee")

    if is_home:
        logit += _W_HOME
        drivers.append("home")

    if primetime and logit > 0:
        logit += _W_PRIMETIME
        drivers.append("primetime")

    lean = 1.0 / (1.0 + math.exp(-logit))
    return PublicLeanRead(lean=lean, drivers=tuple(drivers))
