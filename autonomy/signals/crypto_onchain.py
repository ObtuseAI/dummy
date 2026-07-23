"""Crypto on-chain liquidity challenger: stablecoin-supply risk-appetite drift.

The aggregate circulating supply of USD-pegged stablecoins is the market's dry
powder. When it expands, capital is flowing onto exchanges/chains and is
available to bid crypto (risk-on); when it contracts, liquidity is leaving
(risk-off). This signal reads DefiLlama's keyless stablecoin supply history,
turns its recent momentum into a bounded liquidity score, and applies it as a
modest horizon-scaled directional drift on the crypto lognormal -- the same
shape as the macro-regime challenger, sourced on-chain instead of from
equities.

Discipline mirrors the other crypto challengers:
  * challenger_only -- point-in-time evidence, never auto-fused;
  * fail-closed -- no supply feed, no crypto state, or a degenerate horizon =>
    abstain and the forecast is byte-identical to a run without it;
  * drift scales with horizon_sigma, so it self-limits to ~zero on 15m/hourly
    contracts and only opines meaningfully on multi-hour/daily horizons.
"""
from __future__ import annotations

import math
from typing import Any, Callable

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals.crypto_indicators import (
    CryptoDataHub,
    _hours_to_close,
    _indicator_features,
)
from autonomy.signals.crypto_spot import (
    _normal_cdf,
    crypto_probability_uncertainty,
    parse_crypto_ticker,
)

# Stablecoin supply is a slow macro-liquidity driver, so the drift is small and
# the horizon scaling keeps it near zero on ultra-short contracts.
STABLE_DAILY_DRIFT = 0.010    # max expected daily log-return at score = +/-1
STABLE_MAX_SHIFT_SIGMA = 0.30
# Characteristic multi-week supply moves used to bound each momentum term.
MOMENTUM_TERMS = (
    ("supply_7d", 7, 0.010),    # a +1% weekly expansion is a strong risk-on read
    ("supply_30d", 30, 0.030),  # a +3% monthly expansion likewise
)
_TOTAL_WEIGHT = float(len(MOMENTUM_TERMS))


def _series_total(entry: dict[str, Any]) -> float | None:
    """USD-pegged circulating total from one DefiLlama chart entry."""
    block = entry.get("totalCirculatingUSD")
    if isinstance(block, dict):
        pegged = block.get("peggedUSD")
        try:
            return float(pegged)
        except (TypeError, ValueError):
            return None
    try:
        return float(block)
    except (TypeError, ValueError):
        return None


def stablecoin_supply_series(raw: list[dict[str, Any]]) -> list[float]:
    """Chronological USD-pegged circulating totals from the DefiLlama chart."""
    out: list[float] = []
    for entry in raw or []:
        total = _series_total(entry)
        if total is not None and total > 0:
            out.append(total)
    return out


def onchain_liquidity_score(
    series: list[float],
) -> tuple[float, float, dict[str, float]]:
    """Bounded [-1, 1] liquidity score from stablecoin supply momentum.

    Positive = expanding supply (risk-on). Returns (score, coverage,
    components); a momentum term without enough history contributes zero and
    lowers coverage rather than rescaling.
    """
    components: dict[str, float] = {}
    score = 0.0
    available = 0.0
    for key, lookback, scale in MOMENTUM_TERMS:
        if len(series) <= lookback or series[-1 - lookback] <= 0:
            continue
        change = series[-1] / series[-1 - lookback] - 1.0
        contribution = math.tanh(change / scale)
        components[key] = round(contribution, 5)
        score += contribution
        available += 1.0
    if available <= 0:
        return 0.0, 0.0, components
    score /= available  # average the available terms into [-1, 1]
    coverage = available / _TOTAL_WEIGHT
    return max(-1.0, min(1.0, score)), coverage, components


def default_fetch_stablecoin_supply(*, timeout_seconds: float = 15.0) -> list[float]:
    """Keyless DefiLlama total stablecoin circulating-supply history."""
    import httpx

    try:
        response = httpx.get(
            "https://stablecoins.llama.fi/stablecoincharts/all",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=max(0.1, float(timeout_seconds)),
        )
        response.raise_for_status()
        return stablecoin_supply_series(response.json())
    except Exception:  # noqa: BLE001 - a dead feed just abstains
        return []


class CryptoOnchainLiquiditySignal:
    """Stablecoin-supply liquidity drift on crypto markets; never auto-fused."""

    name = "crypto_onchain_liquidity"

    def __init__(
        self,
        fetch_state: Callable[[str], dict[str, Any]] | None = None,
        fetch_supply: Callable[[], list[float]] | None = None,
        hours_to_close: Callable[[MarketView], float] | None = None,
    ) -> None:
        self._hub = CryptoDataHub() if fetch_state is None else None
        self.fetch_state = fetch_state or self._hub.state
        self.fetch_supply = fetch_supply or default_fetch_stablecoin_supply
        self.hours_to_close = hours_to_close or _hours_to_close
        self._state_cache: dict[str, dict[str, Any]] = {}
        self._supply_cache: list[float] | None = None

    def on_cycle_start(self) -> None:
        self._state_cache.clear()
        self._supply_cache = None
        owner = getattr(self.fetch_state, "__self__", None)
        clear = getattr(owner, "clear", None)
        if callable(clear):
            clear()

    def applicable(self, market: MarketView) -> bool:
        return (
            market.vertical is Vertical.CRYPTO
            and parse_crypto_ticker(market.ticker) is not None
        )

    def _supply(self) -> list[float]:
        if self._supply_cache is None:
            try:
                self._supply_cache = list(self.fetch_supply() or [])
            except Exception:  # noqa: BLE001
                self._supply_cache = []
        return self._supply_cache

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_crypto_ticker(market.ticker)
        if parsed is None:
            return None
        score, coverage, components = onchain_liquidity_score(self._supply())
        if coverage <= 0.0:
            return None

        asset = str(parsed["asset"])
        if asset not in self._state_cache:
            try:
                self._state_cache[asset] = self.fetch_state(asset)
            except Exception:  # noqa: BLE001
                return None
        state = self._state_cache[asset]
        try:
            spot = float(state["spot"])
        except (KeyError, TypeError, ValueError):
            return None
        if spot <= 0:
            return None
        try:
            if state.get("dvol") is not None:
                annual_vol: float | None = float(state["dvol"]) / 100.0
            else:
                indicators = _indicator_features(state)
                annual_vol = (
                    indicators.get("realized_vol_60m_annualized")
                    or indicators.get("realized_vol_7d_annualized")
                )
            annual_vol = None if annual_vol is None else float(annual_vol)
        except (TypeError, ValueError):
            return None
        if annual_vol is None or annual_vol <= 0:
            return None
        hours = self.hours_to_close(market)
        if hours <= 0:
            return None
        horizon_sigma = annual_vol * math.sqrt(hours / (24.0 * 365.0))
        if horizon_sigma <= 0:
            return None
        raw_drift = STABLE_DAILY_DRIFT * score * (hours / 24.0)
        sigma_cap = STABLE_MAX_SHIFT_SIGMA * horizon_sigma
        expected_log_return = max(-sigma_cap, min(sigma_cap, raw_drift))

        def p_above(strike: float) -> float:
            if strike <= 0:
                return 1.0
            z = (math.log(spot / strike) + expected_log_return) / horizon_sigma
            return _normal_cdf(z)

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
            max(0.20, crypto_probability_uncertainty(probability, horizon_sigma) + 0.06),
        )
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=probability,
            uncertainty=uncertainty,
            rationale=(
                f"on-chain liquidity {asset.upper()}: stablecoin supply score "
                f"{score:+.3f} (coverage {coverage:.2f}) -> "
                f"drift {expected_log_return:+.4f} over {hours:.1f}h"
            ),
            features={
                "onchain_liquidity_score": round(score, 5),
                "coverage": round(coverage, 3),
                "expected_log_return": round(expected_log_return, 6),
                "horizon_hours": round(hours, 3),
                "supply_momentum": components,
                "challenger_only": True,
                "promotion_eligible": True,
                "public_read_only": True,
                "asset": asset,
            },
        )
