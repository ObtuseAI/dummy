"""Point-in-time crypto technical-foundry challenger.

This is a clean-room implementation inspired by the broad indicator families
demonstrated in ObtuseAI/dopey (MIT): ATR-normalized momentum, Bollinger
position, stochastic location, on-balance-volume flow, volume anomaly, and
failed-breakout structure.  It does not copy Dopey's implementation or data.

The source is deliberately challenger-only.  It consumes the same cached
public Coinbase/Kraken candles as Dummy's existing crypto sources, abstains
without enough complete OHLCV history, records every primitive for later
point-in-time grading, and cannot enter the ensemble without its own exact
asset/contract/horizon promotion gate.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from autonomy import faststats as statistics  # Fraction-based statistics is a per-cycle hot spot
from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals.crypto_indicators import CryptoDataHub, _hours_to_close
from autonomy.signals.crypto_spot import (
    _normal_cdf,
    crypto_probability_uncertainty,
    parse_crypto_ticker,
)

MIN_BARS = 30
MIN_ACTIVE_COMPONENTS = 3
MIN_ABS_SCORE = 0.18
MAX_SHIFT_SIGMA = 0.35


def _finite(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _ema(values: list[float], span: int) -> float:
    alpha = 2.0 / (span + 1.0)
    result = values[0]
    for value in values[1:]:
        result = alpha * value + (1.0 - alpha) * result
    return result


def technical_foundry_features(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Return bounded causal primitives from oldest-first OHLCV rows."""
    clean: list[dict[str, float]] = []
    for row in rows:
        values = {
            key: _finite(row.get(key))
            for key in ("open", "high", "low", "close", "volume")
        }
        if (
            any(value is None for value in values.values())
            or values["high"] < values["low"]
            or values["close"] <= 0.0
            or values["volume"] < 0.0
        ):
            continue
        clean.append({key: float(value) for key, value in values.items()})
    if len(clean) < MIN_BARS:
        return {}

    closes = [row["close"] for row in clean]
    volumes = [row["volume"] for row in clean]
    true_ranges: list[float] = []
    for index, row in enumerate(clean):
        previous = closes[index - 1] if index else row["open"]
        true_ranges.append(
            max(
                row["high"] - row["low"],
                abs(row["high"] - previous),
                abs(row["low"] - previous),
            )
        )
    atr14 = statistics.fmean(true_ranges[-14:])
    momentum10 = closes[-1] - closes[-11]
    atr_momentum = momentum10 / atr14 if atr14 > 0.0 else 0.0

    band = closes[-20:]
    band_mean = statistics.fmean(band)
    band_std = statistics.pstdev(band)
    bollinger_pct_b = (
        (closes[-1] - (band_mean - 2.0 * band_std)) / (4.0 * band_std)
        if band_std > 0.0
        else 0.5
    )
    high14 = max(row["high"] for row in clean[-14:])
    low14 = min(row["low"] for row in clean[-14:])
    stochastic_k = (closes[-1] - low14) / (high14 - low14) if high14 > low14 else 0.5

    obv = 0.0
    obv_path = [0.0]
    for index in range(1, len(clean)):
        direction = (
            1.0
            if closes[index] > closes[index - 1]
            else (-1.0 if closes[index] < closes[index - 1] else 0.0)
        )
        obv += direction * volumes[index]
        obv_path.append(obv)
    volume_scale = statistics.fmean(volumes[-20:]) or 1.0
    obv_slope = (obv_path[-1] - obv_path[-20]) / (19.0 * volume_scale)
    prior_volumes = volumes[-21:-1]
    volume_mean = statistics.fmean(prior_volumes)
    volume_std = statistics.pstdev(prior_volumes)
    volume_z = (volumes[-1] - volume_mean) / volume_std if volume_std > 0.0 else 0.0

    current = clean[-1]
    close_location = (
        2.0 * (current["close"] - current["low"]) / (current["high"] - current["low"])
        - 1.0
        if current["high"] > current["low"]
        else 0.0
    )
    prior_range = clean[-21:-1]
    prior_high = max(row["high"] for row in prior_range)
    prior_low = min(row["low"] for row in prior_range)
    previous = clean[-2]
    breakout = 0.0
    fakeout = 0.0
    if current["close"] > prior_high:
        breakout = 1.0
    elif current["close"] < prior_low:
        breakout = -1.0
    if previous["high"] > prior_high and current["close"] < prior_high:
        fakeout = -1.0
    elif previous["low"] < prior_low and current["close"] > prior_low:
        fakeout = 1.0

    macd = _ema(closes[-60:], 12) - _ema(closes[-90:], 26)
    macd_atr = macd / atr14 if atr14 > 0.0 else 0.0
    components = {
        "atr_momentum": math.tanh(atr_momentum / 2.0),
        "macd_atr": math.tanh(macd_atr),
        "bollinger_position": max(-1.0, min(1.0, 2.0 * bollinger_pct_b - 1.0)),
        "stochastic_position": max(-1.0, min(1.0, 2.0 * stochastic_k - 1.0)),
        "obv_flow": math.tanh(obv_slope),
        "close_location": max(-1.0, min(1.0, close_location)),
        "breakout_or_fakeout": fakeout or breakout,
    }
    weights = {
        "atr_momentum": 0.20,
        "macd_atr": 0.15,
        "bollinger_position": 0.10,
        "stochastic_position": 0.10,
        "obv_flow": 0.15,
        "close_location": 0.10,
        "breakout_or_fakeout": 0.20,
    }
    raw_score = sum(weights[name] * value for name, value in components.items())
    # Volume confirms directional breakouts; it never creates direction alone.
    confirmation = min(1.25, max(0.75, 1.0 + 0.08 * max(-2.0, min(2.0, volume_z))))
    score = max(-1.0, min(1.0, raw_score * confirmation))
    active = sum(abs(value) >= 0.10 for value in components.values())
    return {
        "foundry_schema_version": 1,
        "bar_count": len(clean),
        "atr_14": atr14,
        "atr_normalized_momentum_10": atr_momentum,
        "macd_atr": macd_atr,
        "bollinger_pct_b_20": bollinger_pct_b,
        "stochastic_k_14": stochastic_k,
        "obv_slope_20": obv_slope,
        "volume_z_20": volume_z,
        "close_location_value": close_location,
        "breakout_state": breakout,
        "fakeout_state": fakeout,
        "components": components,
        "active_components": active,
        "score": score,
    }


class CryptoTechnicalFoundrySignal:
    """Sparse, bounded multi-indicator crypto challenger."""

    name = "crypto_technical_foundry"

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
        return (
            market.vertical is Vertical.CRYPTO
            and parse_crypto_ticker(market.ticker) is not None
        )

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_crypto_ticker(market.ticker)
        if parsed is None:
            return None
        asset = str(parsed["asset"])
        try:
            if asset not in self._cache:
                self._cache[asset] = self.fetch_state(asset)
            state = self._cache[asset]
            hours = float(self.hours_to_close(market))
        except Exception:
            return None
        if hours <= 2.0:
            timeframe, rows = "minute", state.get("minute_ohlcv") or []
        elif hours <= 72.0:
            timeframe, rows = "hourly", state.get("hourly_ohlcv") or []
        else:
            timeframe, rows = "daily", state.get("daily_ohlcv") or []
        features = technical_foundry_features(list(rows))
        if (
            not features
            or int(features["active_components"]) < MIN_ACTIVE_COMPONENTS
            or abs(float(features["score"])) < MIN_ABS_SCORE
        ):
            return None

        spot = _finite(state.get("spot"))
        indicators_vol = _finite(state.get("dvol"))
        if spot is None or spot <= 0.0:
            return None
        if indicators_vol is not None:
            annual_vol = indicators_vol / 100.0
        else:
            closes = [float(row["close"]) for row in rows if row.get("close")]
            returns = [
                math.log(closes[index] / closes[index - 1])
                for index in range(1, len(closes))
                if closes[index - 1] > 0.0 and closes[index] > 0.0
            ]
            if len(returns) < 20:
                return None
            periods = (
                60 * 24 * 365
                if timeframe == "minute"
                else (24 * 365 if timeframe == "hourly" else 365)
            )
            annual_vol = statistics.stdev(returns[-60:]) * math.sqrt(periods)
        horizon_sigma = annual_vol * math.sqrt(hours / (24.0 * 365.0))
        if not math.isfinite(horizon_sigma) or horizon_sigma <= 0.0:
            return None
        shift = MAX_SHIFT_SIGMA * float(features["score"]) * horizon_sigma

        def p_above(strike: float) -> float:
            if strike <= 0.0:
                return 1.0
            return _normal_cdf((math.log(spot / strike) + shift) / horizon_sigma)

        strike_type = str(market.raw.get("strike_type") or "").lower()
        floor = _finite(market.raw.get("floor_strike"))
        cap = _finite(market.raw.get("cap_strike"))
        if strike_type in {"greater", "greater_or_equal"} and floor is not None:
            probability = p_above(floor)
        elif strike_type == "less" and cap is not None:
            probability = 1.0 - p_above(cap)
        elif strike_type == "between" and floor is not None and cap is not None:
            probability = p_above(floor) - p_above(cap)
        else:
            strike = _finite(parsed.get("strike"))
            if strike is None:
                return None
            probability = p_above(strike)
        probability = min(0.995, max(0.005, probability))
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
                f"{asset} {timeframe} technical foundry score "
                f"{float(features['score']):+.3f} across "
                f"{int(features['active_components'])} active primitives"
            ),
            features={
                "challenger_only": True,
                # Evidence-driven now (autonomous thresholded promotion,
                # 2026-07-16): stays challenger_only until the AutoPromotionEngine
                # earns it a place from forward witnessed-fill evidence. Eligibility is
                # not promotion; the engine must still clear every ladder gate.
                "promotion_eligible": True,
                "point_in_time": True,
                "public_read_only": True,
                "clean_room_inspiration": "ObtuseAI/dopey indicator families (MIT)",
                "timeframe": timeframe,
                "hours_to_close": hours,
                "horizon_log_return_sigma": horizon_sigma,
                "shift_in_horizon_sigma": MAX_SHIFT_SIGMA * float(features["score"]),
                **features,
            },
        )


__all__ = ["CryptoTechnicalFoundrySignal", "technical_foundry_features"]
