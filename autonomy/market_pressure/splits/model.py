"""Betting-splits model + intelligently-weighted multi-source fusion.

Each source reports, for one game, the share of BETS (tickets) and where
available the share of MONEY (handle) on each side. The two together are the
signal: when money% runs ahead of ticket% on a side, fewer-but-bigger (sharp)
bets are there; when ticket% runs ahead of money%, it is many-small (public)
bets. ``combine_splits`` fuses several sources into one read, weighting each by
how much to trust it -- money-carrying books over ticket-only consensus,
recent over stale, complete over partial -- and reports how tightly the
sources agree.
"""
from __future__ import annotations

from dataclasses import dataclass

# Per-source base reliability. Money%-carrying sources (real-book handle) are
# trusted more than ticket-only consensus; the values are relative weights,
# not probabilities. Retuned by evidence later; conservative to start.
SOURCE_WEIGHTS: dict[str, float] = {
    "action_network": 1.0,   # ticket% + money%, large sample
    "vsin": 0.9,             # DraftKings ticket% + handle%
    "covers": 0.55,          # ticket% consensus only
    "sbr": 0.5,              # ticket% consensus only
}
DEFAULT_SOURCE_WEIGHT = 0.4
# A read older than this contributes nothing (splits move; a stale split is a
# different game state).
MAX_AGE_SECONDS = 3 * 3600.0
# Money% sources carry extra weight in the money channel specifically.
MONEY_WEIGHT_BONUS = 1.5


@dataclass(frozen=True)
class SplitsRead:
    """One source's split for one game's two-way market (moneyline default)."""

    source: str
    home_team: str
    away_team: str
    home_ticket_pct: float | None      # 0..1
    away_ticket_pct: float | None
    home_money_pct: float | None = None
    away_money_pct: float | None = None
    as_of: float | None = None         # epoch seconds
    market: str = "moneyline"

    def has_tickets(self) -> bool:
        return self.home_ticket_pct is not None and self.away_ticket_pct is not None

    def has_money(self) -> bool:
        return self.home_money_pct is not None and self.away_money_pct is not None


@dataclass(frozen=True)
class FusedSplits:
    has_read: bool
    home_ticket_pct: float | None
    away_ticket_pct: float | None
    home_money_pct: float | None
    away_money_pct: float | None
    sources: tuple[str, ...] = ()
    confidence: float = 0.0
    # Signed money-minus-ticket on the HOME side; + = sharp money on home.
    home_money_ticket_gap: float | None = None
    disagreement: float = 0.0          # ticket% spread across sources (0 = lockstep)

    def sharp_side(self, home: str, away: str, threshold: float = 0.07) -> str | None:
        """The side whose money share leads its ticket share by ``threshold``
        (the classic sharp tell). None when there is no money channel or the
        gap is within noise."""
        if self.home_money_ticket_gap is None:
            return None
        if self.home_money_ticket_gap >= threshold:
            return home
        if self.home_money_ticket_gap <= -threshold:
            return away
        return None

    def public_side(self, home: str, away: str) -> str | None:
        if self.home_ticket_pct is None or self.away_ticket_pct is None:
            return None
        return home if self.home_ticket_pct >= self.away_ticket_pct else away

    def as_dict(self) -> dict:
        return {
            "has_read": self.has_read,
            "home_ticket_pct": _round(self.home_ticket_pct),
            "away_ticket_pct": _round(self.away_ticket_pct),
            "home_money_pct": _round(self.home_money_pct),
            "away_money_pct": _round(self.away_money_pct),
            "home_money_ticket_gap": _round(self.home_money_ticket_gap),
            "sources": list(self.sources),
            "confidence": round(self.confidence, 3),
            "disagreement": round(self.disagreement, 4),
        }


_NO_SPLITS = FusedSplits(False, None, None, None, None)


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def _weight(read: SplitsRead, now: float) -> float:
    base = SOURCE_WEIGHTS.get(read.source, DEFAULT_SOURCE_WEIGHT)
    if read.as_of is not None:
        age = now - read.as_of
        if age > MAX_AGE_SECONDS:
            return 0.0
        # Linear decay to half-weight at the max age.
        base *= max(0.5, 1.0 - 0.5 * age / MAX_AGE_SECONDS)
    return base


def _normalize(home: float | None, away: float | None) -> tuple[float | None, float | None]:
    """Force a two-way share to sum to 1 when both present (sources round or
    report 48/52 vs 0.48/0.52); pass through partial reads untouched."""
    if home is None or away is None:
        return home, away
    total = home + away
    if total <= 0:
        return None, None
    scale = 100.0 if total > 1.5 else 1.0     # percent vs fraction
    home, away = home / scale, away / scale
    total = home + away
    return home / total, away / total


def combine_splits(reads: list[SplitsRead], *, now: float) -> FusedSplits:
    """Intelligently-weighted fusion of several sources' splits for one game.

    Ticket% is fused across every usable source; money% across the sources
    that carry it (with a bonus weight, since handle is the sharper signal).
    Confidence rises with total weight and source count and falls with
    cross-source disagreement."""
    usable = []
    for read in reads:
        if not read.has_tickets():
            continue
        weight = _weight(read, now)
        if weight <= 0:
            continue
        ht, at = _normalize(read.home_ticket_pct, read.away_ticket_pct)
        hm, am = _normalize(read.home_money_pct, read.away_money_pct)
        if ht is None:
            continue
        usable.append((read.source, weight, ht, at, hm, am))
    if not usable:
        return _NO_SPLITS

    tw = sum(w for _s, w, *_ in usable)
    home_ticket = sum(w * ht for _s, w, ht, _at, _hm, _am in usable) / tw
    away_ticket = 1.0 - home_ticket

    money_terms = [(w * (MONEY_WEIGHT_BONUS), hm)
                   for _s, w, _ht, _at, hm, _am in usable if hm is not None]
    if money_terms:
        mw = sum(w for w, _ in money_terms)
        home_money = sum(w * hm for w, hm in money_terms) / mw
        away_money = 1.0 - home_money
        gap = home_money - home_ticket
    else:
        home_money = away_money = gap = None

    ticket_values = [ht for _s, _w, ht, _at, _hm, _am in usable]
    disagreement = max(ticket_values) - min(ticket_values) if len(ticket_values) > 1 else 0.0

    # Confidence: saturating in total weight and count, penalised by spread.
    n = len(usable)
    weight_term = min(1.0, tw / 2.0)
    count_term = min(1.0, n / 3.0)
    agree_term = max(0.0, 1.0 - disagreement / 0.3)
    confidence = round(0.4 * weight_term + 0.3 * count_term + 0.3 * agree_term, 3)

    return FusedSplits(
        has_read=True,
        home_ticket_pct=home_ticket,
        away_ticket_pct=away_ticket,
        home_money_pct=home_money,
        away_money_pct=away_money,
        sources=tuple(s for s, *_ in usable),
        confidence=confidence,
        home_money_ticket_gap=gap,
        disagreement=disagreement,
    )
