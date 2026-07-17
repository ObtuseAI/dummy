"""Honest-quote guards: stop grading (or anchoring) against fabricated mids.

Wave-5 P0-A. The 2026-07-17 audit found the single largest evidence defect in
the system: the "market opinion" used both as the fusion anchor and as the
grading benchmark was the raw ``(yes_bid + yes_ask) / 2`` mid with no quality
check. A dead or wide book (bid 1 / ask 99) fabricates a ~50c "market" that
nobody is quoting; a model that is trivially right on a deep-OTM strike then
"beats the market" by ~0.24 Brier per row. Ledger proof: 240 settled crypto
ladder decisions had a mid in [0.35, 0.65] while the model was beyond 90/10 --
the model "won" 99.2% of them. That phantom edge inflated source trust to the
multiplicative cap, tripped the weight-saturation rail, and made crypto look
light-years better than sports when in truth (on honestly-quoted 15m books)
crypto's edge is modest and MLB is graded against sharp prices.

Three guards, one module, shared by every consumer:

  * :func:`honest_implied_yes` -- the ONLY sanctioned way to turn a book into
    an implied probability. Returns None unless the quote is real: bid >= 1c,
    ask <= 99c, non-crossed, spread <= MAX_HONEST_SPREAD_CENTS.
  * :data:`CONTESTED_DISAGREEMENT` -- the shared contested threshold, so the
    learner and the backtest cannot drift apart on what "disagreement" means.
  * :func:`suspect_crypto_contested_pair` -- read-side quarantine for the
    HISTORICAL rows written before this gate existed (bid/ask were never
    persisted, so the fabrication can only be recognized by its signature:
    a crypto market whose recorded prior sits in the coin-flip band while the
    model is >= 30 points away). Restricted to CRYPTO because the fabrication
    engine was dead ladder books; sports books on Kalshi are actively quoted.

Fail-closed everywhere: no honest quote means no anchor, no benchmark, and no
trust movement -- never a guess.
"""
from __future__ import annotations

# The narrowest quote treated as a genuine market opinion. A 20c-wide book
# still prices *something*; beyond that the mid is closer to an artifact of
# the book's emptiness than to a probability anyone asserted.
MIN_HONEST_BID_CENTS = 1
MAX_HONEST_ASK_CENTS = 99
MAX_HONEST_SPREAD_CENTS = 20

# Shared contested threshold (probability units). Kept here so the learner,
# the backtest, and the miner all gate on the same number.
CONTESTED_DISAGREEMENT = 0.05

# Historical-fabrication signature: recorded prior in the coin-flip band while
# the model claims near-certainty (beyond 90/10 -- the exact pattern measured
# in the audit: 240 such crypto ladder decisions, model "right" 99.2% of the
# time against an average 0.42 phantom mid). Legitimate versions of this
# pattern exist but were unverifiable pre-gate (spreads were not persisted),
# so the quarantine trades a sliver of honest signal for removing a mountain
# of fabricated edge -- and it applies ONLY to rows recorded before
# QUOTE_GATE_EPOCH: after the emission gate deployed, a dead book produces no
# prior at all, so any post-epoch pair is real by construction.
SUSPECT_PRIOR_LOW = 0.35
SUSPECT_PRIOR_HIGH = 0.65
SUSPECT_MODEL_EXTREME_LOW = 0.10
SUSPECT_MODEL_EXTREME_HIGH = 0.90

# The moment the honest-quote emission gate ships to the live box. Rows
# created at/after this instant cannot carry a fabricated prior; the
# historical quarantine automatically retires for them.
QUOTE_GATE_EPOCH = "2026-07-17T00:00:00+00:00"


def _before_gate_epoch(created_at: str | None) -> bool:
    """True when a row predates the emission gate (or its stamp is unreadable
    -- unreadable is treated as pre-gate, the quarantine-eligible side)."""
    if created_at is None:
        return True
    from datetime import datetime, timezone

    try:
        stamp = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        epoch = datetime.fromisoformat(QUOTE_GATE_EPOCH)
        return stamp < epoch
    except (TypeError, ValueError):
        return True


def honest_implied_yes(
    yes_bid: int | float | None,
    yes_ask: int | float | None,
    *,
    max_spread_cents: int = MAX_HONEST_SPREAD_CENTS,
) -> float | None:
    """Implied P(yes) from a book, or None when the quote is not real.

    Real means: both sides present, bid >= 1c (someone commits capital to
    YES), ask <= 99c (someone commits capital to NO), not crossed, and the
    spread is at most ``max_spread_cents``.
    """
    if yes_bid is None or yes_ask is None:
        return None
    try:
        bid = float(yes_bid)
        ask = float(yes_ask)
    except (TypeError, ValueError):
        return None
    if bid < MIN_HONEST_BID_CENTS or ask > MAX_HONEST_ASK_CENTS:
        return None
    if ask < bid or (ask - bid) > max_spread_cents:
        return None
    return ((bid + ask) / 2.0) / 100.0


def suspect_crypto_contested_pair(
    probability_yes: float,
    market_prior: float | None,
    ticker: str | None,
    created_at: str | None = None,
) -> bool:
    """True when a pre-gate (model, recorded-prior) pair matches the
    fabrication signature on a CRYPTO market -- quarantine it from contested
    evidence.

    Rows created at/after :data:`QUOTE_GATE_EPOCH` are never suspect: the
    emission gate means a dead book no longer produces a prior, so any
    post-epoch pair is real by construction. Omitting ``created_at`` treats
    the row as pre-gate (the quarantine-eligible side).
    """
    if market_prior is None or ticker is None:
        return False
    if not _before_gate_epoch(created_at):
        return False
    prior = float(market_prior)
    if not (SUSPECT_PRIOR_LOW <= prior <= SUSPECT_PRIOR_HIGH):
        return False
    p = float(probability_yes)
    if SUSPECT_MODEL_EXTREME_LOW < p < SUSPECT_MODEL_EXTREME_HIGH:
        return False
    try:
        from autonomy.ontology import Vertical
        from autonomy.scanner import classify_vertical

        return classify_vertical(str(ticker)) is Vertical.CRYPTO
    except Exception:
        return False
