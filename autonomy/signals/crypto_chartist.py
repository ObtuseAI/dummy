"""Chartist challenger: the cross-examined technical view, priced (Wave-24).

Wraps ``autonomy.crypto_chartist`` -- candlestick patterns, regular + hidden
divergences, EMA/channel trends, across the 5m/15m/1h/4h/1d ladder -- into
one drift-shaped challenger emission per crypto market, the same lognormal
mechanics as the KAMA challenger: the cross-exam score bends the base
spot/vol probability by a capped drift, conviction narrows uncertainty, and
heavy timeframe disagreement abstains outright (an analyst whose charts
argue with each other does not place the trade).

Challenger-only, fail-closed, deterministic given the hub state; every
emission carries the full per-timeframe vote table, boosts, vetoes, and
disagreements for audit.
"""
from __future__ import annotations

import logging
import math
from typing import Any, Callable

from autonomy.crypto_chartist import build_views, cross_examine
from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals.crypto_spot import parse_crypto_ticker

CHARTIST_MAX_DRIFT_SIGMAS = 0.75
CHARTIST_MIN_CONVICTION = 0.10
CHARTIST_MAX_DISAGREEMENTS = 2
LOGGER = logging.getLogger(__name__)


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _reference_price(market: MarketView) -> float | None:
    raw = market.raw or {}
    for key in ("floor_strike", "cap_strike", "strike"):
        value = raw.get(key)
        if value is None:
            continue
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            return parsed
    return None


class CryptoChartistSignal:
    name = "crypto_chartist"

    def __init__(
        self,
        fetch_state: Callable[[str], dict[str, Any]],
        hours_to_close: Callable[[MarketView], float] | None = None,
    ) -> None:
        self._fetch_state = fetch_state
        if hours_to_close is None:
            from autonomy.signals.crypto_indicators import _hours_to_close

            hours_to_close = _hours_to_close
        self.hours_to_close = hours_to_close
        self._views_cache: dict[str, Any] = {}
        self._diagnostics_cache: dict[str, dict[str, Any]] = {}

    def on_cycle_start(self) -> None:
        self._views_cache = {}
        self._diagnostics_cache = {}

    def applicable(self, market: MarketView) -> bool:
        return (
            market.vertical is Vertical.CRYPTO
            and parse_crypto_ticker(market.ticker) is not None
        )

    def _exam(self, asset: str):
        if asset not in self._views_cache:
            state: dict[str, Any] | None = None
            try:
                state = self._fetch_state(asset)
                views = build_views(state) if state else {}
            except Exception as exc:
                views = {}
                self._diagnostics_cache[asset] = {
                    "status": "UNAVAILABLE",
                    "reason": "chartist_input_error",
                    "error_type": type(exc).__name__,
                }
                LOGGER.warning(
                    "crypto chartist abstained for %s: input error %s",
                    asset,
                    type(exc).__name__,
                    exc_info=True,
                )
            else:
                self._diagnostics_cache[asset] = {
                    "status": "COMPLETE" if views else "PARTIAL",
                    "reason": None if views else "no_timeframe_has_25_closed_bars",
                    "available_timeframes": sorted(views),
                    "stream_rows": {
                        stream: len((state or {}).get(f"{stream}_ohlcv") or [])
                        for stream in ("minute", "five_minute", "hourly", "daily")
                    },
                }
            self._views_cache[asset] = (
                views, cross_examine(views) if views else None, state if views else None)
        return self._views_cache[asset]

    def diagnostic_for(self, asset: str) -> dict[str, Any]:
        """Return the structured reason for an emission or fail-closed abstention."""
        self._exam(str(asset).upper())
        return dict(self._diagnostics_cache.get(str(asset).upper(), {}))

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_crypto_ticker(market.ticker)
        if parsed is None:
            return None
        views, exam, state = self._exam(str(parsed["asset"]))
        if exam is None or state is None or state.get("spot") is None:
            return None
        if exam.conviction < CHARTIST_MIN_CONVICTION:
            return None
        if len(exam.disagreements) > CHARTIST_MAX_DISAGREEMENTS:
            return None   # the charts argue with each other; no view emitted

        spot = float(state["spot"])
        reference = _reference_price(market)
        if reference is None or spot <= 0:
            return None
        hours = self.hours_to_close(market)
        annual_vol = state.get("realized_vol_60m_annualized") or state.get(
            "realized_vol_7d_annualized")
        if not annual_vol or float(annual_vol) <= 0 or hours <= 0:
            return None
        sigma_h = float(annual_vol) * math.sqrt(hours / (24.0 * 365.0))
        if sigma_h <= 0:
            return None

        drift = exam.score * CHARTIST_MAX_DRIFT_SIGMAS * sigma_h
        z = (math.log(spot / reference) + drift) / sigma_h
        p_above = _normal_cdf(z)
        yes_is_above = str((market.raw or {}).get("strike_type", "")).lower() != "less"
        probability = min(0.995, max(0.005, p_above if yes_is_above else 1.0 - p_above))
        uncertainty = min(0.35, max(0.10, 0.32 - 0.20 * exam.conviction))
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=probability,
            uncertainty=uncertainty,
            rationale=(
                f"chartist: score={exam.score:+.2f} conviction={exam.conviction:.2f} "
                f"votes={exam.votes} vetoes={list(exam.vetoes)}"
            )[:400],
            features={
                "challenger_only": True,
                "chart_score": exam.score,
                "chart_conviction": exam.conviction,
                "chart_votes": dict(exam.votes),
                "chart_boosts": list(exam.boosts),
                "chart_vetoes": list(exam.vetoes),
                "chart_disagreements": list(exam.disagreements),
                "chart_input_diagnostic": dict(
                    self._diagnostics_cache.get(str(parsed["asset"]), {})
                ),
                "patterns": {
                    name: [
                        {"name": p.name, "dir": p.direction, "s": p.strength}
                        for p in view.patterns
                    ]
                    for name, view in views.items() if view.patterns
                },
                "hours_to_close": hours,
            },
        )
