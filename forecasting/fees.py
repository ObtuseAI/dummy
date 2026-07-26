"""Fee math shared by the maintained real-market forecast loop."""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING


def kalshi_fee_cents(probability: Decimal, contracts: int = 1) -> int:
    """Return Kalshi's rounded-up taker fee estimate in cents."""

    p = max(Decimal("0"), min(Decimal("1"), Decimal(probability)))
    raw = (
        Decimal("0.07")
        * Decimal(contracts)
        * Decimal("100")
        * p
        * (Decimal("1") - p)
    )
    return int(raw.to_integral_value(rounding=ROUND_CEILING))


def signed_edge_after_fees(edge: Decimal, fee_probability: Decimal) -> Decimal:
    """Deduct fees without allowing costs to manufacture an opposite edge."""

    magnitude = max(
        Decimal("0"),
        abs(edge) - max(Decimal("0"), fee_probability),
    )
    return -magnitude if edge < 0 else magnitude


__all__ = ["kalshi_fee_cents", "signed_edge_after_fees"]
