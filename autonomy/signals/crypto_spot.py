"""Crypto signal: spot + realized volatility vs Kalshi BTC/ETH/SOL markets.

Kalshi crypto markets settle on index prices over short horizons. A driftless
lognormal model over time-to-close, with sigma from recent realized vol
(public Coinbase candles, no key), prices P(settle above strike). Honest
about its own limits: at long horizons or through scheduled events the
uncertainty term widens and the allocator's edge threshold filters it out.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any, Callable

from autonomy.ontology import MarketView, Signal, Vertical

# e.g. KXBTCD-26JUL0917-T71249.99 — date token with the closing hour glued on.
_TICKER_RE = re.compile(
    r"^(?:KX)?(BTC|ETH|SOL)[A-Z]*-(\d{2}[A-Z]{3}\d{2})(\d{2})?-[BT]([\d.]+)$"
)
# Native direction contracts use the opening CF Benchmarks value as the floor
# strike in the market payload; their ticker suffix is not a price.
_DIRECTION_15M_RE = re.compile(
    r"^KX(BTC|ETH|SOL)15M-(\d{2}[A-Z]{3}\d{6})-(?:00|15|30|45)$"
)

_PRODUCTS = {"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD"}

# ``Signal.uncertainty`` is epistemic probability uncertainty used by the
# ensemble's inverse-variance weighting.  The old implementation stored the
# horizon log-return sigma here (often 0.002-0.004 for one-hour contracts),
# which is an aleatoric distribution width in different units.  That made two
# related crypto models look hundreds of times more certain than the market.
CRYPTO_PROBABILITY_UNCERTAINTY_FLOOR = 0.08


def crypto_probability_uncertainty(
    probability: float, horizon_sigma: float, event_bump: float = 0.0,
) -> float:
    """Conservative probability-model uncertainty, not return volatility.

    ``event_bump`` widens uncertainty inside scheduled macro windows
    (autonomy/crypto_events.py); it never shifts the mean and is 0.0 outside
    every window, keeping non-event forecasts byte-identical.
    """
    boundary_sensitivity = 4.0 * probability * (1.0 - probability)
    horizon_penalty = min(0.08, max(0.0, horizon_sigma) * 1.5)
    return min(
        0.35,
        max(
            CRYPTO_PROBABILITY_UNCERTAINTY_FLOOR,
            CRYPTO_PROBABILITY_UNCERTAINTY_FLOOR
            + 0.04 * boundary_sensitivity
            + horizon_penalty
            + max(0.0, event_bump),
        ),
    )


def _fetch_hourly_closes(asset: str) -> list[float]:
    """Most-recent-first hourly closes from public Coinbase Exchange candles."""
    import httpx

    product = _PRODUCTS[asset]
    candles = httpx.get(
        f"https://api.exchange.coinbase.com/products/{product}/candles",
        params={"granularity": 3600},  # hourly, most recent ~300
        timeout=15,
    )
    candles.raise_for_status()
    rows = candles.json()  # [time, low, high, open, close, volume] newest first
    closes = [float(r[4]) for r in rows[:168]]  # ~7 days hourly
    if len(closes) < 24:
        raise ValueError("insufficient candle history")
    return closes


def default_fetch_spot_and_vol(asset: str) -> tuple[float, float]:
    """Return (spot, annualized_vol) from public Coinbase Exchange candles."""
    closes = _fetch_hourly_closes(asset)
    spot = closes[0]
    rets = [math.log(closes[i] / closes[i + 1]) for i in range(len(closes) - 1) if closes[i + 1] > 0]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / max(1, len(rets) - 1)
    hourly_sigma = math.sqrt(var)
    annualized = hourly_sigma * math.sqrt(24 * 365)
    return spot, annualized


# EWMA decay (RiskMetrics standard). Recent hours dominate: after a vol
# shock the estimate reacts within hours, not the flat window's days.
EWMA_LAMBDA = 0.94


def ewma_spot_and_vol(asset: str, closes: list[float] | None = None) -> tuple[float, float]:
    """(spot, annualized EWMA vol) — reactive alternative to the flat window."""
    closes = closes or _fetch_hourly_closes(asset)
    spot = closes[0]
    # Oldest-first returns so the recursion ends weighted toward now.
    ordered = list(reversed(closes))
    rets = [math.log(ordered[i] / ordered[i - 1]) for i in range(1, len(ordered)) if ordered[i - 1] > 0]
    if not rets:
        raise ValueError("no returns")
    var = rets[0] ** 2
    for r in rets[1:]:
        var = EWMA_LAMBDA * var + (1.0 - EWMA_LAMBDA) * r * r
    annualized = math.sqrt(var) * math.sqrt(24 * 365)
    return spot, annualized


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def parse_crypto_ticker(ticker: str) -> dict[str, Any] | None:
    match = _TICKER_RE.match(ticker)
    if match:
        asset, _date, _hour, strike = match.groups()
        return {"asset": asset, "strike": float(strike), "contract_family": "ladder"}
    direction = _DIRECTION_15M_RE.match(ticker)
    if direction:
        asset, _date = direction.groups()
        return {"asset": asset, "strike": 0.0, "contract_family": "15m_direction"}
    return None


class CryptoSpotVolSignal:
    name = "crypto_spot_vol"

    def __init__(
        self,
        fetch_spot_and_vol: Callable[[str], tuple[float, float]] | None = None,
        decision_time_fn: Callable[[], datetime] | None = None,
    ):
        self.fetch_spot_and_vol = fetch_spot_and_vol or default_fetch_spot_and_vol
        self.decision_time_fn = decision_time_fn
        self._cache: dict[str, tuple[float, float]] = {}

    def on_cycle_start(self) -> None:
        """A continuous daemon must never reuse a previous cycle's spot."""
        self._cache.clear()
        owner = getattr(self.fetch_spot_and_vol, "__self__", None)
        reset = getattr(owner, "clear", None)
        if callable(reset):
            reset()

    def applicable(self, market: MarketView) -> bool:
        return market.vertical is Vertical.CRYPTO and parse_crypto_ticker(market.ticker) is not None

    def _hours_to_close(self, market: MarketView) -> float:
        try:
            close = datetime.fromisoformat(market.close_time.replace("Z", "+00:00"))
            decision_time = (
                self.decision_time_fn()
                if self.decision_time_fn is not None
                else datetime.now(timezone.utc)
            )
            if decision_time.tzinfo is None:
                raise ValueError("decision time must include a timezone")
            decision_time = decision_time.astimezone(timezone.utc)
            return max(
                0.05,
                (close - decision_time).total_seconds() / 3600.0,
            )
        except Exception:
            return 24.0

    def _event_bump(self) -> float:
        from autonomy.crypto_events import active_bump

        if self.decision_time_fn is None:
            return active_bump()
        decision_time = self.decision_time_fn()
        if decision_time.tzinfo is None:
            raise ValueError("decision time must include a timezone")
        return active_bump(decision_time.astimezone(timezone.utc))

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_crypto_ticker(market.ticker)
        if parsed is None:
            return None
        asset = parsed["asset"]
        if asset not in self._cache:
            self._cache[asset] = self.fetch_spot_and_vol(asset)
        spot, annual_vol = self._cache[asset]
        if spot <= 0 or annual_vol <= 0:
            return None
        hours = self._hours_to_close(market)
        horizon_sigma = annual_vol * math.sqrt(hours / (24 * 365))
        if horizon_sigma <= 0:
            return None

        def p_above(strike: float) -> float | None:
            # Driftless lognormal: P(S_T >= K) = Phi(ln(S/K)/sigma_T)
            # A non-positive strike is malformed market metadata (e.g. a
            # 15m-direction ticker whose missing floor_strike parses to 0).
            # Abstain instead of emitting a fabricated near-certain YES —
            # the old `return 1.0` was the audit's fail-open finding; the
            # paper twin's equivalent path already abstains.
            if strike <= 0:
                return None
            return _normal_cdf(math.log(spot / strike) / horizon_sigma)

        strike_type = str(market.raw.get("strike_type", "")).lower()
        floor = market.raw.get("floor_strike")
        cap = market.raw.get("cap_strike")
        p_yes: float | None
        if strike_type in {"greater", "greater_or_equal"} and floor is not None:
            p_yes = p_above(float(floor))
        elif strike_type == "less" and cap is not None:
            above_cap = p_above(float(cap))
            p_yes = None if above_cap is None else 1.0 - above_cap
        elif strike_type == "between" and floor is not None and cap is not None:
            above_floor = p_above(float(floor))
            above_cap = p_above(float(cap))
            p_yes = (
                None if above_floor is None or above_cap is None
                else above_floor - above_cap
            )
        else:
            p_yes = p_above(parsed["strike"])
        if p_yes is None:
            return None
        p_yes = min(0.995, max(0.005, p_yes))
        probability_uncertainty = crypto_probability_uncertainty(
            p_yes,
            horizon_sigma,
            event_bump=self._event_bump(),
        )
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=p_yes,
            uncertainty=probability_uncertainty,
            rationale=(
                f"{asset} spot={spot:.0f} annvol={annual_vol:.0%} h={hours:.1f} "
                f"{strike_type or 'threshold'} floor={floor} cap={cap}"
            ),
            features={
                "spot": spot,
                "annual_vol": annual_vol,
                "hours_to_close": hours,
                "horizon_log_return_sigma": horizon_sigma,
                "probability_model_uncertainty": probability_uncertainty,
            },
        )


# Fat-tail mixture: hourly crypto returns are leptokurtic; a single normal
# underprices far strikes (exactly where the champion's edge lives). Model as
# a two-regime normal mixture — calm and stressed — with the scales chosen so
# blended variance matches the EWMA estimate (0.85·0.88² + 0.15·1.53² ≈ 1).
MIX_CALM_WEIGHT = 0.85
MIX_CALM_SCALE = 0.88
MIX_STRESS_SCALE = 1.53


class CryptoEwmaTailSignal(CryptoSpotVolSignal):
    """Challenger to crypto_spot_vol: EWMA vol + fat-tail mixture.

    Runs beside the champion under its own source name; the contested
    calibration record decides which model earns fusion weight. This is the
    self-improvement mechanism for models: challengers earn their way in or
    are starved of trust — nothing is replaced on faith.
    """

    name = "crypto_ewma_t"

    def __init__(self, fetch_spot_and_vol=None, decision_time_fn=None):
        super().__init__(
            fetch_spot_and_vol=fetch_spot_and_vol or ewma_spot_and_vol,
            decision_time_fn=decision_time_fn,
        )

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_crypto_ticker(market.ticker)
        if parsed is None:
            return None
        asset = parsed["asset"]
        if asset not in self._cache:
            self._cache[asset] = self.fetch_spot_and_vol(asset)
        spot, annual_vol = self._cache[asset]
        if spot <= 0 or annual_vol <= 0:
            return None
        hours = self._hours_to_close(market)
        horizon_sigma = annual_vol * math.sqrt(hours / (24 * 365))
        if horizon_sigma <= 0:
            return None

        def p_above(strike: float) -> float:
            if strike <= 0:
                return 1.0
            z = math.log(spot / strike)
            return (MIX_CALM_WEIGHT * _normal_cdf(z / (horizon_sigma * MIX_CALM_SCALE))
                    + (1.0 - MIX_CALM_WEIGHT) * _normal_cdf(z / (horizon_sigma * MIX_STRESS_SCALE)))

        strike_type = str(market.raw.get("strike_type", "")).lower()
        floor = market.raw.get("floor_strike")
        cap = market.raw.get("cap_strike")
        if strike_type in {"greater", "greater_or_equal"} and floor is not None:
            p_yes = p_above(float(floor))
        elif strike_type == "less" and cap is not None:
            p_yes = 1.0 - p_above(float(cap))
        elif strike_type == "between" and floor is not None and cap is not None:
            p_yes = p_above(float(floor)) - p_above(float(cap))
        else:
            p_yes = p_above(parsed["strike"])
        p_yes = min(0.995, max(0.005, p_yes))
        probability_uncertainty = crypto_probability_uncertainty(
            p_yes,
            horizon_sigma,
            event_bump=self._event_bump(),
        )
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=p_yes,
            uncertainty=probability_uncertainty,
            rationale=(
                f"{asset} spot={spot:.0f} ewma_vol={annual_vol:.0%} h={hours:.1f} fat-tail mix "
                f"{strike_type or 'threshold'} floor={floor} cap={cap}"
            ),
            features={
                "spot": spot,
                "ewma_annual_vol": annual_vol,
                "hours_to_close": hours,
                "horizon_log_return_sigma": horizon_sigma,
                "probability_model_uncertainty": probability_uncertainty,
                "mixture": [MIX_CALM_WEIGHT, MIX_CALM_SCALE, MIX_STRESS_SCALE],
            },
        )
