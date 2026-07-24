"""Canonical per-game sports-market registry (Wave-10).

Kalshi carries a deep per-game surface for every league: the moneyline is one
market of many. A single MLB game alone spans winner / run-line spread / total /
team total / first-inning run (YRFI) / first-five-innings winner-spread-total /
and eight player-prop families (home runs, strikeouts, hits, H+R+RBI, total
bases, outs, RBIs, stolen bases). The other leagues add halves, quarters,
periods and team-stat totals.

Two things gate whether dummy can act on a market type: it must be DISCOVERED
(the scanner only fetches series on its watchlist) and it must be CLASSIFIED
(a signal has to know a ticker is "MLB first-five total, line 6.5" to price it).
Historically those two lists lived apart (``scanner.WATCHLIST_SERIES`` and a
per-signal parser), so a series could be fetched but unpriced, or priceable but
never fetched. This module is the single source of truth for both: one registry
maps every per-game series to its semantics, and both the watchlist and the
market-type classifier are derived from it, so they cannot drift.

Descriptive only -- it says what a market IS, never whether to trade it. Pricing
signals decide applicability themselves and stay challenger-only + fail-closed.
The ``discover`` flag gates scan inclusion so the watchlist grows exactly as
pricing coverage does, rather than flooding the scan with market types nothing
can yet price.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from autonomy.ontology import MarketView, Vertical
from autonomy.sports.espn import canonical_team

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

# Stable, year-round navigation roster.  This is a capability list, not a
# claim that any league has a game or listed contract today.  Keep it beside
# the canonical series registry so dashboard, artifact, and desktop surfaces
# cannot silently drop an out-of-season league just because its current slate
# is empty.
SPORTS_LEAGUES: tuple[str, ...] = (
    "MLB",
    "WNBA",
    "NBA",
    "NFL",
    "NHL",
    "NCAAF",
    "NCAAMB",
)

# Market type: WHAT is being priced.
WINNER = "winner"            # moneyline (2-way, or 3-way when a tie is possible)
SPREAD = "spread"            # run/point/goal line at a strike
TOTAL = "total"             # combined total at a strike (over/under)
TEAM_TOTAL = "team_total"    # one team's total at a strike
YRFI = "yrfi"               # a run in the first inning (MLB), binary
PROP = "prop"               # player statistic over/under

# Segment: WHICH slice of the game. ``full`` is the whole game.
FULL = "full"
F5, F3, F7 = "f5", "f3", "f7"          # MLB first-N-innings
H1, H2 = "h1", "h2"                     # halves
Q1, Q2, Q3, Q4 = "q1", "q2", "q3", "q4"  # quarters

# Player-prop stat families (MLB). Names mirror the licensed feed's semantics so
# LicensedPropProvider can map them to the provider's ``player_*`` market keys.
STAT_HOME_RUNS = "home_runs"
STAT_STRIKEOUTS = "strikeouts"
STAT_HITS = "hits"
STAT_HITS_RUNS_RBIS = "hits_runs_rbis"
STAT_TOTAL_BASES = "total_bases"
STAT_OUTS = "outs"
STAT_RBIS = "rbis"
STAT_STOLEN_BASES = "stolen_bases"


@dataclass(frozen=True)
class SeriesSpec:
    """What a Kalshi series ticker means, and whether we discover it."""

    league: str
    market_type: str
    segment: str = FULL
    stat: str | None = None
    is_prop: bool = False
    # Winner markets are 3-way (a tie outcome exists) for MLB first-five and,
    # generally, any segment that can end level. Priced as an explicit third leg.
    three_way: bool = False
    # Included in the scanner watchlist. Turned on exactly when a pricing path
    # exists, so discovery tracks coverage instead of surfacing dead markets.
    discover: bool = False


def _winner(league: str, segment: str = FULL, *, discover: bool, three_way: bool = False) -> SeriesSpec:
    return SeriesSpec(league, WINNER, segment, three_way=three_way, discover=discover)


def _line(league: str, market_type: str, segment: str = FULL, *, discover: bool) -> SeriesSpec:
    return SeriesSpec(league, market_type, segment, discover=discover)


def _prop(league: str, stat: str, *, discover: bool) -> SeriesSpec:
    return SeriesSpec(league, PROP, FULL, stat=stat, is_prop=True, discover=discover)


# ---------------------------------------------------------------------------
# The registry. Every entry is a real Kalshi series (verified live 2026-07-17
# against /series?category=Sports). ``discover=True`` = on the watchlist now;
# False = registered/classified but awaiting its pricing wave (segment lines,
# team-stat props). Full-game winner/spread/total/team_total price via the
# licensed + single-book consensus de-vig today; MLB first-five and team totals
# also price off dummy's own PA-sim.
# ---------------------------------------------------------------------------

_LEAGUE_GAME_LINES: dict[str, dict[str, str]] = {
    # league -> {series_suffix: (implicit via helper below)}
}

SERIES_SPEC: dict[str, SeriesSpec] = {
    # ===================== MLB (reference league) =====================
    "KXMLBGAME": _winner("mlb", discover=True),
    "KXMLBSPREAD": _line("mlb", SPREAD, discover=True),
    "KXMLBTOTAL": _line("mlb", TOTAL, discover=True),
    "KXMLBTEAMTOTAL": _line("mlb", TEAM_TOTAL, discover=True),
    "KXMLBRFI": SeriesSpec("mlb", YRFI, discover=True),
    # First five innings -- winner is 3-way (a 5-inning tie is a real outcome).
    "KXMLBF5": _winner("mlb", F5, discover=True, three_way=True),
    "KXMLBF5SPREAD": _line("mlb", SPREAD, F5, discover=True),
    "KXMLBF5TOTAL": _line("mlb", TOTAL, F5, discover=True),
    # First three / seven innings exist but are thin; registered, not yet discovered.
    "KXMLBF3": _line("mlb", TOTAL, F3, discover=False),
    "KXMLBF7": _line("mlb", TOTAL, F7, discover=False),
    # Player props (the eight families on the app's Player Props tab).
    "KXMLBHR": _prop("mlb", STAT_HOME_RUNS, discover=True),
    "KXMLBKS": _prop("mlb", STAT_STRIKEOUTS, discover=True),
    "KXMLBHIT": _prop("mlb", STAT_HITS, discover=True),
    "KXMLBHRR": _prop("mlb", STAT_HITS_RUNS_RBIS, discover=True),
    "KXMLBTB": _prop("mlb", STAT_TOTAL_BASES, discover=True),
    "KXMLBOUTS": _prop("mlb", STAT_OUTS, discover=True),
    "KXMLBRBI": _prop("mlb", STAT_RBIS, discover=True),
    "KXMLBSB": _prop("mlb", STAT_STOLEN_BASES, discover=True),

    # ===================== NFL =====================
    "KXNFLGAME": _winner("nfl", discover=True),
    "KXNFLSPREAD": _line("nfl", SPREAD, discover=True),
    "KXNFLTOTAL": _line("nfl", TOTAL, discover=True),
    "KXNFLTEAMTOTAL": _line("nfl", TEAM_TOTAL, discover=True),
    "KXNFLTEAMPTS": _line("nfl", TEAM_TOTAL, discover=False),
    # Halves / quarters (segment lines) -- registered, staged for the segment wave.
    "KXNFL1HWINNER": _winner("nfl", H1, discover=True, three_way=True),
    "KXNFL1HSPREAD": _line("nfl", SPREAD, H1, discover=True),
    "KXNFL1HTOTAL": _line("nfl", TOTAL, H1, discover=True),
    "KXNFL2HWINNER": _winner("nfl", H2, discover=True, three_way=True),
    "KXNFL2HSPREAD": _line("nfl", SPREAD, H2, discover=True),
    "KXNFL2HTOTAL": _line("nfl", TOTAL, H2, discover=True),
    "KXNFL1QSPREAD": _line("nfl", SPREAD, Q1, discover=True),
    "KXNFL1QTOTAL": _line("nfl", TOTAL, Q1, discover=True),
    "KXNFL2QSPREAD": _line("nfl", SPREAD, Q2, discover=True),
    "KXNFL2QTOTAL": _line("nfl", TOTAL, Q2, discover=True),
    "KXNFL3QSPREAD": _line("nfl", SPREAD, Q3, discover=True),
    "KXNFL3QTOTAL": _line("nfl", TOTAL, Q3, discover=True),
    "KXNFL4QSPREAD": _line("nfl", SPREAD, Q4, discover=True),
    "KXNFL4QTOTAL": _line("nfl", TOTAL, Q4, discover=True),
    # Wave-85: Kalshi lists KXNFL{1..4}QWINNER, which we had never registered.
    # Registered (so coverage is tracked and the classifier knows them) but NOT
    # discovered: a quarter winner is three-way and needs a quarter-level
    # scoring path that does not exist yet. Same posture as KXMLBF3/KXMLBF7 --
    # a series is fetched exactly when a pricing path exists for it.
    "KXNFL1QWINNER": _winner("nfl", Q1, discover=False, three_way=True),
    "KXNFL2QWINNER": _winner("nfl", Q2, discover=False, three_way=True),
    "KXNFL3QWINNER": _winner("nfl", Q3, discover=False, three_way=True),
    "KXNFL4QWINNER": _winner("nfl", Q4, discover=False, three_way=True),

    # ===================== NBA =====================
    "KXNBAGAME": _winner("nba", discover=True),
    "KXNBASPREAD": _line("nba", SPREAD, discover=True),
    "KXNBATOTAL": _line("nba", TOTAL, discover=True),
    "KXNBATEAMTOTAL": _line("nba", TEAM_TOTAL, discover=True),
    "KXNBA1HWINNER": _winner("nba", H1, discover=True, three_way=True),
    "KXNBA1HSPREAD": _line("nba", SPREAD, H1, discover=True),
    "KXNBA1HTOTAL": _line("nba", TOTAL, H1, discover=True),
    "KXNBA2HWINNER": _winner("nba", H2, discover=True, three_way=True),
    "KXNBA2HSPREAD": _line("nba", SPREAD, H2, discover=True),
    "KXNBA2HTOTAL": _line("nba", TOTAL, H2, discover=True),
    "KXNBA1QSPREAD": _line("nba", SPREAD, Q1, discover=True),
    "KXNBA1QTOTAL": _line("nba", TOTAL, Q1, discover=True),
    "KXNBA2QSPREAD": _line("nba", SPREAD, Q2, discover=True),
    "KXNBA2QTOTAL": _line("nba", TOTAL, Q2, discover=True),
    "KXNBA3QSPREAD": _line("nba", SPREAD, Q3, discover=True),
    "KXNBA3QTOTAL": _line("nba", TOTAL, Q3, discover=True),
    "KXNBA4QSPREAD": _line("nba", SPREAD, Q4, discover=True),
    "KXNBA4QTOTAL": _line("nba", TOTAL, Q4, discover=True),

    # ===================== NHL =====================
    "KXNHLGAME": _winner("nhl", discover=True),
    "KXNHLSPREAD": _line("nhl", SPREAD, discover=True),
    "KXNHLTOTAL": _line("nhl", TOTAL, discover=True),

    # ===================== NCAAF =====================
    "KXNCAAFGAME": _winner("ncaaf", discover=True),
    "KXNCAAFSPREAD": _line("ncaaf", SPREAD, discover=True),
    "KXNCAAFTOTAL": _line("ncaaf", TOTAL, discover=True),
    "KXNCAAFTEAMTOTAL": _line("ncaaf", TEAM_TOTAL, discover=True),
    # NCAAF's segment surface is COMPLETE at 1H winner. The 2026-07-24 audit
    # read the gap against NFL as ours to close; it is not. Kalshi's own
    # /series?category=Sports (3,005 series, checked 2026-07-24) lists exactly
    # one NCAAF segment series -- KXNCAAF1HWINNER. There is no KXNCAAF2HWINNER,
    # no KXNCAAF1H/2H spread or total, and no NCAAF quarter series at all,
    # whereas NFL has the full 1H/2H/1Q-4Q set. The asymmetry is the venue's.
    # Registering the missing names would only spend scan budget on series that
    # do not exist. Re-check before assuming this is still true.
    "KXNCAAF1HWINNER": _winner("ncaaf", H1, discover=True, three_way=True),

    # ===================== NCAAMB =====================
    "KXNCAAMBGAME": _winner("ncaamb", discover=True),
    "KXNCAAMBSPREAD": _line("ncaamb", SPREAD, discover=True),
    "KXNCAAMBTOTAL": _line("ncaamb", TOTAL, discover=True),
    "KXNCAAMB1HWINNER": _winner("ncaamb", H1, discover=True, three_way=True),
    "KXNCAAMB1HSPREAD": _line("ncaamb", SPREAD, H1, discover=True),
    "KXNCAAMB1HTOTAL": _line("ncaamb", TOTAL, H1, discover=True),
    "KXNCAAMB2HSPREAD": _line("ncaamb", SPREAD, H2, discover=True),
    "KXNCAAMB2HTOTAL": _line("ncaamb", TOTAL, H2, discover=True),

    # ===================== WNBA =====================
    "KXWNBAGAME": _winner("wnba", discover=True),
    "KXWNBASPREAD": _line("wnba", SPREAD, discover=True),
    "KXWNBATOTAL": _line("wnba", TOTAL, discover=True),
    # Wave-13: first-half surface priced (basketball half kernel). The 1H
    # winner is 3-way -- an explicit TIE leg exists (verified live 2026-07-17:
    # KXWNBA1HWINNER-26JUL17CONNPHX-TIE).
    "KXWNBA1HWINNER": _winner("wnba", H1, discover=True, three_way=True),
    "KXWNBA1HSPREAD": _line("wnba", SPREAD, H1, discover=True),
    "KXWNBA1HTOTAL": _line("wnba", TOTAL, H1, discover=True),
    "KXWNBA2HWINNER": _winner("wnba", H2, discover=True, three_way=True),
    "KXWNBA2HSPREAD": _line("wnba", SPREAD, H2, discover=True),
    "KXWNBA2HTOTAL": _line("wnba", TOTAL, H2, discover=True),
    "KXWNBA1QSPREAD": _line("wnba", SPREAD, Q1, discover=True),
    "KXWNBA1QTOTAL": _line("wnba", TOTAL, Q1, discover=True),
    "KXWNBA2QSPREAD": _line("wnba", SPREAD, Q2, discover=True),
    "KXWNBA2QTOTAL": _line("wnba", TOTAL, Q2, discover=True),
    "KXWNBA3QSPREAD": _line("wnba", SPREAD, Q3, discover=True),
    "KXWNBA3QTOTAL": _line("wnba", TOTAL, Q3, discover=True),
    "KXWNBA4QSPREAD": _line("wnba", SPREAD, Q4, discover=True),
    "KXWNBA4QTOTAL": _line("wnba", TOTAL, Q4, discover=True),
}


# ---------------------------------------------------------------------------
# Classification of a live market
# ---------------------------------------------------------------------------

_MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], start=1)}
# parts[1] = YY MON DD [HHMM] TEAMS [G<n> doubleheader]; we only need the date.
_DATE_RE = re.compile(r"^(\d{2})([A-Z]{3})(\d{2})(?:\d{4})?[A-Z]{3,}(?:G\d)?$")
# A winner suffix carries the subject team abbreviation, sometimes an index digit
# (e.g. ``-NYY`` or, for spreads, ``-BOS11``). A tie leg is the literal ``TIE``.
_SUBJECT_RE = re.compile(r"^([A-Z]+?)\d*$")


@dataclass(frozen=True)
class SportsMarketInfo:
    """A live Kalshi market, classified against the registry."""

    series: str
    league: str
    market_type: str
    segment: str
    event_ticker: str
    date_yyyymmdd: str | None
    teams: tuple[str, str] | None      # display names from the title, home-agnostic
    subject: str | None                # team abbr (winner/spread/team_total) or player
    threshold: float | None            # strike line (spread/total/team_total)
    stat: str | None                   # prop stat family
    is_prop: bool
    is_tie: bool                       # this leg is the explicit tie outcome
    three_way: bool

    @property
    def segment_label(self) -> str:
        return "" if self.segment == FULL else self.segment.upper()


def series_of(ticker: str) -> str:
    return ticker.upper().split("-", 1)[0]


def spec_for(ticker: str) -> SeriesSpec | None:
    return SERIES_SPEC.get(series_of(ticker))


def is_known_sports_market(ticker: str) -> bool:
    return series_of(ticker) in SERIES_SPEC


def discovery_series() -> list[str]:
    """Series to fetch: exactly those with a live pricing path (``discover``)."""
    return sorted(s for s, spec in SERIES_SPEC.items() if spec.discover)


def registered_series() -> list[str]:
    """Every per-game series the registry knows, discovered or staged."""
    return sorted(SERIES_SPEC)


def _parse_date(token: str) -> str | None:
    m = _DATE_RE.match(token)
    if not m:
        return None
    yy, mon, dd = m.groups()
    month = _MONTHS.get(mon)
    if month is None:
        return None
    return f"20{yy}{month:02d}{int(dd):02d}"


def _teams_from_title(title: str) -> tuple[str, str] | None:
    """Extract the two display names from a ``A vs B ...`` title, best-effort."""
    # Strip a trailing market-descriptor clause so it doesn't leak into team B.
    # Wave-18: segment vocabulary added (Second/Half/Quarter/Period, 1H/2H,
    # 1Q-4Q, 1P-3P) -- a "A vs B: Second Half Total?" title previously left
    # ": Second Half" glued onto team B and broke the matchup lookup. A
    # trailing colon on team B (segment-title separator) is stripped too.
    head = re.split(
        r"\s+(?:Winner|Spread|Total|Team Total|Run|Runs|Points|Goals|"
        r"First|Second|Half|Quarter|Period|[1-4]Q|[12]H|[1-3]P|"
        r"Total Runs|Total Points|Total Goals)\b",
        title, maxsplit=1, flags=re.IGNORECASE)[0]
    names = re.split(r"\s+vs\.?\s+", head, maxsplit=1, flags=re.IGNORECASE)
    if len(names) != 2:
        return None
    a, b = names[0].strip(" ?"), names[1].strip(" ?:")
    if not a or not b:
        return None
    return a, b


def classify(market: MarketView) -> SportsMarketInfo | None:
    """Classify a live market against the registry. Returns None for anything
    not a known per-game sports market. Fail-closed: a recognised series with an
    unparseable date/strike still classifies (type is known) but leaves those
    fields None, so a pricing signal can reject it rather than mis-price it."""
    if market.vertical is not Vertical.SPORTS:
        return None
    ticker = market.ticker.upper()
    parts = ticker.split("-")
    series = parts[0]
    spec = SERIES_SPEC.get(series)
    if spec is None:
        return None

    event_ticker = "-".join(parts[:2]) if len(parts) >= 2 else series
    date = _parse_date(parts[1]) if len(parts) >= 2 else None
    teams = _teams_from_title(market.title) if market.title else None

    subject: str | None = None
    player: str | None = None
    is_tie = False
    threshold: float | None = None

    if spec.is_prop:
        # Player identity is carried in the title ("Yandy Diaz: 2+ home runs?");
        # the ticker's player token is abbreviated. Title is the reliable id.
        m = re.match(r"^\s*(.+?)\s*:", market.title or "")
        player = m.group(1).strip() if m else None
        subject = player
        threshold = _strike(market)
    elif spec.market_type in (SPREAD, TEAM_TOTAL):
        subject = _subject_abbr(parts, spec.league)
        threshold = _strike(market)
    elif spec.market_type == TOTAL:
        threshold = _strike(market)
    elif spec.market_type == WINNER:
        subject = _subject_abbr(parts, spec.league)
        is_tie = subject == "TIE" or (len(parts) >= 3 and parts[2].upper() == "TIE")

    return SportsMarketInfo(
        series=series, league=spec.league, market_type=spec.market_type,
        segment=spec.segment, event_ticker=event_ticker, date_yyyymmdd=date,
        teams=teams, subject=subject, threshold=threshold, stat=spec.stat,
        is_prop=spec.is_prop, is_tie=is_tie, three_way=spec.three_way,
    )


def _subject_abbr(parts: list[str], league: str) -> str | None:
    if len(parts) < 3:
        return None
    token = parts[2].upper()
    if token == "TIE":
        return "TIE"
    m = _SUBJECT_RE.match(token)
    if m is None:
        return None
    return canonical_team(league, m.group(1))


def _strike(market: MarketView) -> float | None:
    raw: dict[str, Any] = market.raw or {}
    for key in ("floor_strike", "cap_strike", "strike"):
        value = raw.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None
