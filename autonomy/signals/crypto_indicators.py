"""Crypto regime, technical, and implied-volatility challengers.

Public Coinbase, Kraken, and Deribit reads are cached once per asset/cycle.
All three probability models are deliberately marked ``challenger_only``:
their signals are logged and graded, while the ensemble excludes them until
later point-in-time evidence justifies an explicit promotion.
"""
from __future__ import annotations

import math
import statistics
import time
from datetime import datetime, timezone
from typing import Any, Callable

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals.crypto_spot import (
    _PRODUCTS,
    _normal_cdf,
    crypto_probability_uncertainty,
    parse_crypto_ticker,
)

_KRAKEN_PAIRS = {"BTC": "XXBTZUSD", "ETH": "XETHZUSD", "SOL": "SOLUSD"}


def _annualized_vol(closes: list[float], periods_per_year: int) -> float | None:
    returns = [
        math.log(closes[index] / closes[index - 1])
        for index in range(1, len(closes))
        if closes[index - 1] > 0 and closes[index] > 0
    ]
    if len(returns) < 2:
        return None
    return statistics.stdev(returns) * math.sqrt(periods_per_year)


def _ema(values: list[float], span: int) -> float | None:
    if not values:
        return None
    alpha = 2.0 / (span + 1.0)
    value = float(values[0])
    for observation in values[1:]:
        value = alpha * float(observation) + (1.0 - alpha) * value
    return value


def _rsi(values: list[float], periods: int = 14) -> float | None:
    if len(values) < periods + 1:
        return None
    changes = [values[index] - values[index - 1] for index in range(1, len(values))]
    recent = changes[-periods:]
    gains = sum(max(0.0, change) for change in recent) / periods
    losses = sum(max(0.0, -change) for change in recent) / periods
    if losses == 0:
        return 100.0 if gains > 0 else 50.0
    relative = gains / losses
    return 100.0 - 100.0 / (1.0 + relative)


def _change_bps(values: list[float], periods: int) -> float | None:
    if len(values) <= periods or values[-periods - 1] <= 0:
        return None
    return 10_000.0 * (values[-1] / values[-periods - 1] - 1.0)


def _indicator_features(state: dict[str, Any]) -> dict[str, Any]:
    minute = [float(value) for value in state.get("minute_closes") or []]
    hourly = [float(value) for value in state.get("hourly_closes") or []]
    volumes = [float(value) for value in state.get("minute_volumes") or []]
    ema12 = _ema(minute[-120:], 12)
    ema26 = _ema(minute[-180:], 26)
    hourly_ema12 = _ema(hourly[-120:], 12)
    hourly_ema26 = _ema(hourly[-180:], 26)
    spot = float(state["spot"])
    recent_vol = _annualized_vol(minute[-61:], 60 * 24 * 365) if len(minute) >= 61 else None
    long_vol = _annualized_vol(hourly[-169:], 24 * 365) if len(hourly) >= 25 else None
    volume_surge = None
    if len(volumes) >= 75:
        recent = sum(volumes[-15:]) / 15.0
        baseline = sum(volumes[-75:-15]) / 60.0
        volume_surge = recent / baseline if baseline > 0 else None
    return {
        "momentum_5m_bps": _change_bps(minute, 5),
        "momentum_15m_bps": _change_bps(minute, 15),
        "momentum_60m_bps": _change_bps(minute, 60),
        "rsi_14m": _rsi(minute, 14),
        "macd_12_26_bps": (
            10_000.0 * (ema12 - ema26) / spot
            if ema12 is not None and ema26 is not None and spot > 0 else None
        ),
        "hourly_momentum_1h_bps": _change_bps(hourly, 1),
        "hourly_momentum_4h_bps": _change_bps(hourly, 4),
        "hourly_momentum_24h_bps": _change_bps(hourly, 24),
        "hourly_rsi_14h": _rsi(hourly, 14),
        "hourly_macd_12_26_bps": (
            10_000.0 * (hourly_ema12 - hourly_ema26) / spot
            if hourly_ema12 is not None and hourly_ema26 is not None and spot > 0 else None
        ),
        "realized_vol_60m_annualized": recent_vol,
        "realized_vol_7d_annualized": long_vol,
        "vol_regime_ratio": (
            recent_vol / long_vol if recent_vol is not None and long_vol else None
        ),
        "volume_surge_15m": volume_surge,
        "top_book_imbalance": state.get("book_imbalance"),
        "microprice_basis_bps": state.get("microprice_basis_bps"),
        "venue_divergence_bps": state.get("venue_divergence_bps"),
        "deribit_dvol": state.get("dvol"),
        "deribit_dvol_at_ms": state.get("dvol_at_ms"),
        "coinbase_hourly_age_s": state.get("coinbase_hourly_age_s"),
        "coinbase_minute_age_s": state.get("coinbase_minute_age_s"),
    }


class CryptoDataHub:
    """One public multi-venue state fetch per asset and cycle."""

    def __init__(
        self,
        client_factory: Callable[[], Any] | None = None,
        now_s: Callable[[], float] | None = None,
    ) -> None:
        self.client_factory = client_factory
        self.now_s = now_s or time.time
        self._cache: dict[str, dict[str, Any]] = {}

    def clear(self) -> None:
        self._cache.clear()

    def _client(self):
        if self.client_factory is not None:
            return self.client_factory()
        import httpx

        return httpx.Client(
            timeout=20,
            headers={"User-Agent": "DummyPredictionResearch/0.1 (public-read-only)"},
        )

    @staticmethod
    def _candle_rows(client: Any, product: str, granularity: int) -> list[list[float]]:
        response = client.get(
            f"https://api.exchange.coinbase.com/products/{product}/candles",
            params={"granularity": granularity},
        )
        response.raise_for_status()
        rows = response.json()
        parsed = [row for row in rows if isinstance(row, list) and len(row) >= 6]
        return sorted(parsed, key=lambda row: int(row[0]))

    @staticmethod
    def _kraken_hourly_rows(client: Any, asset: str) -> list[list[float]]:
        """Kraken hourly OHLC mapped to the Coinbase candle row shape."""
        response = client.get(
            "https://api.kraken.com/0/public/OHLC",
            params={"pair": _KRAKEN_PAIRS[asset], "interval": 60},
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            raise ValueError("kraken ohlc error")
        result = payload.get("result") or {}
        rows = next(
            (value for key, value in result.items()
             if key != "last" and isinstance(value, list)),
            None,
        )
        if not rows:
            raise ValueError("kraken ohlc empty")
        # Kraken: [time, open, high, low, close, vwap, volume, count]
        # -> Coinbase shape [time, low, high, open, close, volume]
        mapped = [
            [int(row[0]), float(row[3]), float(row[2]),
             float(row[1]), float(row[4]), float(row[6])]
            for row in rows if isinstance(row, list) and len(row) >= 7
        ]
        return sorted(mapped, key=lambda row: int(row[0]))

    def _fresh_hourly(
        self, client: Any, product: str, asset: str, now_s: float,
    ) -> tuple[list[list[float]], str]:
        """Coinbase hourly closes, failing over to Kraken when thin/stale.

        The realized-vol pipeline dies without hourly history; Coinbase is
        the primary (byte-identical behavior when healthy -- Kraken is not
        even fetched), Kraken the failover under the SAME depth/freshness
        gates. Only when both are unusable does the state raise, and every
        crypto signal abstains for the cycle.
        """
        try:
            hourly = self._candle_rows(client, product, 3600)
            if len(hourly) >= 48 and now_s - int(hourly[-1][0]) <= 3 * 3600:
                return hourly, "coinbase"
        except Exception:
            pass
        try:
            hourly = self._kraken_hourly_rows(client, asset)
        except Exception:
            raise ValueError("insufficient hourly crypto history") from None
        if len(hourly) < 48:
            raise ValueError("insufficient hourly crypto history")
        if now_s - int(hourly[-1][0]) > 3 * 3600:
            raise ValueError("stale hourly crypto history")
        return hourly, "kraken"

    def state(self, asset: str) -> dict[str, Any]:
        if asset in self._cache:
            return self._cache[asset]
        product = _PRODUCTS[asset]
        client = self._client()
        close = getattr(client, "close", None)
        try:
            now_s = self.now_s()
            hourly, hourly_source = self._fresh_hourly(client, product, asset, now_s)
            hourly_at_s = int(hourly[-1][0])
            try:
                minute = self._candle_rows(client, product, 60)
                if minute and now_s - int(minute[-1][0]) > 10 * 60:
                    minute = []
            except Exception:
                minute = []
            minute_at_s = int(minute[-1][0]) if minute else None
            coinbase_spot = float((minute or hourly)[-1][4])
            # Under Kraken hourly failover with no fresh Coinbase minute data,
            # that value is a Kraken close -- honest telemetry reports no
            # Coinbase spot (and no cross-venue divergence) rather than a
            # mislabeled one. The internal spot median still uses the price.
            coinbase_spot_genuine = bool(minute) or hourly_source == "coinbase"
            book_bid = book_ask = bid_size = ask_size = None
            try:
                response = client.get(
                    f"https://api.exchange.coinbase.com/products/{product}/book",
                    params={"level": 1},
                )
                response.raise_for_status()
                book = response.json()
                book_bid, bid_size = map(float, book["bids"][0][:2])
                book_ask, ask_size = map(float, book["asks"][0][:2])
            except Exception:
                pass
            kraken_spot = None
            try:
                response = client.get(
                    "https://api.kraken.com/0/public/Ticker",
                    params={"pair": _KRAKEN_PAIRS[asset]},
                )
                response.raise_for_status()
                payload = response.json()
                if payload.get("error"):
                    raise ValueError("kraken ticker error")
                kraken_row = next(iter((payload.get("result") or {}).values()))
                kraken_spot = float(kraken_row["c"][0])
            except Exception:
                pass
            dvol = dvol_at = None
            try:
                end_ms = int(now_s * 1000)
                response = client.get(
                    "https://www.deribit.com/api/v2/public/get_volatility_index_data",
                    params={
                        "currency": asset,
                        "start_timestamp": end_ms - 72 * 3600 * 1000,
                        "end_timestamp": end_ms,
                        "resolution": "3600",
                    },
                )
                response.raise_for_status()
                points = sorted(
                    (response.json().get("result") or {}).get("data") or [],
                    key=lambda row: int(row[0]),
                )
                if points:
                    dvol_at = int(points[-1][0])
                    dvol = float(points[-1][4])
                    if end_ms - dvol_at > 6 * 3600 * 1000:
                        dvol = dvol_at = None
            except Exception:
                pass
        finally:
            if callable(close):
                close()
        spot_candidates = [coinbase_spot]
        if book_bid is not None and book_ask is not None:
            spot_candidates.append((book_bid + book_ask) / 2.0)
        if kraken_spot is not None:
            spot_candidates.append(kraken_spot)
        spot = statistics.median(spot_candidates)
        book_imbalance = microprice_basis_bps = None
        if (book_bid is not None and book_ask is not None and bid_size is not None
                and ask_size is not None and bid_size + ask_size > 0):
            book_imbalance = (bid_size - ask_size) / (bid_size + ask_size)
            microprice = (book_ask * bid_size + book_bid * ask_size) / (bid_size + ask_size)
            microprice_basis_bps = 10_000.0 * (microprice / spot - 1.0)
        venue_divergence = (
            10_000.0 * abs(coinbase_spot / kraken_spot - 1.0)
            if coinbase_spot_genuine and kraken_spot and kraken_spot > 0 else None
        )
        state = {
            "asset": asset,
            "spot": spot,
            "coinbase_spot": coinbase_spot if coinbase_spot_genuine else None,
            "kraken_spot": kraken_spot,
            "venue_divergence_bps": venue_divergence,
            "hourly_source": hourly_source,
            "hourly_closes": [float(row[4]) for row in hourly],
            "minute_closes": [float(row[4]) for row in minute],
            "minute_volumes": [float(row[5]) for row in minute],
            "book_imbalance": book_imbalance,
            "microprice_basis_bps": microprice_basis_bps,
            "dvol": dvol,
            "dvol_at_ms": dvol_at,
            "coinbase_hourly_at_s": hourly_at_s,
            "coinbase_minute_at_s": minute_at_s,
            "coinbase_hourly_age_s": max(0.0, now_s - hourly_at_s),
            "coinbase_minute_age_s": (
                max(0.0, now_s - minute_at_s) if minute_at_s is not None else None
            ),
        }
        self._cache[asset] = state
        return state

    def flat_spot_and_vol(self, asset: str) -> tuple[float, float]:
        state = self.state(asset)
        volatility = _annualized_vol(state["hourly_closes"][-169:], 24 * 365)
        if volatility is None:
            raise ValueError("insufficient hourly volatility history")
        return float(state["spot"]), volatility

    def ewma_spot_and_vol(self, asset: str) -> tuple[float, float]:
        state = self.state(asset)
        closes = [float(value) for value in state["hourly_closes"]]
        returns = [
            math.log(closes[index] / closes[index - 1])
            for index in range(1, len(closes)) if closes[index - 1] > 0
        ]
        if not returns:
            raise ValueError("no hourly returns")
        variance = returns[0] ** 2
        for value in returns[1:]:
            variance = 0.94 * variance + 0.06 * value * value
        return float(state["spot"]), math.sqrt(variance) * math.sqrt(24 * 365)


def _hours_to_close(market: MarketView) -> float:
    close = datetime.fromisoformat(market.close_time.replace("Z", "+00:00"))
    return max(0.05, (close - datetime.now(timezone.utc)).total_seconds() / 3600.0)


def _event_probability(
    terminal_prices: list[float], weights: list[float], market: MarketView,
    fallback_strike: float,
) -> tuple[float, float]:
    strike_type = str(market.raw.get("strike_type", "")).lower()
    floor = market.raw.get("floor_strike")
    cap = market.raw.get("cap_strike")
    success = 0.0
    total = sum(weights)
    for price, weight in zip(terminal_prices, weights):
        if strike_type in {"greater", "greater_or_equal"} and floor is not None:
            event = price >= float(floor)
        elif strike_type == "less" and cap is not None:
            event = price < float(cap)
        elif strike_type == "between" and floor is not None and cap is not None:
            event = float(floor) <= price < float(cap)
        else:
            event = price >= fallback_strike
        success += weight * int(event)
    probability = (success + 0.5) / (total + 1.0)
    effective_n = total * total / sum(weight * weight for weight in weights)
    return min(0.995, max(0.005, probability)), effective_n


def _nonoverlapping_horizon_returns(
    closes: list[float], horizon_steps: int,
) -> list[float]:
    returns = []
    end = len(closes) - 1
    step = max(1, int(horizon_steps))
    while end - step >= 0:
        start = end - step
        if closes[start] > 0 and closes[end] > 0:
            returns.append(math.log(closes[end] / closes[start]))
        end = start
    return list(reversed(returns))


class CryptoEmpiricalRegimeSignal:
    """Weighted historical-simulation challenger with indicator telemetry."""

    name = "crypto_empirical_regime"

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
        if asset not in self._cache:
            self._cache[asset] = self.fetch_state(asset)
        state = self._cache[asset]
        hours = self.hours_to_close(market)
        if hours < 0.75 and state.get("minute_closes"):
            closes = [float(value) for value in state["minute_closes"]]
            steps = max(1, round(hours * 60.0))
            resolution = "1m"
        else:
            closes = [float(value) for value in state["hourly_closes"]]
            steps = max(1, round(hours))
            resolution = "1h"
        returns = _nonoverlapping_horizon_returns(closes, steps)
        if len(returns) < 12:
            return None
        # Recency half-life is one third of the usable blocks.
        half_life = max(6.0, len(returns) / 3.0)
        weights = [
            math.exp(-math.log(2.0) * (len(returns) - 1 - index) / half_life)
            for index in range(len(returns))
        ]
        spot = float(state["spot"])
        terminal = [spot * math.exp(value) for value in returns]
        probability, effective_n = _event_probability(
            terminal, weights, market, float(parsed["strike"]),
        )
        standard_error = math.sqrt(probability * (1.0 - probability) / max(1.0, effective_n))
        divergence = float(state.get("venue_divergence_bps") or 0.0)
        uncertainty = min(0.35, max(0.08, standard_error, divergence / 10_000.0 * 5.0))
        indicators = _indicator_features(state)
        features = {
            **indicators,
            "challenger_only": True,
            "indicator_schema_version": 1,
            "spot": spot,
            "hours_to_close": hours,
            "return_resolution": resolution,
            "horizon_steps": steps,
            "return_samples": len(returns),
            "effective_samples": effective_n,
            "probability_model_uncertainty": uncertainty,
        }
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=probability,
            uncertainty=uncertainty,
            rationale=(
                f"{asset} empirical {resolution} blocks n={len(returns)} neff={effective_n:.1f} "
                f"spot={spot:.2f} h={hours:.2f}; challenger-only"
            ),
            features=features,
        )


def _scaled(value: Any, scale: float) -> float | None:
    if value is None:
        return None
    return math.tanh(float(value) / scale)


def _technical_score(indicators: dict[str, Any]) -> tuple[float, float, dict[str, float]]:
    """Bounded, auditable directional score and indicator coverage.

    Coefficients are fixed research priors, not fit on Dummy's outcome ledger.
    Missing inputs contribute zero and lower coverage rather than silently
    changing the scale of the score.
    """
    minute_mode = indicators.get("momentum_15m_bps") is not None
    if minute_mode:
        definitions = (
            ("momentum_5m", indicators.get("momentum_5m_bps"), 8.0, 0.12),
            ("momentum_15m", indicators.get("momentum_15m_bps"), 15.0, 0.18),
            ("momentum_60m", indicators.get("momentum_60m_bps"), 35.0, 0.18),
            ("macd_12_26", indicators.get("macd_12_26_bps"), 8.0, 0.15),
            ("rsi_14m", (
                None if indicators.get("rsi_14m") is None
                else float(indicators["rsi_14m"]) - 50.0
            ), 20.0, 0.10),
            ("top_book_imbalance", indicators.get("top_book_imbalance"), 1.0, 0.15),
            ("microprice_basis", indicators.get("microprice_basis_bps"), 2.0, 0.07),
            ("hourly_momentum_4h", indicators.get("hourly_momentum_4h_bps"), 80.0, 0.05),
        )
        resolution = 1.0
    else:
        definitions = (
            ("hourly_momentum_1h", indicators.get("hourly_momentum_1h_bps"), 40.0, 0.25),
            ("hourly_momentum_4h", indicators.get("hourly_momentum_4h_bps"), 80.0, 0.25),
            ("hourly_momentum_24h", indicators.get("hourly_momentum_24h_bps"), 200.0, 0.10),
            ("hourly_macd_12_26", indicators.get("hourly_macd_12_26_bps"), 40.0, 0.15),
            ("hourly_rsi_14h", (
                None if indicators.get("hourly_rsi_14h") is None
                else float(indicators["hourly_rsi_14h"]) - 50.0
            ), 20.0, 0.10),
            ("top_book_imbalance", indicators.get("top_book_imbalance"), 1.0, 0.10),
            ("microprice_basis", indicators.get("microprice_basis_bps"), 2.0, 0.05),
        )
        resolution = 0.0
    components: dict[str, float] = {}
    available_weight = 0.0
    score = 0.0
    for name, value, scale, weight in definitions:
        transformed = _scaled(value, scale)
        if transformed is None:
            continue
        contribution = weight * transformed
        components[name] = contribution
        score += contribution
        available_weight += weight
    volume_surge = indicators.get("volume_surge_15m")
    if volume_surge is not None:
        multiplier = 1.0 + 0.15 * math.tanh((float(volume_surge) - 1.0) / 0.75)
        score *= multiplier
        components["volume_confirmation_multiplier"] = multiplier
    components["minute_resolution"] = resolution
    return max(-1.0, min(1.0, score)), available_weight, components


class CryptoTechnicalCompositeSignal:
    """Bounded technical-indicator challenger; never fused automatically."""

    name = "crypto_technical_composite"

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
        if asset not in self._cache:
            self._cache[asset] = self.fetch_state(asset)
        state = self._cache[asset]
        indicators = _indicator_features(state)
        score, coverage, components = _technical_score(indicators)
        spot = float(state["spot"])
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
        # Technical inputs can move the distribution center by at most 0.45
        # horizon standard deviations. This prevents indicator saturation from
        # creating unjustified near-certain probabilities.
        expected_log_return = 0.45 * score * horizon_sigma

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
        divergence = float(state.get("venue_divergence_bps") or 0.0)
        uncertainty = min(
            0.40,
            max(
                0.14,
                crypto_probability_uncertainty(probability, horizon_sigma) + 0.04,
                (1.0 - coverage) * 0.20,
                divergence / 10_000.0 * 5.0,
            ),
        )
        features = {
            **indicators,
            "challenger_only": True,
            "indicator_schema_version": 1,
            "technical_model_version": 1,
            "technical_score": score,
            "technical_coverage": coverage,
            "technical_components": components,
            "expected_log_return": expected_log_return,
            "shift_in_horizon_sigma": 0.45 * score,
            "annual_vol_used": float(annual_vol),
            "horizon_log_return_sigma": horizon_sigma,
            "hours_to_close": hours,
            "spot": spot,
            "probability_model_uncertainty": uncertainty,
        }
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=probability,
            uncertainty=uncertainty,
            rationale=(
                f"{asset} bounded technical composite score={score:.3f} "
                f"coverage={coverage:.2f} shift={0.45 * score:.2f}sigma; challenger-only"
            ),
            features=features,
        )


class CryptoDvolSignal:
    """Deribit implied-volatility distribution challenger."""

    name = "crypto_dvol_implied"

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
        if asset not in self._cache:
            self._cache[asset] = self.fetch_state(asset)
        state = self._cache[asset]
        if state.get("dvol") is None:
            return None
        spot = float(state["spot"])
        annual_vol = float(state["dvol"]) / 100.0
        hours = self.hours_to_close(market)
        horizon_sigma = annual_vol * math.sqrt(hours / (24.0 * 365.0))
        if spot <= 0 or horizon_sigma <= 0:
            return None

        def p_above(strike: float) -> float:
            return _normal_cdf(math.log(spot / strike) / horizon_sigma) if strike > 0 else 1.0

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
        divergence = float(state.get("venue_divergence_bps") or 0.0)
        uncertainty = min(
            0.35,
            max(0.12, crypto_probability_uncertainty(probability, horizon_sigma) + 0.03,
                divergence / 10_000.0 * 5.0),
        )
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=probability,
            uncertainty=uncertainty,
            rationale=(
                f"{asset} Deribit DVOL={annual_vol:.1%} spot={spot:.2f} h={hours:.2f}; "
                "challenger-only"
            ),
            features={
                **_indicator_features(state),
                "challenger_only": True,
                "indicator_schema_version": 1,
                "spot": spot,
                "annual_implied_vol": annual_vol,
                "hours_to_close": hours,
                "horizon_log_return_sigma": horizon_sigma,
                "probability_model_uncertainty": uncertainty,
            },
        )
