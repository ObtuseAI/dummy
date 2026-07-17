"""Adaptive crypto challengers: patience-with-confirmation + KAMA momentum.

Wave-8, operator directive 2026-07-17: on the 15-minute and hourly BTC/ETH/SOL
surfaces, experiment with PATIENCE — waiting for confirmation closer to
expiration instead of opining the moment a window opens — and with adaptive
indicators whose aggressiveness scales with measured market state.

The evidence motivating both: the Wave-7 negative-control battery showed the
always-on crypto sources carry ~zero ROW-LEVEL discrimination early in a
window (their edge is rate-based calibration structure), and the strategy
miner independently found a late-window information lead on hourly buckets.
Later in the window there is simply more information; these challengers only
speak when that information exists.

Both are challenger_only and fail-closed everywhere; they reach execution only
via the WS-14 promotion ladder, graded per (asset x family x horizon) scope
like every other source. Preregistrations with falsification conditions ship
in ``scripts/preregister_wave8.py``.
"""
from __future__ import annotations

import math
from typing import Any

from autonomy.ontology import MarketView, Signal
from autonomy.signals.crypto_indicators import _normal_cdf
from autonomy.signals.crypto_spot import parse_crypto_ticker
from autonomy.signals.crypto_vol import CryptoBlendSigmaSignal, _CryptoStateSignal

# --- Patience gate -----------------------------------------------------------
# Speak only inside the final fraction of the window: the last ~40% of a 15m
# window (~6 minutes) and of an hourly bucket (~24 minutes). Earlier, the
# always-on sources already cover the surface; the patience thesis is that
# THIS slice is where row-level information lives.
PATIENCE_WINDOW_FRACTION = 0.40
# Confirmation drift: spot must have moved at least this fraction of its
# window-open distance-to-reference toward the predicted side (or already be
# through the reference).
CONFIRM_MOVE_FRACTION = 0.5

# --- KAMA (Kaufman adaptive moving average) ----------------------------------
KAMA_ER_WINDOW = 20          # efficiency-ratio lookback, minutes
KAMA_FAST = 2.0 / (2 + 1)    # classic fast/slow smoothing constants
KAMA_SLOW = 2.0 / (30 + 1)
KAMA_MIN_CLOSES = 45         # fail-closed below this many 1m closes
# Momentum drift is bounded to this many horizon-sigmas no matter how strong
# the trend reads — an adaptive signal must not out-shout its own noise.
KAMA_MAX_DRIFT_SIGMAS = 0.75


def _window_hours(parsed: dict[str, Any], hours_to_close: float) -> float | None:
    """The contract window this market belongs to, or None if out of scope.

    15m-direction contracts are always a 0.25h window. Ladder contracts are in
    scope only when they are inside their final hour (the hourly bucket);
    daily+ ladders are somebody else's job.
    """
    family = str(parsed.get("contract_family") or "")
    if family == "15m_direction":
        return 0.25
    if family == "ladder" and hours_to_close <= 1.0:
        return 1.0
    return None


def _reference_price(parsed: dict[str, Any], market: MarketView) -> float | None:
    """The settlement reference the YES side is measured against."""
    raw = market.raw or {}
    if str(parsed.get("contract_family")) == "15m_direction":
        for key in ("floor_strike", "functional_strike", "cap_strike"):
            value = raw.get(key)
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        return None
    strike_type = str(raw.get("strike_type", "")).lower()
    if strike_type in {"greater", "greater_or_equal"} and raw.get("floor_strike") is not None:
        return float(raw["floor_strike"])
    if strike_type == "less" and raw.get("cap_strike") is not None:
        return float(raw["cap_strike"])
    if strike_type in {"", "greater", "greater_or_equal"} and parsed.get("strike"):
        return float(parsed["strike"])
    return None   # "between" and exotic shapes are out of scope (fail-closed)


def _window_open_price(state: dict[str, Any], elapsed_minutes: int) -> float | None:
    closes = state.get("minute_closes") or []
    if not closes or elapsed_minutes < 1 or elapsed_minutes >= len(closes):
        return None
    try:
        return float(closes[-(elapsed_minutes + 1)])
    except (TypeError, ValueError, IndexError):
        return None


class CryptoPatienceSignal(_CryptoStateSignal):
    """Re-emits the champion's late-window forecast only after confirmation.

    Gate 1 (patience): inside the final PATIENCE_WINDOW_FRACTION of the 15m
    window / hourly bucket only.
    Gate 2 (confirmation): spot is already through the settlement reference on
    the predicted side, or has covered >= CONFIRM_MOVE_FRACTION of its
    window-open distance toward it. No confirmation -> silence.
    """

    name = "crypto_patience_confirm"

    def __init__(self, fetch_state=None, hours_to_close=None, parent=None) -> None:
        super().__init__(fetch_state=fetch_state, hours_to_close=hours_to_close)
        self.parent = parent or CryptoBlendSigmaSignal(
            fetch_state=fetch_state, hours_to_close=hours_to_close)

    def on_cycle_start(self) -> None:
        super().on_cycle_start()
        parent_reset = getattr(self.parent, "on_cycle_start", None)
        if callable(parent_reset):
            parent_reset()

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_crypto_ticker(market.ticker)
        if parsed is None:
            return None
        hours = self.hours_to_close(market)
        window = _window_hours(parsed, hours)
        if window is None or hours > PATIENCE_WINDOW_FRACTION * window:
            return None
        parent_signal = self.parent.generate(market)
        if parent_signal is None:
            return None
        state = self._state(str(parsed["asset"]))
        if not state or state.get("spot") is None:
            return None
        spot = float(state["spot"])
        reference = _reference_price(parsed, market)
        if reference is None or reference <= 0 or spot <= 0:
            return None

        predicted_yes = parent_signal.probability_yes >= 0.5
        # For every in-scope shape, YES means settling at/above the reference
        # (the "less" ladder shape inverts: YES means below).
        yes_is_above = str((market.raw or {}).get("strike_type", "")).lower() != "less"
        wants_above = predicted_yes == yes_is_above

        through = spot >= reference if wants_above else spot <= reference
        confirmed_by = None
        if through:
            confirmed_by = "spot_through_reference"
        else:
            elapsed_minutes = int(round((window - hours) * 60.0))
            open_price = _window_open_price(state, elapsed_minutes)
            if open_price is not None and open_price > 0:
                open_gap = abs(reference - open_price)
                covered = (spot - open_price) if wants_above else (open_price - spot)
                if open_gap > 0 and covered / open_gap >= CONFIRM_MOVE_FRACTION:
                    confirmed_by = "drift_toward_reference"
        if confirmed_by is None:
            return None

        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=parent_signal.probability_yes,
            # Confirmation is genuine extra information; tighten modestly,
            # never below the champion floor.
            uncertainty=max(0.08, parent_signal.uncertainty * 0.9),
            rationale=(
                f"patience: {hours * 60:.1f}m left of {window * 60:.0f}m window, "
                f"{confirmed_by}; parent {parent_signal.probability_yes:.3f}"
            ),
            features={
                **(parent_signal.features or {}),
                "challenger_only": True,
                "patience_variant": "late_window_confirmed_v1",
                "parent_source": parent_signal.source,
                "confirmed_by": confirmed_by,
                "window_hours": window,
                "hours_to_close": hours,
            },
        )


def kama(closes: list[float], er_window: int = KAMA_ER_WINDOW) -> float | None:
    """Kaufman adaptive moving average over 1m closes (last value)."""
    if len(closes) < er_window + 2:
        return None
    value = closes[0]
    for i in range(1, len(closes)):
        start = max(0, i - er_window)
        change = abs(closes[i] - closes[start])
        volatility = sum(abs(closes[j] - closes[j - 1]) for j in range(start + 1, i + 1))
        er = (change / volatility) if volatility > 0 else 0.0
        sc = (er * (KAMA_FAST - KAMA_SLOW) + KAMA_SLOW) ** 2
        value = value + sc * (closes[i] - value)
    return value


def efficiency_ratio(closes: list[float], er_window: int = KAMA_ER_WINDOW) -> float:
    if len(closes) < er_window + 1:
        return 0.0
    tail = closes[-(er_window + 1):]
    change = abs(tail[-1] - tail[0])
    volatility = sum(abs(tail[i] - tail[i - 1]) for i in range(1, len(tail)))
    return (change / volatility) if volatility > 0 else 0.0


class CryptoKamaMomentumSignal(_CryptoStateSignal):
    """Adaptive momentum: drift weighted by Kaufman efficiency ratio.

    In a trending regime (ER -> 1) the spot-vs-KAMA displacement is treated as
    genuine drift over the remaining window; in chop (ER -> 0) the drift
    weight collapses and the forecast converges to the no-drift lognormal —
    the adaptivity IS the indicator. Drift is hard-bounded to
    KAMA_MAX_DRIFT_SIGMAS horizon-sigmas.
    """

    name = "crypto_kama_momentum"

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_crypto_ticker(market.ticker)
        if parsed is None:
            return None
        hours = self.hours_to_close(market)
        window = _window_hours(parsed, hours)
        if window is None:
            return None
        state = self._state(str(parsed["asset"]))
        if not state or state.get("spot") is None:
            return None
        closes = [float(v) for v in (state.get("minute_closes") or [])]
        if len(closes) < KAMA_MIN_CLOSES:
            return None
        spot = float(state["spot"])
        reference = _reference_price(parsed, market)
        if reference is None or reference <= 0 or spot <= 0:
            return None
        annual_vol = state.get("realized_vol_60m_annualized") or state.get(
            "realized_vol_7d_annualized")
        if not annual_vol or float(annual_vol) <= 0:
            return None
        sigma_h = float(annual_vol) * math.sqrt(hours / (24.0 * 365.0))
        if sigma_h <= 0:
            return None

        anchor = kama(closes)
        if anchor is None or anchor <= 0:
            return None
        er = efficiency_ratio(closes)
        raw_drift = math.log(spot / anchor)          # displacement in log space
        drift = er * raw_drift                        # adaptive weighting
        cap = KAMA_MAX_DRIFT_SIGMAS * sigma_h
        drift = max(-cap, min(cap, drift))

        z = (math.log(spot / reference) + drift) / sigma_h
        p_above = _normal_cdf(z)
        yes_is_above = str((market.raw or {}).get("strike_type", "")).lower() != "less"
        probability = p_above if yes_is_above else 1.0 - p_above
        probability = min(0.995, max(0.005, probability))
        # Chop earns wide uncertainty; a clean trend earns (bounded) confidence.
        uncertainty = min(0.35, max(0.10, 0.28 - 0.15 * er))
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=probability,
            uncertainty=uncertainty,
            rationale=(
                f"KAMA momentum: ER={er:.2f} drift={drift / sigma_h:+.2f}σ_h "
                f"spot={spot:.2f} kama={anchor:.2f} ref={reference:.2f}"
            ),
            features={
                "challenger_only": True,
                "efficiency_ratio": round(er, 4),
                "kama": round(anchor, 6),
                "drift_sigmas": round(drift / sigma_h, 4),
                "hours_to_close": hours,
                "window_hours": window,
            },
        )
