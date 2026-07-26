"""Crypto-equities flow challenger: BTC/ETH ETFs, crypto stocks, treasuries.

Operator directive 2026-07-12: crypto should track Bitcoin ETFs, crypto-
related stocks, and "treasury" companies. The equity market prices crypto
exposure all session with institutional flow the spot tape doesn't show:
spot-ETF volume is the cleanest public proxy for institutional appetite,
COIN/MARA/RIOT carry levered crypto beta, and MSTR trades as a
BTC-treasury vehicle whose premium behavior leads risk appetite.

Same discipline as the macro challenger it mirrors (crypto_macro.py):
  * challenger_only=True -- logged + contested-Brier graded, never fused
    into the execution ensemble until an explicit promotion review.
  * fail-closed -- no equity data, no crypto state, or a degenerate horizon
    means abstain (None); forecasts without this signal are byte-identical.
  * bounded -- score in [-1, 1], drift capped at EQUITY_MAX_SHIFT_SIGMA
    horizon standard deviations; a long horizon can never manufacture
    certainty out of a hot week for MSTR.
  * divergence honesty -- when the equity complex disagrees with the spot
    tape's own recent momentum, uncertainty WIDENS instead of one side
    being silently trusted.

Data: the keyless Yahoo Finance chart API already used by the macro signal
(one fetch per cycle for the whole factor list; symbols verified live
2026-07-12: IBIT, FBTC, ETHA, MSTR, COIN, MARA, RIOT).
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

# (key, yahoo_symbol, coefficient, tanh scale). Coefficients are all positive
# (every factor is crypto-long exposure); scale normalizes each instrument's
# typical weekly move so tanh saturates comparably.
EQUITY_FACTORS: tuple[tuple[str, str, float, float], ...] = (
    ("ibit", "IBIT", 1.00, 0.05),   # spot BTC ETF -- institutional flow proxy
    ("fbtc", "FBTC", 0.50, 0.05),   # second BTC ETF (redundancy, lower weight)
    ("etha", "ETHA", 0.60, 0.06),   # spot ETH ETF
    ("mstr", "MSTR", 0.80, 0.12),   # BTC treasury company (levered, noisy)
    ("coin", "COIN", 0.70, 0.08),   # exchange equity, broad crypto beta
    ("mara", "MARA", 0.40, 0.12),   # miner beta
    ("riot", "RIOT", 0.40, 0.12),   # miner beta
)

# Per-asset factor relevance: the ETH ETF says little about a BTC strike and
# vice versa; stocks/treasuries carry broad-complex beta for every asset.
_ASSET_FACTOR_WEIGHT: dict[str, dict[str, float]] = {
    "BTC": {"ibit": 1.0, "fbtc": 1.0, "etha": 0.3, "mstr": 1.0,
            "coin": 1.0, "mara": 1.0, "riot": 1.0},
    "ETH": {"ibit": 0.4, "fbtc": 0.4, "etha": 1.0, "mstr": 0.5,
            "coin": 1.0, "mara": 0.5, "riot": 0.5},
    "SOL": {"ibit": 0.4, "fbtc": 0.4, "etha": 0.5, "mstr": 0.5,
            "coin": 1.0, "mara": 0.5, "riot": 0.5},
}

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
PROMOTION_ELIGIBLE_SCOPE = "crypto_equities_flow|sol|ladder|daily+"

EQUITY_DAILY_DRIFT = 0.010      # max expected log-return over a day at score +/-1
EQUITY_MAX_SHIFT_SIGMA = 0.35   # hard cap in horizon standard deviations
# ETF volume surge (recent 5d vs prior 15d avg) above this reads as a flow
# event; it can amplify conviction by at most EQUITY_FLOW_AMPLIFIER_CAP.
EQUITY_FLOW_SURGE_THRESHOLD = 1.5
EQUITY_FLOW_AMPLIFIER_CAP = 1.25
# Extra uncertainty when the equity complex fights the spot tape's momentum.
EQUITY_DIVERGENCE_PENALTY = 0.05


def equity_flow_score(
    changes: dict[str, float], asset: str,
) -> tuple[float, float, dict[str, float]]:
    """Bounded [-1, 1] crypto-appetite score from equity %-changes.

    Mirrors ``macro_regime_score``: a missing factor contributes zero and
    lowers coverage instead of silently rescaling the score. Factor weights
    are asset-conditioned (the ETH ETF barely opines on a BTC strike).
    """
    weights = _ASSET_FACTOR_WEIGHT.get(asset, _ASSET_FACTOR_WEIGHT["BTC"])
    components: dict[str, float] = {}
    score = 0.0
    available = 0.0
    total = 0.0
    for key, _symbol, coeff, scale in EQUITY_FACTORS:
        relevance = weights.get(key, 0.5)
        total += abs(coeff) * relevance
        change = changes.get(key)
        if change is None:
            continue
        contribution = coeff * relevance * math.tanh(float(change) / scale)
        components[key] = contribution
        score += contribution
        available += abs(coeff) * relevance
    coverage = available / total if total > 0 else 0.0
    return max(-1.0, min(1.0, score)), coverage, components


def _pct_change(closes: list[float], sessions: int = 5) -> float | None:
    usable = [value for value in closes if value is not None]
    if len(usable) <= sessions or usable[-1 - sessions] <= 0:
        return None
    return usable[-1] / usable[-1 - sessions] - 1.0


def _volume_surge(volumes: list[float]) -> float | None:
    """Recent 5-session avg volume vs the prior 15-session baseline."""
    usable = [value for value in volumes if value is not None and value > 0]
    if len(usable) < 20:
        return None
    recent = sum(usable[-5:]) / 5.0
    baseline = sum(usable[-20:-5]) / 15.0
    return recent / baseline if baseline > 0 else None


def default_fetch_equity_state(
    *,
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    """Keyless Yahoo chart fetch: %-changes for every factor + ETF volume surge.

    A symbol that fails is omitted (lower coverage, never a raise) --
    identical failure discipline to the macro fetch it mirrors.
    """
    import httpx

    changes: dict[str, float] = {}
    etf_volume_surges: dict[str, float] = {}
    for key, symbol, _coeff, _scale in EQUITY_FACTORS:
        try:
            response = httpx.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                params={"range": "3mo", "interval": "1d"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=max(0.1, float(timeout_seconds)),
            )
            response.raise_for_status()
            result = response.json()["chart"]["result"][0]
            quote = result["indicators"]["quote"][0]
            change = _pct_change(quote.get("close") or [])
            if change is not None:
                changes[key] = change
            if key in {"ibit", "fbtc", "etha"}:
                surge = _volume_surge(quote.get("volume") or [])
                if surge is not None:
                    etf_volume_surges[key] = surge
        except Exception:
            continue  # one dead symbol never sinks the flow read
    return {"changes": changes, "etf_volume_surges": etf_volume_surges}


class CryptoEquitiesSignal:
    """Equity-complex crypto-appetite drift; never fused automatically."""

    name = "crypto_equities_flow"

    def __init__(
        self,
        fetch_state: Callable[[str], dict[str, Any]] | None = None,
        fetch_equities: Callable[[], dict[str, Any]] | None = None,
        hours_to_close: Callable[[MarketView], float] | None = None,
    ) -> None:
        self._hub = CryptoDataHub() if fetch_state is None else None
        self.fetch_state = fetch_state or self._hub.state
        self.fetch_equities = fetch_equities or default_fetch_equity_state
        self.hours_to_close = hours_to_close or _hours_to_close
        self._state_cache: dict[str, dict[str, Any]] = {}
        self._equity_cache: dict[str, Any] | None = None

    def on_cycle_start(self) -> None:
        self._state_cache.clear()
        self._equity_cache = None
        owner = getattr(self.fetch_state, "__self__", None)
        clear = getattr(owner, "clear", None)
        if callable(clear):
            clear()

    def applicable(self, market: MarketView) -> bool:
        return market.vertical is Vertical.CRYPTO and parse_crypto_ticker(market.ticker) is not None

    def _equities(self) -> dict[str, Any]:
        if self._equity_cache is None:
            try:
                self._equity_cache = dict(self.fetch_equities() or {})
            except Exception:
                self._equity_cache = {}
        return self._equity_cache

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_crypto_ticker(market.ticker)
        if parsed is None:
            return None
        hours = self.hours_to_close(market)
        if hours <= 0:
            return None
        contract_horizon = horizon_bucket(market.ticker, hours)
        # Daily equity/ETF closes and volume aggregates cannot support
        # sub-daily crypto forecasts.  Abstain before fetching either feed.
        if contract_horizon not in SUPPORTED_CONTRACT_HORIZONS:
            return None
        asset = str(parsed["asset"])
        equity_state = self._equities()
        changes = dict(equity_state.get("changes") or {})
        score, coverage, components = equity_flow_score(changes, asset)
        if coverage <= 0.0:
            return None  # no equity data -> abstain, byte-identical without us

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
        indicators = _indicator_features(state)  # one pass; reused for divergence
        try:
            if state.get("dvol") is not None:
                annual_vol: float | None = float(state["dvol"]) / 100.0
            else:
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

        # A genuine ETF flow event (volume surge in the direction of the
        # score) modestly amplifies conviction, hard-capped.
        surges = dict(equity_state.get("etf_volume_surges") or {})
        max_surge = max(surges.values(), default=None)
        amplifier = 1.0
        if max_surge is not None and max_surge > EQUITY_FLOW_SURGE_THRESHOLD:
            amplifier = min(
                EQUITY_FLOW_AMPLIFIER_CAP,
                1.0 + (max_surge - EQUITY_FLOW_SURGE_THRESHOLD) * 0.25,
            )

        raw_drift = EQUITY_DAILY_DRIFT * score * amplifier * (hours / 24.0)
        sigma_cap = EQUITY_MAX_SHIFT_SIGMA * horizon_sigma
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

        # Divergence honesty: equity complex vs the spot tape's own recent
        # momentum. Disagreement widens uncertainty rather than picking a
        # winner -- the contested-Brier record decides who earns trust.
        spot_momentum = indicators.get("hourly_momentum_24h_bps")
        divergence_penalty = 0.0
        if spot_momentum is not None and abs(score) > 0.1:
            if float(spot_momentum) * score < 0:
                divergence_penalty = EQUITY_DIVERGENCE_PENALTY

        uncertainty = min(
            0.45,
            max(
                0.18,
                crypto_probability_uncertainty(probability, horizon_sigma) + 0.05,
                (1.0 - coverage) * 0.30,
            ) + divergence_penalty,
        )
        features: dict[str, Any] = {
            "challenger_only": True,
            "equities_model_version": 1,
            "equity_score": score,
            "equity_coverage": coverage,
            "equity_components": components,
            "equity_changes": changes,
            "etf_volume_surges": surges,
            "flow_amplifier": amplifier,
            "spot_equity_divergence": bool(divergence_penalty),
            "expected_log_return": expected_log_return,
            "shift_in_horizon_sigma": expected_log_return / horizon_sigma,
            "annual_vol_used": float(annual_vol),
            "horizon_log_return_sigma": horizon_sigma,
            "hours_to_close": hours,
            "contract_horizon": contract_horizon,
            "source_observation_horizon": "daily_equity_sessions",
            "spot": spot,
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
                f"{asset} equity-flow score={score:.3f} coverage={coverage:.2f} "
                f"amp={amplifier:.2f} shift={expected_log_return / horizon_sigma:.2f}sigma"
                + ("; diverges from spot tape" if divergence_penalty else "")
                + "; challenger-only"
            ),
            features=features,
        )
