"""Volatility triangulation, VRP regime, and settlement-proximity guard.

Council build-out WS-16 (floor raiser). Three under-exploited edges, all as
CHALLENGERS -- the champion (crypto_spot_vol) is never silently altered; the
blended-sigma view and the settlement guard reach execution only if WS-14
promotes them at a scope where they have earned it.

  * Vol triangle. The system already computes three volatility estimates --
    flat realized, EWMA realized, and Deribit implied (DVOL) -- but prices
    off one at a time. ``blended_sigma`` fuses them with horizon-appropriate
    weights (implied dominates daily, EWMA dominates 15m) and reports their
    disagreement, which widens the challenger's uncertainty.
  * VRP regime. implied minus realized ("volatility risk premium") is a
    known mean-reversion signal: a fear premium tends to unwind (mild upward
    drift on price), a complacency inversion the opposite. Bounded to 0.25
    horizon sigma.
  * Settlement-proximity guard. The strategy miner's first live pass flagged
    a near-close weakness: Kalshi settles crypto on CF Benchmarks while we
    price off an exchange median, so basis error dominates model edge near
    strike near close. The guard widens uncertainty there rather than
    pretending to know. Its own effectiveness is miner-graded.

Everything fails closed: missing vols / spot / horizon -> abstain, and a
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

# (flat, ewma, implied) blend weights per horizon. Implied vol is a daily-scale
# quantity, so it carries no weight on 15-minute contracts and the most on
# daily+. Tuner-managed later (WS-9).
_BLEND_WEIGHTS: dict[str, tuple[float, float, float]] = {
    "15m": (0.4, 0.6, 0.0),
    "hourly": (0.3, 0.4, 0.3),
    "daily+": (0.25, 0.25, 0.5),
    "unknown": (0.34, 0.33, 0.33),
}

# Settlement-proximity guard.
SETTLEMENT_PROXIMITY_HOURS = 0.75
SETTLEMENT_NEAR_STRIKE_SIGMAS = 1.0
SETTLEMENT_PROXIMITY_BUMP = 0.06

# VRP regime (points of annualized vol).
VRP_FEAR_THRESHOLD = 15.0      # implied this far above realized -> unwind drift up
VRP_COMPLACENCY_THRESHOLD = -5.0
VRP_MAX_SHIFT_SIGMA = 0.25


def ewma_annualized_vol(closes: list[float], decay: float = 0.94) -> float | None:
    """RiskMetrics EWMA annualized vol from hourly closes (None if too thin)."""
    usable = [float(value) for value in closes if value is not None and value > 0]
    returns = [
        math.log(usable[index] / usable[index - 1])
        for index in range(1, len(usable))
    ]
    if not returns:
        return None
    variance = returns[0] ** 2
    for value in returns[1:]:
        variance = decay * variance + (1.0 - decay) * value * value
    return math.sqrt(variance) * math.sqrt(24 * 365)


def blended_sigma(
    flat: float | None,
    ewma: float | None,
    implied: float | None,
    horizon: str,
) -> tuple[float | None, float | None]:
    """Weighted blend of the available annualized vols + their disagreement.

    Missing estimates renormalize over what remains; none available -> (None,
    None). ``disagreement`` is max/min - 1 over the available estimates (0.0
    when only one exists).
    """
    weights = _BLEND_WEIGHTS.get(horizon, _BLEND_WEIGHTS["unknown"])
    available = [
        (value, weight)
        for value, weight in zip((flat, ewma, implied), weights)
        if value is not None and float(value) > 0 and weight > 0
    ]
    if not available:
        return None, None
    total = sum(weight for _value, weight in available)
    sigma = sum(float(value) * weight for value, weight in available) / total
    values = [float(value) for value, _weight in available]
    low = min(values)
    disagreement = (max(values) / low - 1.0) if low > 0 else None
    return sigma, disagreement


def vrp_points(dvol: float | None, realized_7d_annual: float | None) -> float | None:
    """Volatility risk premium in points of annualized vol (implied - realized).

    DVOL is quoted in percent; realized is a fraction, so it is scaled to
    points to match.
    """
    if dvol is None or realized_7d_annual is None:
        return None
    try:
        return float(dvol) - float(realized_7d_annual) * 100.0
    except (TypeError, ValueError):
        return None


def settlement_proximity_uncertainty(
    hours_to_close: float | None,
    spot: float | None,
    strike: float | None,
    horizon_sigma: float | None,
) -> float:
    """Extra uncertainty near strike near close; 0.0 otherwise.

    Near the settlement the CF-Benchmarks-vs-exchange basis dominates model
    edge, and only when the contract could still go either way (spot within
    ~1 horizon sigma of the strike) does that basis actually matter.
    """
    if hours_to_close is None or float(hours_to_close) > SETTLEMENT_PROXIMITY_HOURS:
        return 0.0
    if not (spot and strike and float(strike) > 0 and horizon_sigma and float(horizon_sigma) > 0):
        return 0.0
    z = abs(math.log(float(spot) / float(strike))) / float(horizon_sigma)
    return SETTLEMENT_PROXIMITY_BUMP if z < SETTLEMENT_NEAR_STRIKE_SIGMAS else 0.0


def vrp_regime_score(vrp: float | None) -> float:
    """Bounded [-1, 1] mean-reversion score from the VRP; 0 in the dead zone."""
    if vrp is None:
        return 0.0
    if vrp > VRP_FEAR_THRESHOLD:
        return min(1.0, (vrp - VRP_FEAR_THRESHOLD) / 30.0)
    if vrp < VRP_COMPLACENCY_THRESHOLD:
        return max(-1.0, (vrp - VRP_COMPLACENCY_THRESHOLD) / 20.0)
    return 0.0


def _vols_from_state(state: dict[str, Any]) -> tuple[float | None, float | None, float | None]:
    hourly = [float(v) for v in state.get("hourly_closes") or []]
    flat = _annualized_vol(hourly[-169:], 24 * 365) if len(hourly) >= 25 else None
    ewma = ewma_annualized_vol(hourly) if len(hourly) >= 2 else None
    dvol = state.get("dvol")
    implied = float(dvol) / 100.0 if dvol is not None else None
    return flat, ewma, implied


def _relevant_strikes(market: MarketView, parsed: dict[str, Any]) -> list[float]:
    """The strike boundaries this contract actually settles against.

    Mirrors ``_price_strikes``' branch selection so the settlement-proximity
    guard measures distance to the RIGHT boundary/boundaries (a between market
    has two, and spot can sit near either).
    """
    strike_type = str(market.raw.get("strike_type", "")).lower()
    floor = market.raw.get("floor_strike")
    cap = market.raw.get("cap_strike")
    if strike_type in {"greater", "greater_or_equal"} and floor is not None:
        return [float(floor)]
    if strike_type == "less" and cap is not None:
        return [float(cap)]
    if strike_type == "between" and floor is not None and cap is not None:
        return [float(floor), float(cap)]
    return [float(parsed["strike"])]


def _price_strikes(market: MarketView, parsed: dict[str, Any], p_above) -> float:
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
    return min(0.995, max(0.005, probability))


class _CryptoStateSignal:
    """Shared plumbing for the WS-16 challengers over the hub state cache."""

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
        return market.vertical is Vertical.CRYPTO and parse_crypto_ticker(market.ticker) is not None

    def _state(self, asset: str) -> dict[str, Any] | None:
        try:
            if asset not in self._cache:
                self._cache[asset] = self.fetch_state(asset)
        except Exception:
            return None
        return self._cache[asset]


class CryptoBlendSigmaSignal(_CryptoStateSignal):
    """Champion lognormal priced on the triangulated (blended) sigma."""

    name = "crypto_blend_sigma"

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_crypto_ticker(market.ticker)
        if parsed is None:
            return None
        state = self._state(str(parsed["asset"]))
        if not state:
            return None
        try:
            spot = float(state["spot"])
        except (KeyError, TypeError, ValueError):
            return None
        if spot <= 0:
            return None
        hours = self.hours_to_close(market)
        if hours <= 0:
            return None
        horizon = horizon_bucket(market.ticker, hours)
        flat, ewma, implied = _vols_from_state(state)
        annual_vol, disagreement = blended_sigma(flat, ewma, implied, horizon)
        if annual_vol is None or annual_vol <= 0:
            return None
        horizon_sigma = annual_vol * math.sqrt(hours / (24.0 * 365.0))
        if horizon_sigma <= 0:
            return None

        def p_above(strike: float) -> float:
            if strike <= 0:
                return 1.0
            return _normal_cdf(math.log(spot / strike) / horizon_sigma)

        probability = _price_strikes(market, parsed, p_above)
        # Guard against every boundary this contract settles on (a between
        # market has two); spot near ANY of them triggers the basis widening.
        guard = max(
            settlement_proximity_uncertainty(hours, spot, strike, horizon_sigma)
            for strike in _relevant_strikes(market, parsed)
        )
        uncertainty = min(
            0.45,
            crypto_probability_uncertainty(probability, horizon_sigma)
            + 0.02 * min(3.0, (disagreement or 0.0) * 10.0)
            + guard,
        )
        # `flat` is the 7-day realized vol (hourly[-169:]), the realized leg of VRP.
        vrp = vrp_points(state.get("dvol"), flat)
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=probability,
            uncertainty=uncertainty,
            rationale=(
                f"{parsed['asset']} blended sigma={annual_vol:.0%} "
                f"(flat={flat}, ewma={ewma}, implied={implied}) "
                f"disagreement={disagreement} h={hours:.2f} {horizon}"
                + ("; settlement-proximity guard" if guard else "")
            ),
            features={
                "challenger_only": True,
                "vol_blend_model_version": 1,
                "blended_annual_vol": annual_vol,
                "vol_flat": flat,
                "vol_ewma": ewma,
                "vol_implied": implied,
                "vol_disagreement": disagreement,
                "vrp_points": vrp,
                "near_close_near_strike": bool(guard),
                "horizon_bucket": horizon,
                "hours_to_close": hours,
                "horizon_log_return_sigma": horizon_sigma,
            },
        )


class CryptoVrpRegimeSignal(_CryptoStateSignal):
    """Volatility-risk-premium mean-reversion drift; opines only off the dead zone."""

    name = "crypto_vrp_regime"

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_crypto_ticker(market.ticker)
        if parsed is None:
            return None
        state = self._state(str(parsed["asset"]))
        if not state:
            return None
        flat, ewma, implied = _vols_from_state(state)
        vrp = vrp_points(state.get("dvol"), flat)  # flat = 7-day realized
        score = vrp_regime_score(vrp)
        if score == 0.0:
            return None  # dead zone: no regime opinion
        try:
            spot = float(state["spot"])
        except (KeyError, TypeError, ValueError):
            return None
        annual_vol = implied if implied is not None else (ewma or flat)
        if spot <= 0 or annual_vol is None or annual_vol <= 0:
            return None
        hours = self.hours_to_close(market)
        if hours <= 0:
            return None
        horizon_sigma = float(annual_vol) * math.sqrt(hours / (24.0 * 365.0))
        if horizon_sigma <= 0:
            return None
        expected_log_return = VRP_MAX_SHIFT_SIGMA * score * horizon_sigma

        def p_above(strike: float) -> float:
            if strike <= 0:
                return 1.0
            return _normal_cdf((math.log(spot / strike) + expected_log_return) / horizon_sigma)

        probability = _price_strikes(market, parsed, p_above)
        uncertainty = min(
            0.45,
            crypto_probability_uncertainty(probability, horizon_sigma) + 0.06,
        )
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=probability,
            uncertainty=uncertainty,
            rationale=(
                f"{parsed['asset']} VRP={vrp:.1f}pts score={score:+.2f} "
                f"shift={VRP_MAX_SHIFT_SIGMA * score:+.2f}sigma; challenger-only"
            ),
            features={
                "challenger_only": True,
                "vrp_model_version": 1,
                "vrp_points": vrp,
                "vrp_score": score,
                "expected_log_return": expected_log_return,
                "shift_in_horizon_sigma": VRP_MAX_SHIFT_SIGMA * score,
                "horizon_log_return_sigma": horizon_sigma,
                "horizon_bucket": horizon_bucket(market.ticker, hours),
            },
        )
