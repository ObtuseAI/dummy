"""Deribit DVOL implied-volatility book for crypto triangulation (Phase 1).

The crypto analog of the sports sharp book: an INDEPENDENT estimator of
P(YES) for a Kalshi crypto contract, derived from Deribit's implied
volatility index rather than our own realized-vol model. Our champion prices
from backward-looking realized sigma; the options market prices from
forward-looking implied sigma. When both diverge from the Kalshi price in
the same direction, the mispricing engine grades the edge "model+book" --
the same high-confidence tier MLB earns from the de-vigged sportsbook.

Strike handling mirrors ``CryptoSpotVolSignal.generate`` exactly (floor /
cap / between / parsed-threshold), so model and book always price the same
payoff on the same contract terms.

Fail-closed: no parseable ticker, no hub state, stale/missing DVOL (the hub
already nulls DVOL older than 6h), or a degenerate horizon all return None,
and the assessment degrades to "model_only" -- byte-identical to a run
without this book.
"""
from __future__ import annotations

import math
from typing import Any, Callable

from autonomy.ontology import MarketView
from autonomy.signals.crypto_indicators import _hours_to_close
from autonomy.signals.crypto_spot import _normal_cdf, parse_crypto_ticker


class CryptoImpliedBook:
    """Risk-neutral P(above strike) from the Deribit DVOL index."""

    def __init__(
        self,
        fetch_state: Callable[[str], dict[str, Any]],
        hours_to_close: Callable[[MarketView], float] | None = None,
    ) -> None:
        # ``fetch_state`` is the shared CryptoDataHub.state bound method --
        # one public multi-venue fetch per asset per cycle, never a second
        # network path of our own.
        self.fetch_state = fetch_state
        self.hours_to_close = hours_to_close or _hours_to_close

    def book_probability(self, market: MarketView) -> float | None:
        parsed = parse_crypto_ticker(market.ticker)
        if parsed is None:
            return None
        try:
            state = self.fetch_state(parsed["asset"])
        except Exception:
            return None
        dvol = state.get("dvol")
        spot = state.get("spot")
        if dvol is None or spot is None or float(spot) <= 0 or float(dvol) <= 0:
            return None
        try:
            hours = self.hours_to_close(market)
        except Exception:
            return None
        # DVOL is quoted in annualized percent (e.g. 52.3).
        implied_sigma = (float(dvol) / 100.0) * math.sqrt(hours / (24 * 365))
        if implied_sigma <= 0:
            return None
        spot_value = float(spot)

        def p_above(strike: float) -> float:
            if strike <= 0:
                return 1.0
            return _normal_cdf(math.log(spot_value / strike) / implied_sigma)

        strike_type = str(market.raw.get("strike_type", "")).lower()
        floor = market.raw.get("floor_strike")
        cap = market.raw.get("cap_strike")
        if strike_type in {"greater", "greater_or_equal"} and floor is not None:
            probability = p_above(float(floor))
        elif strike_type == "less" and cap is not None:
            probability = 1.0 - p_above(float(cap))
        elif strike_type == "between" and floor is not None and cap is not None:
            probability = p_above(float(floor)) - p_above(float(cap))
        else:
            probability = p_above(parsed["strike"])
        return min(0.995, max(0.005, probability))
