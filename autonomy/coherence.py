"""Cross-market coherence engine: the 3x3 conviction lattice (spec Sec3.0/3.1).

Every game gets a nine-cell lattice -- three estimators (our sport-native
model, the de-vigged sharp book, the Kalshi crowd) x three market families
(winner, spread ladder, total ladder). Two independent checks live here:

  * ``ladder_violations`` -- Kalshi's own rung monotonicity within ONE
    family (spread or total). Needs no model opinion at all: if Kalshi's own
    quotes say covering a BIGGER margin is MORE likely than covering a
    smaller one (beyond fee/spread slack), that is a structural incoherence
    entirely internal to Kalshi's own book.
  * ``cross_family_incoherence`` -- Kalshi's winner price vs. its own spread
    price, reconciled through the MODEL's joint distribution shape (a
    first-order linear transport; see the function docstring for the exact
    approximation and its documented limits).

``lattice_conviction`` folds both checks plus the underlying model/book
assessments into a single per-game conviction tier, the ranking WS-5 feeds to
the opportunist as an anchor-threshold relaxation for the two top tiers.

Grouping (``build_game_lattices``) is the REAL grouping layer: it goes
through ``autonomy.signals.sports_intelligence.parse_sports_contract`` (the
same parser the sports specialists use), not a hand-rolled dict lookup. A
market that does not parse to a sports contract, or whose contract family is
not one of winner/spread/total (e.g. MLB's yrfi), is simply not grouped --
fail-closed by construction: no cells means no lattice, means no violations,
means no incoherence, means no conviction-tier boost anywhere downstream.

SUBJECT-AWARENESS (why a game groups both teams' markets, yet never
cross-contaminates them): one game lists markets for BOTH sides -- "HOU
wins" and "TEX covers 1.5" and "HOU covers 1.5" all belong to the same
game_key. That is correct for grouping, but the coherence math must never
treat opposite-team cells as rungs or confirmations of one another (doing so
fabricates a structural violation on essentially every game, since the two
spread sides carry near-complementary probabilities at the same line). So
every ``LatticeCell`` carries the per-side ``subject`` it backs, and every
derivation -- ``ladder_violations``, ``cross_family_incoherence``,
``lattice_conviction`` -- segregates or matches on that subject before
comparing. Game-level totals back no single team (``subject is None``) and
form their own single ladder.

Known scope limitation (documented, not silently assumed): ``SportsContract``
carries no home/away flag, so games are keyed on a SORTED pair of competitor
labels rather than a fixed away/home order. For MLB (§4's live-now target),
winner/spread/total all derive their competitors from the SAME ticker-
embedded team abbreviations, so grouping is exact and the subject-aware
checks are fully effective. For the generic team-sports parser
(NBA/NFL/NCAAF/NHL/NCAAMB, pre-existing in ``sports_intelligence.py``), the
winner family's competitors come from the ticker suffix (abbreviations)
while spread/total come from the market TITLE (full team names) -- two
different string spaces, so winner and spread/total for those sports land
under different game_keys and do not yet cross-group (their same-family
ladders still group and are subject-segregated correctly). That is a
pre-existing asymmetry in ``parse_sports_contract``; it degrades gracefully
(smaller/partial lattices, never a false violation -- subject-awareness
holds regardless) and closes out as each sport's specialist ships (spec:
"seeded on MLB, inherited free by every later specialist").
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from autonomy.mispricing import MispricingAssessment
from autonomy.signals.sports_intelligence import SportsContract, parse_sports_contract

# Rung-gap must exceed this combined fee/spread slack to count as a real
# monotonicity break (not just bid/ask noise).
FEE_BAND = 0.03

TIER_STRUCTURAL = "structural"
TIER_CROSS_CONFIRMED = "cross_confirmed"
TIER_MODEL_BOOK = "model+book"
TIER_MODEL_ONLY = "model_only"

# Total order (low -> high); used both to pick the per-game tier and to sort
# the report's lattice rows richest-first.
TIER_RANK: dict[str | None, int] = {
    None: 0,
    TIER_MODEL_ONLY: 1,
    TIER_MODEL_BOOK: 2,
    TIER_CROSS_CONFIRMED: 3,
    TIER_STRUCTURAL: 4,
}

_FAMILY_BY_MARKET_TYPE = {
    "winner": "winner",
    "spread": "spread",
    "total": "total",
    "total_runs": "total",  # MLB's own family name for the same "total" slot
}


@dataclass(frozen=True)
class LatticeCell:
    family: str            # "winner" | "spread" | "total"
    ticker: str
    # The per-SIDE subject this cell backs when YES resolves: the specific
    # team for winner/spread (e.g. "HOU" vs "TEX" -- the two opposite spread
    # sides of one game are DISTINCT subjects), or None for a game-level
    # total (over/under the combined score backs no single team). Every
    # subject-aware derivation below keys on this so opposite-team cells are
    # never compared as if they were rungs/confirmations of one another.
    subject: str | None
    line: float | None
    model_prob: float | None
    book_prob: float | None
    kalshi_prob: float | None


@dataclass(frozen=True)
class GameLattice:
    game_key: str          # f"{sport}:{date}:{a}@{b}" (a, b canonical-sorted)
    sport: str
    cells: list[LatticeCell]


def _canonical_game_key(sport: str, date_yyyymmdd: str, competitors: tuple[str, str]) -> str:
    left, right = sorted(competitors)
    return f"{sport}:{date_yyyymmdd}:{left}@{right}"


def build_game_lattices(
    markets: Iterable[Any], assessments: dict[str, MispricingAssessment],
) -> list[GameLattice]:
    """Group scanned markets into per-game 3x3 lattices.

    Cells are populated from the ALREADY-COMPUTED ``assessments`` (ticker ->
    MispricingAssessment) the sweep produced from its own ``forecast_fn``/
    ``book_fn`` -- no second fetch, no second model call. Grouping itself
    goes through the real ``parse_sports_contract`` (sport, date,
    competitors, family, line) so it is exercised exactly the way live
    markets are, not through a hand-built dict that could silently drift
    from the real field mapping.

    Fail-closed: a market with no assessment (no model view), a market that
    does not parse to a sports contract, or a contract whose family is not
    winner/spread/total (e.g. MLB's yrfi) contributes no cell and is simply
    not grouped.
    """
    by_game: dict[str, list[LatticeCell]] = {}
    sport_by_game: dict[str, str] = {}
    for market in markets:
        ticker = getattr(market, "ticker", None)
        if not ticker:
            continue
        assessment = assessments.get(ticker)
        if assessment is None:
            continue
        try:
            contract = parse_sports_contract(market)
        except Exception:
            continue
        if contract is None or not contract.competitors:
            continue
        family = _FAMILY_BY_MARKET_TYPE.get(contract.market_type)
        if family is None:
            continue
        game_key = _canonical_game_key(contract.sport, contract.date_yyyymmdd, contract.competitors)
        cell = LatticeCell(
            family=family, ticker=ticker, subject=contract.subject,
            line=contract.threshold,
            model_prob=assessment.model_prob, book_prob=assessment.book_prob,
            kalshi_prob=assessment.market_prob,
        )
        by_game.setdefault(game_key, []).append(cell)
        sport_by_game[game_key] = contract.sport
    return [
        GameLattice(game_key=key, sport=sport_by_game[key], cells=cells)
        for key, cells in by_game.items()
    ]


def ladder_violations(cells: list[LatticeCell], family: str) -> list[dict]:
    """Kalshi's own rung monotonicity within one family -- needs NO model.

    SUBJECT-AWARE: monotonicity only holds along rungs that back the SAME
    subject. A single MLB game routinely lists BOTH sides' spread markets
    (e.g. "HOU covers 1.5" AND "TEX covers 1.5") -- these are near-
    complementary probabilities at the SAME line for OPPOSITE teams, not
    two rungs of one ladder. Comparing them would fabricate a structural
    violation on essentially every game, so this function segregates
    ``cells`` by ``subject`` first and scans each subject's rungs
    independently. (Game-level totals share ``subject is None``; that is one
    real ladder -- over/under the combined score -- so they stay grouped,
    which is correct.)

    Covering a bigger margin (spread) or clearing a higher line (total) is
    strictly harder, so within one subject Kalshi's own quoted probability
    must be non-increasing as the line rises: for rungs k1 < k2,
    ``P_kalshi(cover k1) >= P_kalshi(cover k2) - FEE_BAND``. A break beyond
    that fee/spread slack between adjacent same-subject rungs is a
    structural incoherence -- an edge requiring no model opinion, only
    Kalshi's own internal consistency.
    """
    by_subject: dict[str | None, list[LatticeCell]] = {}
    for c in cells:
        if c.family == family and c.line is not None and c.kalshi_prob is not None:
            by_subject.setdefault(c.subject, []).append(c)

    violations: list[dict] = []
    for subject, subject_cells in by_subject.items():
        ladder = sorted(subject_cells, key=lambda c: c.line)
        for lo, hi in zip(ladder, ladder[1:]):
            gap = lo.kalshi_prob - hi.kalshi_prob  # expected >= 0
            if gap < -FEE_BAND:
                violations.append({
                    "family": family,
                    "subject": subject,
                    "rungs": (lo.line, hi.line),
                    "tickers": (lo.ticker, hi.ticker),
                    "gap": round(gap, 4),
                    "tier": TIER_STRUCTURAL,
                })
    return violations


def cross_family_incoherence(lattice: GameLattice) -> list[dict]:
    """Winner-implied vs. spread-implied P(win) gaps (needs the model shape).

    Each specialist prices winner + spread from ONE joint score
    distribution; Kalshi prices them as independent markets set by
    independent crowds. This maps Kalshi's spread price onto an implied
    winner probability via a FIRST-ORDER LINEAR TRANSPORT through the
    model's own distribution shape (documented approximation, not the
    model's exact joint law):

        implied_win = model_win - model_cover(k) + kalshi_cover(k)

    i.e. start from the model's own win probability and add back only the
    portion of the spread-cover disagreement that is Kalshi's (not the
    model's). A gap between Kalshi's actual quoted winner probability and
    this implied value beyond ``2 * FEE_BAND`` means Kalshi's own winner and
    spread markets disagree about the game by more than fee/spread slack can
    explain, given the model's shape.

    SUBJECT-AWARE: the transport only makes sense when the winner cell and
    the spread cell back the SAME team -- "HOU wins" reconciled against
    "HOU covers 1.5", never against "TEX covers 1.5" (which backs the
    opponent). Only (winner, spread) pairs whose ``subject`` matches are
    checked; pairs missing any required probability are skipped (fail-closed
    -- no fabricated rows).
    """
    winners = [c for c in lattice.cells if c.family == "winner"]
    spreads = [c for c in lattice.cells if c.family == "spread"]
    rows: list[dict] = []
    for w in winners:
        if w.model_prob is None or w.kalshi_prob is None:
            continue
        for s in spreads:
            if s.subject != w.subject:
                continue  # opposite-team pairing -- transport is meaningless
            if s.model_prob is None or s.kalshi_prob is None or s.line is None:
                continue
            implied_win = w.model_prob - s.model_prob + s.kalshi_prob
            gap = w.kalshi_prob - implied_win
            if abs(gap) > 2 * FEE_BAND:
                rows.append({
                    "game_key": lattice.game_key,
                    "family": "winner_vs_spread",
                    "subject": w.subject,
                    "line": s.line,
                    "kalshi_winner": round(w.kalshi_prob, 4),
                    "implied_win": round(implied_win, 4),
                    "gap": round(gap, 4),
                    "winner_ticker": w.ticker,
                    "spread_ticker": s.ticker,
                })
    return rows


def lattice_conviction(
    lattice: GameLattice, assessments: dict[str, MispricingAssessment],
) -> dict:
    """Per-game conviction tier: structural > cross_confirmed > model+book > model_only.

    ``assessments`` is the full ticker -> MispricingAssessment map the sweep
    already computed; only tickers that are cells of this lattice matter.

    * ``structural`` -- any (subject-aware) ladder violation (spread or
      total) fires for this game; the strongest tier, needs no model
      opinion.
    * ``cross_confirmed`` -- an actionable edge (real side, book agreement)
      backs the SAME team in the SAME direction across >= 2 distinct
      families. Cross-cell confirmation is keyed on ``(subject, side)``, not
      side alone: a YES on "HOU wins" and a YES on "HOU covers 1.5" both
      back HOU and confirm each other, but a YES on "HOU wins" and a YES on
      "TEX covers 1.5" back OPPOSITE teams and must NOT be read as
      agreement. This is the strongest signal the system can emit short of a
      structural break.
    * ``model+book`` -- at least one cell has book agreement, but no
      cross-family (same-team) confirmation.
    * ``model_only`` -- at least one cell has an actionable model side with
      no book confirmation.
    * ``None`` -- fail-closed: the lattice's cells never reach any tier
      (e.g. every cell assessed to side "NONE").

    A game that lacks the cells for a tier simply cannot reach it -- e.g. a
    single-cell lattice can never be ``structural`` (needs 2 same-subject
    ladder rungs) or ``cross_confirmed`` (needs 2 distinct families backing
    one team).
    """
    tier: str | None = None
    if ladder_violations(lattice.cells, "spread") or ladder_violations(lattice.cells, "total"):
        tier = TIER_STRUCTURAL
    else:
        cell_assessments = [
            (cell, assessments[cell.ticker])
            for cell in lattice.cells
            if cell.ticker in assessments
        ]
        # Key confirmation on (subject, side): only cells backing the SAME
        # team in the SAME direction, in >= 2 distinct families, cross-confirm.
        families_by_team: dict[tuple[str | None, str], set[str]] = {}
        for cell, assessment in cell_assessments:
            if assessment.agreement == TIER_MODEL_BOOK and assessment.side in ("YES", "NO"):
                families_by_team.setdefault((cell.subject, assessment.side), set()).add(cell.family)
        if any(len(families) >= 2 for families in families_by_team.values()):
            tier = TIER_CROSS_CONFIRMED
        elif any(a.agreement == TIER_MODEL_BOOK for _, a in cell_assessments):
            tier = TIER_MODEL_BOOK
        elif any(a.side != "NONE" for _, a in cell_assessments):
            tier = TIER_MODEL_ONLY

    return {
        "game_key": lattice.game_key,
        "sport": lattice.sport,
        "conviction_tier": tier,
        "cell_count": len(lattice.cells),
    }
