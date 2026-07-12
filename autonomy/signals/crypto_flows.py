"""BTC-to-alt lead-lag challenger (spot only, no derivatives).

Council build-out WS-17. Bitcoin leads ETH and SOL by minutes on the spot
tape: a sharp BTC move that an alt has not yet followed is short-horizon
predictive of the alt catching up. This prices that residual catch-up as a
bounded drift on the alt's lognormal.

Spot data only -- Coinbase minute closes the hub already caches. No
perpetual funding, basis, or any derivative input (operator directive
2026-07-12: the system does not touch perpetuals).

Challenger-only, fail-closed: thin BTC/alt data, a degenerate horizon, or an
alt that has already caught up (residual floored at zero) all abstain, and a
disabled challenger leaves the ensemble byte-identical.
"""
from __future__ import annotations

import math
from typing import Any, Callable

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals.crypto_indicators import (
    CryptoDataHub,
    _annualized_vol,
    _hours_to_close,
)
from autonomy.signals.crypto_spot import (
    _normal_cdf,
    crypto_probability_uncertainty,
    parse_crypto_ticker,
)
from autonomy.taxonomy import horizon_bucket

# BTC-follow beta per alt (how much of a BTC move the alt tends to track).
_LEADLAG_BETA = {"ETH": 0.70, "SOL": 0.60}
LEADLAG_WINDOW_MINUTES = 15
LEADLAG_MAX_SHIFT_SIGMA = 0.35
# Residual (in sigma) below this is noise -> abstain.
LEADLAG_MIN_RESIDUAL_SIGMA = 0.15
# Lead-lag is a minutes-scale effect; only opine on short-horizon contracts.
_LEADLAG_HORIZONS = {"15m", "hourly"}


def move_in_sigma(
    closes: list[float], window_minutes: int, annual_vol: float | None,
) -> float | None:
    """Recent log-return over ``window_minutes`` expressed in sigma units.

    Uses the asset's own annualized vol to normalize, so BTC and an alt are
    comparable. None when the series is too short or vol is degenerate.
    """
    if annual_vol is None or float(annual_vol) <= 0:
        return None
    usable = [float(value) for value in closes if value is not None and value > 0]
    if len(usable) < window_minutes + 1:
        return None
    log_return = math.log(usable[-1] / usable[-1 - window_minutes])
    window_sigma = float(annual_vol) * math.sqrt(window_minutes / (60 * 24 * 365))
    if window_sigma <= 0:
        return None
    return log_return / window_sigma


def leadlag_residual(btc_sigma: float, alt_sigma: float, beta: float) -> float:
    """Catch-up the alt still owes BTC's move, in the alt's sigma units.

    Floored at zero once the alt has moved as far as (or farther than) beta *
    BTC in the same direction -- no double counting and never a reversal.
    """
    target = btc_sigma * beta
    remaining = target - alt_sigma
    if (target > 0 and remaining > 0) or (target < 0 and remaining < 0):
        return remaining
    return 0.0


class CryptoBtcLeadlagSignal:
    """ETH/SOL short-horizon drift from an un-followed BTC move (spot only)."""

    name = "crypto_btc_leadlag"

    def __init__(
        self,
        fetch_state: Callable[[str], dict[str, Any]] | None = None,
        hours_to_close: Callable[[MarketView], float] | None = None,
    ) -> None:
        self._hub = CryptoDataHub() if fetch_state is None else None
        self.fetch_state = fetch_state or self._hub.state
        self.hours_to_close = hours_to_close or _hours_to_close
        self._cache: dict[str, dict[str, Any]] = {}

    def on_cycle_start(self) -> None:
        self._cache.clear()
        owner = getattr(self.fetch_state, "__self__", None)
        clear = getattr(owner, "clear", None)
        if callable(clear):
            clear()

    def applicable(self, market: MarketView) -> bool:
        parsed = parse_crypto_ticker(market.ticker)
        return (
            market.vertical is Vertical.CRYPTO
            and parsed is not None
            and str(parsed["asset"]) in _LEADLAG_BETA
        )

    def _state(self, asset: str) -> dict[str, Any] | None:
        try:
            if asset not in self._cache:
                self._cache[asset] = self.fetch_state(asset)
        except Exception:
            return None
        return self._cache[asset]

    @staticmethod
    def _asset_vol(state: dict[str, Any]) -> float | None:
        hourly = [float(v) for v in state.get("hourly_closes") or []]
        return _annualized_vol(hourly[-169:], 24 * 365) if len(hourly) >= 25 else None

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_crypto_ticker(market.ticker)
        if parsed is None:
            return None
        asset = str(parsed["asset"])
        beta = _LEADLAG_BETA.get(asset)
        if beta is None:
            return None
        hours = self.hours_to_close(market)
        if hours <= 0 or horizon_bucket(market.ticker, hours) not in _LEADLAG_HORIZONS:
            return None
        alt_state = self._state(asset)
        btc_state = self._state("BTC")
        if not alt_state or not btc_state:
            return None
        try:
            spot = float(alt_state["spot"])
        except (KeyError, TypeError, ValueError):
            return None
        if spot <= 0:
            return None
        alt_vol = self._asset_vol(alt_state)
        btc_vol = self._asset_vol(btc_state)
        alt_move = move_in_sigma(alt_state.get("minute_closes") or [],
                                 LEADLAG_WINDOW_MINUTES, alt_vol)
        btc_move = move_in_sigma(btc_state.get("minute_closes") or [],
                                 LEADLAG_WINDOW_MINUTES, btc_vol)
        if alt_move is None or btc_move is None or alt_vol is None or alt_vol <= 0:
            return None
        residual = leadlag_residual(btc_move, alt_move, beta)
        if abs(residual) < LEADLAG_MIN_RESIDUAL_SIGMA:
            return None  # alt already caught up / no meaningful lead

        horizon_sigma = alt_vol * math.sqrt(hours / (24.0 * 365.0))
        if horizon_sigma <= 0:
            return None
        score = max(-1.0, min(1.0, residual))
        expected_log_return = LEADLAG_MAX_SHIFT_SIGMA * score * horizon_sigma

        def p_above(strike: float) -> float:
            if strike <= 0:
                return 1.0
            return _normal_cdf((math.log(spot / strike) + expected_log_return) / horizon_sigma)

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
            probability = p_above(float(parsed["strike"]))
        probability = min(0.995, max(0.005, probability))
        uncertainty = min(
            0.45,
            crypto_probability_uncertainty(probability, horizon_sigma) + 0.05,
        )
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=probability,
            uncertainty=uncertainty,
            rationale=(
                f"{asset} BTC lead-lag: btc={btc_move:+.2f}sig alt={alt_move:+.2f}sig "
                f"beta={beta} residual={residual:+.2f}sig "
                f"shift={LEADLAG_MAX_SHIFT_SIGMA * score:+.2f}sigma; challenger-only"
            ),
            features={
                "challenger_only": True,
                "leadlag_model_version": 1,
                "btc_move_sigma": btc_move,
                "alt_move_sigma": alt_move,
                "leadlag_beta": beta,
                "leadlag_residual_sigma": residual,
                "expected_log_return": expected_log_return,
                "shift_in_horizon_sigma": LEADLAG_MAX_SHIFT_SIGMA * score,
                "horizon_log_return_sigma": horizon_sigma,
                "horizon_bucket": horizon_bucket(market.ticker, hours),
            },
        )
