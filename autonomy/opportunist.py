"""Patience / opportunist engine: pre-lock conviction, pounce on the dip.

A static edge scan buys whatever looks cheap right now. The opportunist is
patient: it LOCKS a high-conviction candidate at its (efficient) anchor price
-- a strong pre-game favorite our model rates well above the market -- then
WAITS, and only strikes when an early-game deviation discounts the executable
price below our fair value (the favorite falls behind early, the price dips,
but our live model still likes them). The wait is the edge: buying the same
outcome cheaper after a temporary overreaction.

Stateful, deterministic, fail-closed. It consumes ``MispricingAssessment``
objects (from ``autonomy.mispricing``) so it inherits the model-vs-book
triangulation: it never pounces into a book CONFLICT or a low-confidence read,
and it never fires at the lock-in anchor (patience is enforced by requiring a
real move away from the anchor before triggering).
"""
from __future__ import annotations

from dataclasses import dataclass

from autonomy.mispricing import MispricingAssessment, _CONFIDENCE_RANK

# A candidate must be at least this confident (model P on its favored side) to
# be worth watching at all.
DEFAULT_CONVICTION_FLOOR = 0.62
# The dip must open at least this much fair-vs-price edge to strike.
DEFAULT_TRIGGER_EDGE = 0.06
# ...and the market must have moved at least this far against the favored side
# since the anchor (the "deviation"), so we do not fire at the entry price.
DEFAULT_MIN_DEVIATION = 0.03

# WS-5 (autonomy/coherence.py): a lattice conviction tier on the assessment
# lowers the lock-in conviction floor -- a structural (ladder-violation) or
# cross_confirmed (independent cross-family agreement) read is trustworthy
# evidence on its own, so the model doesn't need to clear the full 0.62 bar
# to be worth watching. Unknown/absent tiers get no drop (byte-identical).
CONVICTION_TIER_ANCHOR_DROP: dict[str, float] = {
    "structural": 0.04,
    "cross_confirmed": 0.02,
}


def _favored(model_prob: float) -> tuple[str, float]:
    """(favored side, conviction) — the side the model backs and how strongly."""
    return ("YES", model_prob) if model_prob >= 0.5 else ("NO", 1.0 - model_prob)


def _confirming_divergence(divergence: dict | None, side: str) -> dict | None:
    """Return the divergence dict iff it CONFIRMS the favored side, else None.

    ``divergence`` carries a HOME-signed ``gap = ensemble_margin -
    our_engine_margin`` (positive when the external ensemble is more bullish on
    the HOME team than our engine) plus ``subject_is_home`` telling us how this
    market's YES side relates to the home team. The opportunist's ``side`` is
    SUBJECT-oriented, so we re-sign the gap to the subject first: a YES on an
    away-subject market ("Will [away] win?") is confirmed by a gap that favors
    the AWAY team (home-signed gap < 0). A YES lean is confirmed by a positive
    subject-oriented gap, a NO lean by a negative one. Zero/absent/malformed or
    counter-signed gaps are not surfaced. Pure evidence — never gates the strike.
    """
    if not divergence:
        return None
    gap = divergence.get("gap")
    if not isinstance(gap, (int, float)) or isinstance(gap, bool) or gap == 0:
        return None
    # Re-sign the home-signed gap to this market's subject. Absent orientation
    # defaults to home-subject (backward-compatible with a home-implied dict).
    subject_gap = gap if divergence.get("subject_is_home", True) else -gap
    confirms = subject_gap > 0 if side == "YES" else subject_gap < 0
    return divergence if confirms else None


@dataclass
class Candidate:
    ticker: str
    side: str              # favored side at lock-in ("YES"/"NO")
    conviction: float      # model P on the favored side at lock-in
    anchor_prob: float     # market mid (implied YES prob) when locked
    triggered: bool = False


@dataclass(frozen=True)
class Opportunity:
    ticker: str
    side: str
    conviction: float
    anchor_prob: float
    entry_prob: float      # market mid at the strike
    edge: float
    deviation: float       # how far the price moved against the favored side
    confidence: str
    rationale: str
    # CF1: power-ratings divergence evidence present at the strike, when the
    # external-ratings ensemble also disagreed with our engine on this market
    # (surfaced for review only; it does not gate the strike). None otherwise.
    power_divergence: dict | None = None
    # Raw ESPN live-play observations present at the strike. Evidence-only;
    # never part of the trigger predicate or any probability adjustment.
    ejection_events: tuple[dict, ...] = ()


class OpportunistEngine:
    """Track high-conviction candidates and fire when the dip arrives."""

    def __init__(
        self,
        *,
        conviction_floor: float = DEFAULT_CONVICTION_FLOOR,
        trigger_edge: float = DEFAULT_TRIGGER_EDGE,
        min_deviation: float = DEFAULT_MIN_DEVIATION,
        min_confidence: str = "medium",
    ) -> None:
        self.conviction_floor = conviction_floor
        self.trigger_edge = trigger_edge
        self.min_deviation = min_deviation
        self.min_confidence = min_confidence
        self.candidates: dict[str, Candidate] = {}

    def _meets_confidence(self, confidence: str) -> bool:
        return _CONFIDENCE_RANK.get(confidence, 0) >= _CONFIDENCE_RANK.get(self.min_confidence, 1)

    def observe(self, assessment: MispricingAssessment) -> Opportunity | None:
        """Feed one assessment; return an Opportunity only when the dip triggers.

        Locks a candidate the first time we see it with high conviction and a
        real quote. On later observations, fires once when the favored side is
        discounted past ``trigger_edge`` AND the price has deviated at least
        ``min_deviation`` against the favored side since the anchor. Fires at
        most once per candidate; never on a book conflict or below
        ``min_confidence``.
        """
        if assessment.market_prob is None:
            return None  # no executable price -> nothing to anchor or strike on
        side, conviction = _favored(assessment.model_prob)
        mid = assessment.market_prob

        candidate = self.candidates.get(assessment.market_ticker)
        if candidate is None:
            tier = getattr(assessment, "conviction_tier", None)
            effective_floor = self.conviction_floor - CONVICTION_TIER_ANCHOR_DROP.get(tier, 0.0)
            if conviction < effective_floor:
                return None  # not a candidate worth the patience
            candidate = Candidate(
                ticker=assessment.market_ticker, side=side,
                conviction=conviction, anchor_prob=mid,
            )
            self.candidates[assessment.market_ticker] = candidate
            # No strike on the lock-in observation: patience means waiting for a
            # move away from this anchor.
            return None

        # Deviation = how far the price has moved AGAINST the favored side since
        # the anchor (YES favored -> YES prob fell; NO favored -> YES prob rose).
        deviation = (candidate.anchor_prob - mid) if candidate.side == "YES" else (mid - candidate.anchor_prob)
        if (
            not candidate.triggered
            and assessment.side == candidate.side
            and assessment.agreement != "conflict"
            and self._meets_confidence(assessment.confidence)
            and assessment.edge >= self.trigger_edge
            and deviation >= self.min_deviation
        ):
            candidate.triggered = True
            rationale = (
                f"{candidate.side} conviction {candidate.conviction:.2f}; price "
                f"dipped {deviation:+.2%} from anchor {candidate.anchor_prob:.2f} to "
                f"{mid:.2f}, opening {assessment.edge:.2%} edge ({assessment.confidence})"
            )
            # CF1: surface a same-side power-ratings divergence as extra evidence
            # (never a gate -- power_ratings is an unpromoted challenger). The
            # ensemble confirms the favored side when its home-signed gap points
            # the same way: YES favored -> gap>0 (ensemble even more bullish on
            # home), NO favored -> gap<0.
            divergence = _confirming_divergence(assessment.power_divergence, candidate.side)
            if divergence is not None:
                rationale += (
                    f"; power-ratings ensemble confirms ({divergence['gap']:+.1f} pt gap "
                    f"vs our engine, sources agree)"
                )
            if assessment.ejection_events:
                rationale += (
                    f"; {len(assessment.ejection_events)} live ejection "
                    f"observation{'s' if len(assessment.ejection_events) != 1 else ''}"
                )
            return Opportunity(
                ticker=candidate.ticker, side=candidate.side,
                conviction=candidate.conviction, anchor_prob=candidate.anchor_prob,
                entry_prob=mid, edge=assessment.edge, deviation=deviation,
                confidence=assessment.confidence, rationale=rationale,
                power_divergence=divergence,
                ejection_events=assessment.ejection_events,
            )
        return None
