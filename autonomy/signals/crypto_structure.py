"""Multi-timeframe structure challenger: swing setups at S/R inside channels.

Operator directive 2026-07-12: play the swings -- price a directional edge
only when market structure (multi-timeframe support/resistance + trend
channels, autonomy/crypto_structure.py) and the confirming technicals agree.

Discipline mirrors the other crypto challengers exactly:
  * challenger_only=True -- logged and contested-Brier graded, never fused
    into the execution ensemble until an explicit promotion review.
  * abstains by default -- no actionable setup (|score| below threshold),
    thin series, or missing state means None, byte-identical to a run
    without this signal. A swing trader who is always in a trade is noise;
    this one opines only at structure.
  * bounded -- the setup can move the distribution center by at most 0.45
    horizon standard deviations (the shared technical-shift cap), so
    structure conviction can never manufacture near-certainty.

Every emitted signal logs the full structure state (levels, channels,
alignment, reasons) as features: point-in-time raw material the strategy
miner (Phase 1c) uses to reverse-engineer which setups actually carried
edge.
"""
from __future__ import annotations

import math
from typing import Any, Callable

from autonomy.crypto_structure import (
    SwingSetup,
    mtf_alignment,
    structure_state,
    swing_setup,
)
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

# Setups weaker than this are not setups; the signal abstains.
MIN_SETUP_SCORE = 0.15
# Shared cap: structure may shift the center by at most this many horizon sigmas.
MAX_SHIFT_SIGMA = 0.45


class CryptoStructureSignal:
    """Swing-at-structure challenger over the shared CryptoDataHub state."""

    name = "crypto_structure_swing"

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

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_crypto_ticker(market.ticker)
        if parsed is None:
            return None
        asset = str(parsed["asset"])
        try:
            if asset not in self._cache:
                self._cache[asset] = self.fetch_state(asset)
        except Exception:
            return None
        state = self._cache[asset]
        structures = structure_state(state)
        if not structures:
            return None
        indicators = _indicator_features(state)
        setup: SwingSetup = swing_setup(structures, indicators)
        if abs(setup.score) < MIN_SETUP_SCORE:
            return None  # no swing, no opinion -- structure is a scalpel

        spot = float(state.get("spot") or 0.0)
        hours = self.hours_to_close(market)
        annual_vol = (
            float(state["dvol"]) / 100.0 if state.get("dvol") is not None
            else indicators.get("realized_vol_60m_annualized")
            or indicators.get("realized_vol_7d_annualized")
        )
        if spot <= 0 or annual_vol is None or float(annual_vol) <= 0:
            return None
        horizon_sigma = float(annual_vol) * math.sqrt(hours / (24.0 * 365.0))
        if horizon_sigma <= 0:
            return None
        expected_log_return = MAX_SHIFT_SIGMA * setup.score * horizon_sigma

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

        alignment = mtf_alignment(structures)
        # Fighting the higher-timeframe trend is the classic swing failure
        # mode: widen uncertainty when the setup direction conflicts with it.
        conflict_penalty = 0.05 if alignment * setup.score < -0.05 else 0.0
        uncertainty = min(
            0.40,
            crypto_probability_uncertainty(probability, horizon_sigma)
            + 0.04  # challenger humility, matching the technical composite
            + conflict_penalty,
        )

        def _level_row(level):
            if level is None:
                return None
            return {
                "price": level.price, "kind": level.kind,
                "touches": level.touches, "strength": round(level.strength, 4),
                "age_bars": level.last_touch_age_bars,
            }

        def _channel_row(channel):
            if channel is None:
                return None
            return {
                "slope_bps_per_bar": round(channel.slope_bps_per_bar, 3),
                "r_squared": round(channel.r_squared, 4),
                "position": round(channel.position, 4),
                "band_width_bps": round(channel.band_width_bps, 1),
            }

        structure_features = {
            timeframe: {
                "support": _level_row(snapshot.support),
                "resistance": _level_row(snapshot.resistance),
                "channel": _channel_row(snapshot.channel),
            }
            for timeframe, snapshot in structures.items()
        }
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=probability,
            uncertainty=uncertainty,
            rationale=(
                f"{asset} swing setup {setup.score:+.2f} at structure "
                f"(mtf {alignment:+.2f}, h={hours:.1f}): "
                + "; ".join(setup.reasons[:4])
            ),
            features={
                "challenger_only": True,
                "structure_schema_version": 1,
                "setup_score": setup.score,
                "setup_reasons": setup.reasons,
                "mtf_alignment": alignment,
                "expected_log_return": expected_log_return,
                "shift_in_horizon_sigma": MAX_SHIFT_SIGMA * setup.score,
                "horizon_log_return_sigma": horizon_sigma,
                "structure": structure_features,
                "hourly_source": state.get("hourly_source"),
            },
        )
