"""Crypto macro-regime challenger: risk-appetite drift from public macro data.

Crypto trades as a long-duration risk asset. It rises with equity risk-on and
falls with a strengthening dollar, rising real yields, and fear spikes. This
signal reads a handful of keyless public macro series (Yahoo Finance chart API,
the same feed the retired commodities signal used) and turns their recent moves
into a bounded, auditable *risk-appetite score*, which it applies as a modest
directional drift on the crypto lognormal -- exactly the shape of the technical
composite challenger, but sourced from macro instead of order-flow technicals.

Discipline mirrors the other crypto challengers:
  * challenger_only=True -- logged as point-in-time evidence, never fused into
    the execution ensemble until a settlement-backed promotion review. Breadth
    cannot silently alter live risk.
  * fail-closed / non-destructive -- no macro feed, no crypto state, or a
    degenerate horizon => the signal abstains (returns None) and the crypto
    forecast is byte-identical to a run without it.
  * the drift scales with horizon_sigma, so it self-limits to ~zero on the
    ultra-short (15m/hourly) contracts where macro has no predictive content
    and only opines meaningfully on multi-hour/daily horizons.
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
from autonomy.taxonomy import horizon_bucket

# Macro factors: (feature key, Yahoo symbol, signed coefficient, characteristic
# 5-session move). The coefficient sign encodes crypto's correlation with the
# factor; its magnitude is a fixed research prior (NOT fit on Dummy's ledger).
# tanh(change / scale) bounds each factor's pull and keeps an outlier print from
# dominating. Equities and a weak dollar lift crypto; VIX/yields/DXY suppress it;
# gold and oil contribute a mild liquidity/growth tilt.
MACRO_FACTORS: tuple[tuple[str, str, float, float], ...] = (
    ("sp500", "^GSPC", 0.30, 0.020),      # equity risk-on
    ("dxy", "DX-Y.NYB", -0.22, 0.015),    # a strong dollar drains crypto
    ("vix", "^VIX", -0.20, 0.20),         # fear spike -> risk-off
    ("ust10y", "^TNX", -0.15, 0.08),      # rising real yields hurt long-duration risk
    ("gold", "GC=F", 0.08, 0.025),        # debasement / liquidity proxy
    ("oil", "CL=F", 0.05, 0.06),          # growth / risk proxy
)

_TOTAL_ABS_COEFF = sum(abs(coeff) for _, _, coeff, _ in MACRO_FACTORS)

# Macro expresses a drift RATE, not a fixed fraction of a standard deviation:
# the expected log-return is MACRO_DAILY_DRIFT * score over a full day and scales
# linearly with the fraction of a day to close. Because horizon_sigma grows as
# sqrt(hours), the resulting probability shift grows as sqrt(hours) -- macro moves
# a daily contract meaningfully but a 15-minute contract almost not at all, which
# is the correct behaviour for a slow driver. The shift is still capped at
# MACRO_MAX_SHIFT_SIGMA horizon standard deviations so a long horizon can never
# manufacture a near-certain probability.
MACRO_DAILY_DRIFT = 0.012   # max expected log-return over a day at score = +/-1
MACRO_MAX_SHIFT_SIGMA = 0.35

# Forward-registered promotion-candidate scope (2026-07-22 elite audit;
# runtime/autonomy/promotion_forward_registrations.json). promotion_eligible
# is stamped True for EXACTLY this grading scope's emissions -- the
# auto-promotion evaluator requires a majority per-scope opt-in before
# forward evidence can promote anything, and no other scope of this source
# is registered. The registration FINGERPRINT is never stamped here: the
# ledger stamps it at record time from the immutable registrations file
# (AutonomyLedger._stamp_forward_fingerprint), so a later re-implementation
# of this module cannot silently inherit the old registration.
SUPPORTED_CONTRACT_HORIZONS = frozenset({"daily+", "weekly"})
PROMOTION_ELIGIBLE_SCOPE = "crypto_macro_regime|sol|ladder|daily+"


def macro_regime_score(changes: dict[str, float]) -> tuple[float, float, dict[str, float]]:
    """Bounded risk-appetite score in [-1, 1] from recent macro % changes.

    Returns ``(score, coverage, components)``. A missing factor contributes zero
    and lowers coverage rather than silently rescaling the score. ``coverage`` is
    the fraction of the total factor weight that had usable data.
    """
    components: dict[str, float] = {}
    score = 0.0
    available = 0.0
    for key, _symbol, coeff, scale in MACRO_FACTORS:
        change = changes.get(key)
        if change is None:
            continue
        contribution = coeff * math.tanh(float(change) / scale)
        components[key] = contribution
        score += contribution
        available += abs(coeff)
    coverage = available / _TOTAL_ABS_COEFF if _TOTAL_ABS_COEFF > 0 else 0.0
    return max(-1.0, min(1.0, score)), coverage, components


def _pct_change(closes: list[float], sessions: int = 5) -> float | None:
    """Fractional change over the last ``sessions`` closes (e.g. 0.02 = +2%)."""
    usable = [c for c in closes if c is not None]
    if len(usable) <= sessions or usable[-1 - sessions] <= 0:
        return None
    return usable[-1] / usable[-1 - sessions] - 1.0


def default_fetch_macro_state(
    *,
    timeout_seconds: float = 15.0,
) -> dict[str, float]:
    """Recent macro % changes from the keyless Yahoo Finance chart API.

    One month of daily candles per symbol; a symbol that fails to fetch or lacks
    history is simply omitted (lowering coverage, never raising).
    """
    import httpx

    changes: dict[str, float] = {}
    for key, symbol, _coeff, _scale in MACRO_FACTORS:
        try:
            response = httpx.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                params={"range": "1mo", "interval": "1d"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=max(0.1, float(timeout_seconds)),
            )
            response.raise_for_status()
            result = response.json()["chart"]["result"][0]
            closes = result["indicators"]["quote"][0]["close"]
            change = _pct_change([c for c in closes if c is not None])
            if change is not None:
                changes[key] = change
        except Exception:
            continue  # one dead symbol never sinks the regime read
    return changes


class CryptoMacroRegimeSignal:
    """Macro risk-appetite drift on crypto markets; never fused automatically."""

    name = "crypto_macro_regime"

    def __init__(
        self,
        fetch_state: Callable[[str], dict[str, Any]] | None = None,
        fetch_macro: Callable[[], dict[str, float]] | None = None,
        hours_to_close: Callable[[MarketView], float] | None = None,
    ) -> None:
        self._hub = CryptoDataHub() if fetch_state is None else None
        self.fetch_state = fetch_state or self._hub.state
        self.fetch_macro = fetch_macro or default_fetch_macro_state
        self.hours_to_close = hours_to_close or _hours_to_close
        self._state_cache: dict[str, dict[str, Any]] = {}
        self._macro_cache: dict[str, float] | None = None

    def on_cycle_start(self) -> None:
        self._state_cache.clear()
        self._macro_cache = None
        owner = getattr(self.fetch_state, "__self__", None)
        clear = getattr(owner, "clear", None)
        if callable(clear):
            clear()

    def applicable(self, market: MarketView) -> bool:
        return market.vertical is Vertical.CRYPTO and parse_crypto_ticker(market.ticker) is not None

    def _macro(self) -> dict[str, float]:
        if self._macro_cache is None:
            try:
                self._macro_cache = dict(self.fetch_macro() or {})
            except Exception:
                self._macro_cache = {}
        return self._macro_cache

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_crypto_ticker(market.ticker)
        if parsed is None:
            return None
        hours = self.hours_to_close(market)
        if hours <= 0:
            return None
        contract_horizon = horizon_bucket(market.ticker, hours)
        # The inputs are five-session macro changes.  They have no defensible
        # point-in-time mapping to a 15-minute or hourly crypto outcome.
        if contract_horizon not in SUPPORTED_CONTRACT_HORIZONS:
            return None
        score, coverage, components = macro_regime_score(self._macro())
        if coverage <= 0.0:
            return None  # no macro data -> abstain (non-destructive)

        asset = str(parsed["asset"])
        if asset not in self._state_cache:
            try:
                self._state_cache[asset] = self.fetch_state(asset)
            except Exception:
                return None
        state = self._state_cache[asset]
        try:
            spot = float(state["spot"])
        except (KeyError, TypeError, ValueError):
            return None
        if spot <= 0:
            return None
        # dvol (implied) preferred; realized-vol fallback only computed if needed.
        # Any non-numeric vol field abstains rather than throwing (fail-closed).
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
        horizon_sigma = annual_vol * math.sqrt(hours / (24.0 * 365.0))
        if horizon_sigma <= 0:
            return None
        # Drift-rate over the horizon, capped at MACRO_MAX_SHIFT_SIGMA sigma.
        raw_drift = MACRO_DAILY_DRIFT * score * (hours / 24.0)
        sigma_cap = MACRO_MAX_SHIFT_SIGMA * horizon_sigma
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

        # Macro is a weak, slow driver, so the floor here is deliberately higher
        # than the technical composite's -- the ensemble weights it lightly until
        # its contested-Brier record earns more.
        uncertainty = min(
            0.45,
            max(
                0.20,
                crypto_probability_uncertainty(probability, horizon_sigma) + 0.06,
                (1.0 - coverage) * 0.30,
            ),
        )
        features = {
            "challenger_only": True,
            "macro_model_version": 1,
            "macro_score": score,
            "macro_coverage": coverage,
            "macro_components": components,
            "macro_changes": dict(self._macro()),
            "expected_log_return": expected_log_return,
            "shift_in_horizon_sigma": expected_log_return / horizon_sigma,
            "annual_vol_used": float(annual_vol),
            "horizon_log_return_sigma": horizon_sigma,
            "hours_to_close": hours,
            "contract_horizon": contract_horizon,
            "source_observation_horizon": "five_trading_sessions",
            "spot": spot,
            "probability_model_uncertainty": uncertainty,
        }
        try:
            from autonomy.taxonomy import grading_scope

            if (
                grading_scope(self.name, market.ticker, features)
                == PROMOTION_ELIGIBLE_SCOPE
            ):
                features["promotion_eligible"] = True
        except Exception:  # noqa: BLE001 - fail closed: no opt-in stamp
            pass
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=probability,
            uncertainty=uncertainty,
            rationale=(
                f"{asset} macro risk-appetite score={score:.3f} coverage={coverage:.2f} "
                f"shift={expected_log_return / horizon_sigma:.2f}sigma; challenger-only"
            ),
            features=features,
        )
