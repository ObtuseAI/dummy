"""Triangulated mispricing engine: our model vs the sharp book vs the price.

Three independent estimates of a binary market's true probability meet here:

  1. ``model_prob`` — our own forecast (e.g. the live plate-appearance sim's
     win probability, or any fused source probability).
  2. ``book_prob`` — the de-vigged sportsbook consensus (optional; the sharpest
     public number when it exists). See ``autonomy.signals.sportsbook``.
  3. the **market** — what Kalshi will actually fill, implied by the executable
     quotes (you pay the ask to take a side).

The novel core is the *agreement* logic. When our independent model AND the
sharp book BOTH say the market price is wrong in the SAME direction, that is
the highest-confidence edge — two uncorrelated sharp estimators agree the
price is off. When they conflict (model likes one side, book the other), we do
NOT pretend to know: the assessment is flagged low-confidence and the
per-source contested-Brier record is left to settle who was right (books earn
that trust fast). With no book, the model stands alone at medium confidence.

Pure and deterministic. Every threshold is explicit. Missing/naive quotes ->
a NONE assessment (fail-closed); the caller simply does not act.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}

# An actionable side needs at least this much fair-vs-price edge (probability).
DEFAULT_EDGE_THRESHOLD = 0.04
# The book must lead/lag the market by at least this much to count as
# confirming or conflicting (inside this band the book is treated as neutral).
DEFAULT_AGREE_MARGIN = 0.02
# Thin books require MORE edge before an assessment is actionable: a marginal
# edge on a market with almost no depth is usually un-executable at that price
# (you move the book taking it), so it pollutes the shortlist. Thresholds are
# RESTING LIQUIDITY IN CENTS -- MarketView.liquidity is cents (the scanner
# derives it from Kalshi's liquidity / liquidity_dollars*100). Most-restrictive
# tier first: under $50 of depth (+0.04), under $200 (+0.02), deeper is neutral.
LIQUIDITY_EDGE_FLOOR_TIERS: tuple[tuple[int, float], ...] = ((5_000, 0.04), (20_000, 0.02))


def liquidity_edge_floor(liquidity: int | None) -> float:
    """Extra fair-vs-price edge for a thin book, keyed on resting cents.

    ``None`` (unknown depth) is neutral (0.0); a reported 0 is genuinely
    empty and gets the most-restrictive floor.
    """
    if liquidity is None:
        return 0.0
    try:
        depth_cents = int(liquidity)
    except (TypeError, ValueError):
        return 0.0
    for threshold, extra in LIQUIDITY_EDGE_FLOOR_TIERS:
        if depth_cents < threshold:
            return extra
    return 0.0


@dataclass(frozen=True)
class MispricingAssessment:
    market_ticker: str
    side: str            # "YES" | "NO" | "NONE"
    model_prob: float
    market_prob: float | None   # mid implied by the executable quotes; None if unpriced
    book_prob: float | None
    edge: float          # signed fair-minus-price edge on the chosen side (>=0 when actionable)
    agreement: str       # "model+book" | "model_only" | "conflict" | "none"
    confidence: str      # "high" | "medium" | "low"
    rationale: str
    # WS-5 (autonomy/coherence.py): optional per-game lattice conviction tier
    # ("structural" | "cross_confirmed" | "model+book" | "model_only" | None).
    # Absent/None is byte-identical to pre-WS-5 behavior everywhere it is
    # consumed (autonomy/opportunist.py's anchor-threshold relaxation).
    conviction_tier: str | None = None
    # CF1 (Phenon WS-A2): optional power-ratings divergence evidence for this
    # market -- the dict PowerRatingsSignal attaches when the external-ratings
    # ensemble disagrees with our own engine while the ratings sources agree
    # ({gap, ensemble_margin, our_engine_margin, dispersion, kalshi_mid, sport}).
    # Surfaced as buy-low EVIDENCE only (opportunist rationale + report rows +
    # dashboard); it never changes the actionable side/edge/confidence or the
    # opportunist gating while power_ratings remains an unpromoted challenger.
    # Absent/None is byte-identical to the field never existing.
    power_divergence: dict[str, Any] | None = None


def _implied_yes_from_quotes(
    yes_ask: int | None, no_ask: int | None
) -> tuple[float | None, float | None, float | None]:
    """(cost to hold YES, cost to hold NO, mid YES prob) from cent quotes.

    Kalshi quotes are integer cents = probability*100. You pay ``yes_ask`` to
    hold YES and ``no_ask`` to hold NO; the mid YES prob blends the YES ask with
    the complement of the NO ask (the two-sided book's center).
    """
    yes_cost = yes_ask / 100.0 if yes_ask and 0 < yes_ask < 100 else None
    no_cost = no_ask / 100.0 if no_ask and 0 < no_ask < 100 else None
    if yes_cost is not None and no_cost is not None:
        mid = (yes_cost + (1.0 - no_cost)) / 2.0
    elif yes_cost is not None:
        mid = yes_cost
    elif no_cost is not None:
        mid = 1.0 - no_cost
    else:
        mid = None
    return yes_cost, no_cost, mid


def assess_mispricing(
    market_ticker: str,
    model_prob: float,
    yes_ask: int | None,
    no_ask: int | None,
    *,
    book_prob: float | None = None,
    edge_threshold: float = DEFAULT_EDGE_THRESHOLD,
    agree_margin: float = DEFAULT_AGREE_MARGIN,
    liquidity: int | None = None,
) -> MispricingAssessment:
    """Assess whether the market is mispriced vs the model (and book).

    ``yes_ask``/``no_ask`` are the executable ask quotes in cents. Returns a
    NONE assessment (no actionable edge) when quotes are missing or neither side
    clears the effective threshold (``edge_threshold`` plus a thin-book floor
    from ``liquidity``).
    """
    model_prob = min(1.0, max(0.0, float(model_prob)))
    yes_cost, no_cost, mid = _implied_yes_from_quotes(yes_ask, no_ask)
    effective_threshold = edge_threshold + liquidity_edge_floor(liquidity)

    # Edge = our fair probability minus what we pay to hold that side.
    yes_edge = (model_prob - yes_cost) if yes_cost is not None else None
    no_edge = ((1.0 - model_prob) - no_cost) if no_cost is not None else None

    side = "NONE"
    edge = 0.0
    candidates = []
    if yes_edge is not None:
        candidates.append(("YES", yes_edge))
    if no_edge is not None:
        candidates.append(("NO", no_edge))
    if candidates:
        best_side, best_edge = max(candidates, key=lambda item: item[1])
        if best_edge >= effective_threshold:
            side, edge = best_side, best_edge

    if mid is None or side == "NONE":
        return MispricingAssessment(
            market_ticker=market_ticker, side="NONE", model_prob=model_prob,
            market_prob=mid, book_prob=book_prob,
            edge=0.0, agreement="none", confidence="low",
            rationale=(
                "no executable quote" if mid is None
                else f"no side clears {effective_threshold:.0%} edge (best model vs mid)"
            ),
        )

    # Triangulate against the book, if present. "cheap" = underpriced by the
    # market on the side the model likes.
    if book_prob is not None:
        book_prob = min(1.0, max(0.0, float(book_prob)))
        if side == "YES":
            book_lead = book_prob - mid
        else:  # NO: underpricing of NO means the market's YES is too HIGH
            book_lead = mid - book_prob
        if book_lead >= agree_margin:
            agreement, confidence = "model+book", "high"
            note = f"book confirms ({book_prob:.2f} vs mid {mid:.2f})"
        elif book_lead <= -agree_margin:
            agreement, confidence = "conflict", "low"
            note = f"book CONFLICTS ({book_prob:.2f} vs mid {mid:.2f}); defer to record"
        else:
            agreement, confidence = "model_only", "medium"
            note = f"book neutral ({book_prob:.2f} vs mid {mid:.2f})"
    else:
        agreement, confidence = "model_only", "medium"
        note = "no book"

    return MispricingAssessment(
        market_ticker=market_ticker, side=side, model_prob=model_prob,
        market_prob=mid, book_prob=book_prob, edge=edge,
        agreement=agreement, confidence=confidence,
        rationale=(
            f"{side} edge {edge:+.2%} (model {model_prob:.2f} vs mid {mid:.2f}); {note}"
        ),
    )


class MispricingMonitor:
    """A stateless buy-low pass: score a batch of markets for mispricing.

    Injectable so it is exercised without a live daemon: ``forecast_fn`` returns
    our model probability for a market (None -> skip, fail-closed), and the
    optional ``book_fn`` returns the de-vigged sportsbook probability. The scan
    returns the actionable assessments (a real side, at or above
    ``min_confidence``), richest edge first — the buy-low shortlist a fast
    monitor loop or the dashboard consumes. Same engine for sports and crypto;
    crypto simply has no ``book_fn``.
    """

    def __init__(
        self,
        forecast_fn: Callable[[Any], float | None],
        book_fn: Callable[[Any], float | None] | None = None,
        *,
        edge_threshold: float = DEFAULT_EDGE_THRESHOLD,
        agree_margin: float = DEFAULT_AGREE_MARGIN,
        min_confidence: str = "medium",
    ) -> None:
        self.forecast_fn = forecast_fn
        self.book_fn = book_fn
        self.edge_threshold = edge_threshold
        self.agree_margin = agree_margin
        self.min_confidence = min_confidence

    def _meets_confidence(self, confidence: str) -> bool:
        return _CONFIDENCE_RANK.get(confidence, 0) >= _CONFIDENCE_RANK.get(self.min_confidence, 1)

    def assess_market(self, market: Any) -> MispricingAssessment | None:
        """Assess one market; None when we have no model view (fail-closed)."""
        try:
            model_prob = self.forecast_fn(market)
        except Exception:
            return None
        if model_prob is None:
            return None
        book_prob = None
        if self.book_fn is not None:
            try:
                book_prob = self.book_fn(market)
            except Exception:
                book_prob = None
        return assess_mispricing(
            getattr(market, "ticker", ""),
            float(model_prob),
            getattr(market, "yes_ask", None),
            getattr(market, "no_ask", None),
            book_prob=book_prob,
            edge_threshold=self.edge_threshold,
            agree_margin=self.agree_margin,
            liquidity=getattr(market, "liquidity", None),
        )

    def scan(self, markets: list[Any]) -> list[MispricingAssessment]:
        """Actionable buy-low assessments, richest edge first.

        A model+book CONFLICT never makes the shortlist regardless of edge — we
        do not fight the sharp book on faith; that market waits for the
        contested-Brier record to settle who is right.
        """
        found: list[MispricingAssessment] = []
        for market in markets:
            assessment = self.assess_market(market)
            if assessment is None or assessment.side == "NONE":
                continue
            if assessment.agreement == "conflict":
                continue
            if not self._meets_confidence(assessment.confidence):
                continue
            found.append(assessment)
        return sorted(found, key=lambda a: a.edge, reverse=True)
