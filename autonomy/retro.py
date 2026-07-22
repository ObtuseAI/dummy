"""Retro evidence engine: point-in-time replay against already-settled markets.

The evidence gate needs settled markets where our sources demonstrably beat
the market. Waiting for live shadow positions to settle accrues that evidence
at slot-turnover speed — days to weeks. But Kalshi keeps the full history:
every settled market, its result, and its price candlesticks. And our signal
inputs are reconstructible point-in-time: Coinbase serves historical candles,
Open-Meteo serves the forecast *as it was issued* for any past day.

So instead of waiting for the future, we grade the recent past:

  for each market that settled in the lookback window:
    1. market prior  = the book's own mid from the last candle at or before
                       the decision timestamp (what the market believed THEN)
    2. model signal  = the same signal class the live loop runs, fed only
                       data that existed at the decision timestamp
    3. truth         = the settlement result

Signals are written to the ledger with mode='retro' and historical
timestamps; settlements are recorded exactly as live reconciliation would.
The backtester and canary gate then score them like any other evidence.

Honesty rules (fail-closed):
  - No candle at/before decision time -> the market is skipped entirely
    (without a contemporaneous market prior there is no baseline to beat).
  - Crypto spot/vol come only from candles fully closed before decision time.
  - Weather forecasts come from the historical-forecast API (the day's own
    model runs), never from the archive of actuals. Note: bias/sigma
    calibration is the current artifact, whose fit window overlaps the
    replay window — disclosed in the report as weather_calibration_overlap.
  - A market already settled in the ledger is never rewritten. New challenger
    source rows may be appended at the original decision timestamp so a new
    model can be graded against the existing immutable settlement.
  - Markets are only written when BOTH the market prior and a model signal
    exist, so retro evidence never pads the settled count with markets the
    model didn't actually cover.
"""

from __future__ import annotations

import dataclasses
import json
import math
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from autonomy.ledger import AutonomyLedger
from autonomy.ontology import MarketView, Signal
from autonomy.reconciler import default_fetch_settled_page
from autonomy.scanner import to_market_view
from autonomy.signals.crypto_indicators import (
    CryptoDvolSignal,
    CryptoEmpiricalRegimeSignal,
    CryptoTechnicalCompositeSignal,
)
from autonomy.signals.crypto_spot import (
    _PRODUCTS,
    CryptoSpotVolSignal,
    parse_crypto_ticker,
)
from autonomy.signals.market_prior import MarketPriorSignal
from autonomy.signals.weather_openmeteo import CITY_TABLE

CRYPTO_SERIES = ["KXBTCD", "KXETHD", "KXBTC", "KXETH"]
WEATHER_SERIES = [
    "KXHIGHNY",
    "KXHIGHCHI",
    "KXHIGHMIA",
    "KXHIGHAUS",
    "KXHIGHDEN",
    "KXHIGHPHIL",
    "KXHIGHLAX",
    "KXHIGHTSEA",
]

# Decision timestamps: when the live loop would realistically have acted.
CRYPTO_DECISION_LEAD_S = 45 * 60  # 45 minutes before close
WEATHER_DECISION_HOUR_UTC = 14  # 14:00Z on the event day (morning US)

_KALSHI_BASE_ENV = ("KALSHI_API_BASE", "https://api.elections.kalshi.com")


def _public_base() -> str:
    base = os.environ.get(*_KALSHI_BASE_ENV).rstrip("/")
    version = os.environ.get("KALSHI_API_VERSION", "trade-api/v2").strip("/")
    return f"{base}/{version}"


# ---------------------------------------------------------------------------
# Default fetchers (all public, no auth)
# ---------------------------------------------------------------------------


def default_fetch_candles(
    series: str, ticker: str, start_ts: int, end_ts: int, period_interval: int = 60
) -> list[dict[str, Any]]:
    import httpx

    response = httpx.get(
        f"{_public_base()}/series/{series}/markets/{ticker}/candlesticks",
        params={
            "start_ts": start_ts,
            "end_ts": end_ts,
            "period_interval": period_interval,
        },
        timeout=20,
    )
    response.raise_for_status()
    candles = response.json().get("candlesticks", [])
    return candles if isinstance(candles, list) else []


def default_fetch_coinbase_candles(
    product: str, start_iso: str, end_iso: str, granularity: int = 3600
) -> list[list[float]]:
    import httpx

    response = httpx.get(
        f"https://api.exchange.coinbase.com/products/{product}/candles",
        params={"granularity": granularity, "start": start_iso, "end": end_iso},
        timeout=20,
    )
    response.raise_for_status()
    rows = response.json()
    return rows if isinstance(rows, list) else []


# ---------------------------------------------------------------------------
# Point-in-time reconstruction helpers
# ---------------------------------------------------------------------------


def _dollars_to_cents(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(round(float(value) * 100))
    except Exception:
        return None


def candle_quote_at(
    candles: list[dict[str, Any]], decision_ts: int
) -> dict[str, Any] | None:
    """Last candle whose period ended at or before the decision timestamp."""
    best: dict[str, Any] | None = None
    for candle in candles:
        try:
            end = int(candle.get("end_period_ts", 0))
        except Exception:
            continue
        if end <= decision_ts and (best is None or end > int(best["end_period_ts"])):
            best = candle
    if best is None:
        return None
    bid = _dollars_to_cents((best.get("yes_bid") or {}).get("close_dollars"))
    ask = _dollars_to_cents((best.get("yes_ask") or {}).get("close_dollars"))
    if bid is None or ask is None or ask <= 0:
        return None
    try:
        volume = int(float(best.get("volume_fp") or 0))
    except Exception:
        volume = 0
    return {
        "yes_bid": bid,
        "yes_ask": ask,
        "volume": volume,
        "end_period_ts": int(best["end_period_ts"]),
    }


class HourlyPriceSeries:
    """Continuous hourly close series for one product, sliceable at any ts.

    Fetched once per asset for the whole replay window; spot/vol at a decision
    time use only candles that fully closed before it — no lookahead.
    """

    def __init__(
        self,
        product: str,
        start_ts: int,
        end_ts: int,
        fetch: Callable[..., list[list[float]]] | None = None,
    ) -> None:
        fetch = fetch or default_fetch_coinbase_candles
        self.closes: list[tuple[int, float]] = []  # (candle_start_ts, close) ascending
        seen: set[int] = set()
        chunk = 250 * 3600  # stay under the 300-candle response cap
        cursor = start_ts
        while cursor < end_ts:
            upper = min(cursor + chunk, end_ts)
            rows = fetch(
                product,
                datetime.fromtimestamp(cursor, tz=timezone.utc).isoformat(),
                datetime.fromtimestamp(upper, tz=timezone.utc).isoformat(),
                3600,
            )
            for row in rows:
                ts = int(row[0])
                if ts not in seen:
                    seen.add(ts)
                    self.closes.append((ts, float(row[4])))
            cursor = upper
        self.closes.sort()

    def spot_and_vol_at(
        self, ts: int, window_hours: int = 168
    ) -> tuple[float, float] | None:
        """(spot, annualized_vol) using candles fully closed before ts.

        Mirrors the live signal's math: hourly log-return stdev annualized.
        """
        closed = [(t, c) for t, c in self.closes if t + 3600 <= ts]
        if len(closed) < 24:
            return None
        recent = closed[-window_hours:]
        closes = [c for _t, c in recent]
        spot = closes[-1]
        rets = [
            math.log(closes[i] / closes[i - 1])
            for i in range(1, len(closes))
            if closes[i - 1] > 0
        ]
        if not rets:
            return None
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / max(1, len(rets) - 1)
        annualized = math.sqrt(var) * math.sqrt(24 * 365)
        if spot <= 0 or annualized <= 0:
            return None
        return spot, annualized

    def closes_at(self, ts: int, window_hours: int = 350) -> list[float]:
        """Ascending closes fully available before ``ts``."""
        closed = [c for t, c in self.closes if t + 3600 <= ts]
        return closed[-window_hours:]


class _RetroCryptoSignal(CryptoSpotVolSignal):
    """Live crypto signal with time frozen at the historical decision point."""

    def __init__(self, spot: float, annual_vol: float, hours_to_close: float) -> None:
        super().__init__(fetch_spot_and_vol=lambda asset: (spot, annual_vol))
        self._frozen_hours = max(0.05, hours_to_close)

    def _hours_to_close(self, market: MarketView) -> float:
        return self._frozen_hours


def build_weather_history_fetcher(
    lookback_days: int,
    today: datetime | None = None,
    fetch_history: Callable[..., dict[str, list]] | None = None,
) -> Callable[[float, float, str, str], list[float]]:
    """Prefetch per-city historical day-0 forecasts; serve them per date.

    Returns a drop-in fetch_daily_temps for OpenMeteoWeatherSignal whose
    answers are the per-model forecasts as issued for each past day.
    """
    from autonomy.weather_calibration import default_fetch_historical_forecast

    fetch_history = fetch_history or default_fetch_historical_forecast
    now = today or datetime.now(timezone.utc)
    start = (now - timedelta(days=lookback_days + 1)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")

    by_city: dict[str, dict[str, list[float]]] = {}
    for code, city in CITY_TABLE.items():
        try:
            daily = fetch_history(city["lat"], city["lon"], start, end, "HIGH")
        except Exception:
            continue
        times = daily.get("time", [])
        columns = [
            v
            for k, v in daily.items()
            if k.startswith("temperature_2m_max") and isinstance(v, list)
        ]
        per_date: dict[str, list[float]] = {}
        for i, date in enumerate(times):
            vals = [col[i] for col in columns if i < len(col) and col[i] is not None]
            if vals:
                per_date[date] = [float(v) for v in vals]
        by_city[code] = per_date

    coord_to_code = {
        (round(c["lat"], 4), round(c["lon"], 4)): code for code, c in CITY_TABLE.items()
    }

    def fetcher(lat: float, lon: float, date_iso: str, kind: str) -> list[float]:
        code = coord_to_code.get((round(lat, 4), round(lon, 4)))
        if code is None or kind != "HIGH":
            return []
        return by_city.get(code, {}).get(date_iso, [])

    return fetcher


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------


class RetroEvidenceEngine:
    def __init__(
        self,
        ledger: AutonomyLedger,
        fetch_settled_page: Callable[..., dict[str, Any]] | None = None,
        fetch_candles: Callable[..., list[dict[str, Any]]] | None = None,
        fetch_coinbase: Callable[..., list[list[float]]] | None = None,
        fetch_deribit: Callable[[str, int, int], dict[str, Any]] | None = None,
        fetch_weather_history: Callable[..., dict[str, list]] | None = None,
        sleep_s: float = 0.06,
        now: datetime | None = None,
    ) -> None:
        self.ledger = ledger
        self.fetch_settled_page = fetch_settled_page or default_fetch_settled_page
        self.fetch_candles = fetch_candles or default_fetch_candles
        self.fetch_coinbase = fetch_coinbase or default_fetch_coinbase_candles
        if fetch_deribit is None:
            from autonomy.statistics_intake import default_fetch_deribit_dvol

            fetch_deribit = default_fetch_deribit_dvol
        self.fetch_deribit = fetch_deribit
        self.fetch_weather_history = fetch_weather_history
        self.sleep_s = sleep_s
        self.now = now or datetime.now(timezone.utc)
        # (market_mid_probability, result) pairs for the debias curve — every
        # settled market with a contemporaneous quote contributes, model or not.
        self.debias_samples: list[tuple[float, int]] = []

    # -- listing ----------------------------------------------------------

    def settled_markets(
        self, series: str, lookback_days: float, max_markets: int
    ) -> list[dict[str, Any]]:
        min_close_ts = int(self.now.timestamp() - lookback_days * 86400)
        out: list[dict[str, Any]] = []
        cursor: str | None = None
        while len(out) < max_markets:
            try:
                page = self.fetch_settled_page(series, min_close_ts, cursor)
            except Exception:
                break
            markets = page.get("markets", [])
            for market in markets:
                if str(market.get("result", "")).lower() in ("yes", "no"):
                    out.append(market)
                    if len(out) >= max_markets:
                        break
            cursor = page.get("cursor") or None
            if not cursor or not markets:
                break
        return out

    # -- per-market replay -------------------------------------------------

    def _market_prior_view(
        self, raw: dict[str, Any], series: str, decision_ts: int
    ) -> MarketView | None:
        ticker = str(raw.get("ticker", ""))
        try:
            candles = self.fetch_candles(
                series, ticker, decision_ts - 48 * 3600, decision_ts, 60
            )
        except Exception:
            return None
        quote = candle_quote_at(candles, decision_ts)
        if quote is None:
            # Sparse book: retry at minute resolution over a tight window.
            try:
                candles = self.fetch_candles(
                    series, ticker, decision_ts - 6 * 3600, decision_ts, 1
                )
            except Exception:
                return None
            quote = candle_quote_at(candles, decision_ts)
        if quote is None:
            return None
        view = to_market_view(raw)
        return dataclasses.replace(
            view,
            yes_bid=quote["yes_bid"],
            yes_ask=quote["yes_ask"],
            volume=quote["volume"],
        )

    def _write_market(
        self, view: MarketView, model_signal: Signal, decision_ts: int, result_yes: bool
    ) -> bool:
        prior = MarketPriorSignal().generate(view)
        if prior is None:
            return False
        decision_iso = datetime.fromtimestamp(decision_ts, tz=timezone.utc).isoformat()
        replay_signals = [
            dataclasses.replace(signal, created_at=decision_iso)
            for signal in (prior, model_signal)
        ]
        if not all(
            self.ledger.record_signals(replay_signals, mode="retro", all_or_none=True)
        ):
            return False
        self.ledger.record_settlement(view.ticker, result_yes)
        mid_prob = min(
            0.995, max(0.005, ((view.yes_bid or 0) + (view.yes_ask or 0)) / 200.0)
        )
        self.debias_samples.append((mid_prob, 1 if result_yes else 0))
        return True

    def _collect_debias_only(self, view: MarketView, result_yes: bool) -> None:
        if view.yes_bid is None or view.yes_ask is None:
            return
        mid_prob = min(0.995, max(0.005, (view.yes_bid + view.yes_ask) / 200.0))
        self.debias_samples.append((mid_prob, 1 if result_yes else 0))

    # -- verticals ----------------------------------------------------------

    def replay_crypto(
        self,
        lookback_days: float = 10.0,
        max_per_series: int = 250,
        series_list: list[str] | None = None,
    ) -> dict[str, Any]:
        stats = {
            "written": 0,
            "skipped_no_quote": 0,
            "skipped_no_model": 0,
            "skipped_already_settled": 0,
            "listed": 0,
        }
        already = self._already_settled()
        window_start = int(self.now.timestamp() - (lookback_days + 9) * 86400)
        window_end = int(self.now.timestamp())
        price_series: dict[str, HourlyPriceSeries] = {}

        for series in series_list or CRYPTO_SERIES:
            for raw in self.settled_markets(series, lookback_days, max_per_series):
                stats["listed"] += 1
                ticker = str(raw.get("ticker", ""))
                if ticker in already:
                    stats["skipped_already_settled"] += 1
                    continue
                parsed = parse_crypto_ticker(ticker)
                close_ts = _close_ts(raw)
                if parsed is None or close_ts is None:
                    stats["skipped_no_model"] += 1
                    continue
                decision_ts = close_ts - CRYPTO_DECISION_LEAD_S
                asset = parsed["asset"]
                if asset not in price_series:
                    product = _PRODUCTS[asset]
                    price_series[asset] = HourlyPriceSeries(
                        product, window_start, window_end, fetch=self.fetch_coinbase
                    )
                spot_vol = price_series[asset].spot_and_vol_at(decision_ts)
                if spot_vol is None:
                    stats["skipped_no_model"] += 1
                    continue

                view = self._market_prior_view(raw, series, decision_ts)
                if self.sleep_s:
                    time.sleep(self.sleep_s)
                if view is None:
                    stats["skipped_no_quote"] += 1
                    continue
                hours = (close_ts - decision_ts) / 3600.0
                signal = _RetroCryptoSignal(spot_vol[0], spot_vol[1], hours).generate(
                    view
                )
                if signal is None:
                    self._collect_debias_only(
                        view, str(raw.get("result")).lower() == "yes"
                    )
                    stats["skipped_no_model"] += 1
                    continue
                result_yes = str(raw.get("result")).lower() == "yes"
                if self._write_market(view, signal, decision_ts, result_yes):
                    already.add(ticker)
                    stats["written"] += 1
        return stats

    def replay_crypto_challengers(
        self,
        lookback_days: float = 10.0,
        max_per_series: int = 250,
        series_list: list[str] | None = None,
    ) -> dict[str, Any]:
        """Append point-in-time empirical challenger signals to settled truth."""
        stats = {
            "source": "crypto_empirical_regime",
            "written": 0,
            "listed": 0,
            "skipped_no_settlement": 0,
            "skipped_no_model": 0,
            "skipped_existing_signal": 0,
        }
        window_start = int(self.now.timestamp() - (lookback_days + 16) * 86400)
        window_end = int(self.now.timestamp())
        price_series: dict[str, HourlyPriceSeries] = {}
        frozen_hours = CRYPTO_DECISION_LEAD_S / 3600.0

        for series in series_list or CRYPTO_SERIES:
            for raw in self.settled_markets(series, lookback_days, max_per_series):
                stats["listed"] += 1
                ticker = str(raw.get("ticker", ""))
                if self.ledger.settlement_result(ticker) is None:
                    stats["skipped_no_settlement"] += 1
                    continue
                parsed = parse_crypto_ticker(ticker)
                close_ts = _close_ts(raw)
                if parsed is None or close_ts is None:
                    stats["skipped_no_model"] += 1
                    continue
                decision_ts = close_ts - CRYPTO_DECISION_LEAD_S
                decision_iso = datetime.fromtimestamp(
                    decision_ts,
                    tz=timezone.utc,
                ).isoformat()
                exists = self.ledger._conn.execute(  # noqa: SLF001
                    "SELECT 1 FROM signal_history WHERE source='crypto_empirical_regime'"
                    " AND market_ticker=? AND mode='retro' LIMIT 1",
                    (ticker,),
                ).fetchone()
                if exists:
                    stats["skipped_existing_signal"] += 1
                    continue
                asset = str(parsed["asset"])
                if asset not in price_series:
                    price_series[asset] = HourlyPriceSeries(
                        _PRODUCTS[asset],
                        window_start,
                        window_end,
                        fetch=self.fetch_coinbase,
                    )
                closes = price_series[asset].closes_at(decision_ts)
                if len(closes) < 48:
                    stats["skipped_no_model"] += 1
                    continue
                state = {
                    "asset": asset,
                    "spot": closes[-1],
                    "coinbase_spot": closes[-1],
                    "kraken_spot": None,
                    "venue_divergence_bps": None,
                    "hourly_closes": closes,
                    "minute_closes": [],
                    "minute_volumes": [],
                    "book_imbalance": None,
                    "microprice_basis_bps": None,
                    "dvol": None,
                    "dvol_at_ms": None,
                }
                signal = CryptoEmpiricalRegimeSignal(
                    fetch_state=lambda _asset, payload=state: payload,
                    hours_to_close=lambda _market: frozen_hours,
                ).generate(to_market_view(raw))
                if signal is None:
                    stats["skipped_no_model"] += 1
                    continue
                signal = dataclasses.replace(
                    signal,
                    created_at=decision_iso,
                    features={**signal.features, "retro_point_in_time": True},
                )
                if self.ledger.record_signal(signal, mode="retro"):
                    stats["written"] += 1
                else:
                    stats["skipped_existing_signal"] += 1
        return stats

    def replay_crypto_dvol_challenger(
        self,
        lookback_days: float = 10.0,
        max_per_series: int = 250,
        series_list: list[str] | None = None,
    ) -> dict[str, Any]:
        """Append point-in-time Deribit DVOL challenger signals."""
        stats = {
            "source": "crypto_dvol_implied",
            "written": 0,
            "listed": 0,
            "skipped_no_settlement": 0,
            "skipped_no_model": 0,
            "skipped_existing_signal": 0,
        }
        window_start = int(self.now.timestamp() - (lookback_days + 16) * 86400)
        window_end = int(self.now.timestamp())
        frozen_hours = CRYPTO_DECISION_LEAD_S / 3600.0
        price_series: dict[str, HourlyPriceSeries] = {}
        dvol_series: dict[str, list[tuple[int, float]]] = {}

        for series in series_list or CRYPTO_SERIES:
            for raw in self.settled_markets(series, lookback_days, max_per_series):
                stats["listed"] += 1
                ticker = str(raw.get("ticker", ""))
                if self.ledger.settlement_result(ticker) is None:
                    stats["skipped_no_settlement"] += 1
                    continue
                parsed = parse_crypto_ticker(ticker)
                close_ts = _close_ts(raw)
                if parsed is None or close_ts is None:
                    stats["skipped_no_model"] += 1
                    continue
                exists = self.ledger._conn.execute(  # noqa: SLF001
                    "SELECT 1 FROM signal_history WHERE source='crypto_dvol_implied'"
                    " AND market_ticker=? AND mode='retro' LIMIT 1",
                    (ticker,),
                ).fetchone()
                if exists:
                    stats["skipped_existing_signal"] += 1
                    continue
                decision_ts = close_ts - CRYPTO_DECISION_LEAD_S
                decision_iso = datetime.fromtimestamp(
                    decision_ts,
                    tz=timezone.utc,
                ).isoformat()
                asset = str(parsed["asset"])
                if asset not in price_series:
                    price_series[asset] = HourlyPriceSeries(
                        _PRODUCTS[asset],
                        window_start,
                        window_end,
                        fetch=self.fetch_coinbase,
                    )
                if asset not in dvol_series:
                    try:
                        payload = self.fetch_deribit(
                            asset,
                            window_start * 1000,
                            window_end * 1000,
                        )
                        dvol_series[asset] = sorted(
                            [
                                (int(row[0] // 1000), float(row[4]))
                                for row in (
                                    (payload.get("result") or {}).get("data") or []
                                )
                                if isinstance(row, list) and len(row) >= 5
                            ]
                        )
                    except Exception:
                        dvol_series[asset] = []
                closes = price_series[asset].closes_at(decision_ts)
                # A one-hour DVOL candle is knowable only after its period.
                eligible_dvol = [
                    value
                    for timestamp, value in dvol_series[asset]
                    if timestamp + 3600 <= decision_ts
                ]
                if len(closes) < 48 or not eligible_dvol:
                    stats["skipped_no_model"] += 1
                    continue
                state = {
                    "asset": asset,
                    "spot": closes[-1],
                    "coinbase_spot": closes[-1],
                    "kraken_spot": None,
                    "venue_divergence_bps": None,
                    "hourly_closes": closes,
                    "minute_closes": [],
                    "minute_volumes": [],
                    "book_imbalance": None,
                    "microprice_basis_bps": None,
                    "dvol": eligible_dvol[-1],
                    "dvol_at_ms": None,
                }
                signal = CryptoDvolSignal(
                    fetch_state=lambda _asset, payload=state: payload,
                    hours_to_close=lambda _market: frozen_hours,
                ).generate(to_market_view(raw))
                if signal is None:
                    stats["skipped_no_model"] += 1
                    continue
                signal = dataclasses.replace(
                    signal,
                    created_at=decision_iso,
                    features={**signal.features, "retro_point_in_time": True},
                )
                if self.ledger.record_signal(signal, mode="retro"):
                    stats["written"] += 1
                else:
                    stats["skipped_existing_signal"] += 1
        return stats

    def replay_crypto_technical_challenger(
        self,
        lookback_days: float = 10.0,
        max_per_series: int = 250,
        series_list: list[str] | None = None,
    ) -> dict[str, Any]:
        """Append point-in-time hourly technical-composite signals."""
        stats = {
            "source": "crypto_technical_composite",
            "written": 0,
            "listed": 0,
            "skipped_no_settlement": 0,
            "skipped_no_model": 0,
            "skipped_existing_signal": 0,
        }
        window_start = int(self.now.timestamp() - (lookback_days + 16) * 86400)
        window_end = int(self.now.timestamp())
        frozen_hours = CRYPTO_DECISION_LEAD_S / 3600.0
        price_series: dict[str, HourlyPriceSeries] = {}

        for series in series_list or CRYPTO_SERIES:
            for raw in self.settled_markets(series, lookback_days, max_per_series):
                stats["listed"] += 1
                ticker = str(raw.get("ticker", ""))
                if self.ledger.settlement_result(ticker) is None:
                    stats["skipped_no_settlement"] += 1
                    continue
                parsed = parse_crypto_ticker(ticker)
                close_ts = _close_ts(raw)
                if parsed is None or close_ts is None:
                    stats["skipped_no_model"] += 1
                    continue
                exists = self.ledger._conn.execute(  # noqa: SLF001
                    "SELECT 1 FROM signal_history WHERE source='crypto_technical_composite'"
                    " AND market_ticker=? AND mode='retro' LIMIT 1",
                    (ticker,),
                ).fetchone()
                if exists:
                    stats["skipped_existing_signal"] += 1
                    continue
                decision_ts = close_ts - CRYPTO_DECISION_LEAD_S
                decision_iso = datetime.fromtimestamp(
                    decision_ts,
                    tz=timezone.utc,
                ).isoformat()
                asset = str(parsed["asset"])
                if asset not in price_series:
                    price_series[asset] = HourlyPriceSeries(
                        _PRODUCTS[asset],
                        window_start,
                        window_end,
                        fetch=self.fetch_coinbase,
                    )
                closes = price_series[asset].closes_at(decision_ts)
                if len(closes) < 48:
                    stats["skipped_no_model"] += 1
                    continue
                state = {
                    "asset": asset,
                    "spot": closes[-1],
                    "coinbase_spot": closes[-1],
                    "kraken_spot": None,
                    "venue_divergence_bps": None,
                    "hourly_closes": closes,
                    "minute_closes": [],
                    "minute_volumes": [],
                    "book_imbalance": None,
                    "microprice_basis_bps": None,
                    "dvol": None,
                    "dvol_at_ms": None,
                }
                signal = CryptoTechnicalCompositeSignal(
                    fetch_state=lambda _asset, payload=state: payload,
                    hours_to_close=lambda _market: frozen_hours,
                ).generate(to_market_view(raw))
                if signal is None:
                    stats["skipped_no_model"] += 1
                    continue
                signal = dataclasses.replace(
                    signal,
                    created_at=decision_iso,
                    features={**signal.features, "retro_point_in_time": True},
                )
                if self.ledger.record_signal(signal, mode="retro"):
                    stats["written"] += 1
                else:
                    stats["skipped_existing_signal"] += 1
        return stats

    def replay_weather(
        self,
        lookback_days: float = 30.0,
        max_per_series: int = 60,
        series_list: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "status": "RETIRED_DATA_ONLY",
            "written": 0,
            "skipped_no_quote": 0,
            "skipped_no_model": 0,
            "skipped_already_settled": 0,
            "listed": 0,
            "reason": "weather may supply contextual data but is not a prediction target",
        }

    # -- orchestration -------------------------------------------------------

    def _already_settled(self) -> set[str]:
        rows = self.ledger._conn.execute("SELECT market_ticker FROM settlements")  # noqa: SLF001
        return {r[0] for r in rows}

    def run(
        self,
        crypto_days: float = 10.0,
        weather_days: float = 30.0,
        crypto_max_per_series: int = 250,
        weather_max_per_series: int = 60,
        curve_path: Path | None = None,
    ) -> dict[str, Any]:
        crypto = self.replay_crypto(crypto_days, crypto_max_per_series)
        crypto_challengers = self.replay_crypto_challengers(
            crypto_days,
            crypto_max_per_series,
        )
        crypto_dvol_challenger = self.replay_crypto_dvol_challenger(
            crypto_days,
            crypto_max_per_series,
        )
        crypto_technical_challenger = self.replay_crypto_technical_challenger(
            crypto_days,
            crypto_max_per_series,
        )
        weather = self.replay_weather(weather_days, weather_max_per_series)

        from autonomy.signals.market_debias import (
            LIVE_EVIDENCE_MODE,
            fit_curve,
            ledger_samples,
            write_curve,
        )

        # Retro candles remain a research diagnostic; only receipt-bounded
        # live observations may train the operational debias challenger.
        verified_live_samples = ledger_samples(self.ledger)
        curve = fit_curve(verified_live_samples)
        curve_path = write_curve(curve, curve_path)

        report = {
            "report_name": "RETRO_EVIDENCE_BACKFILL",
            "crypto": crypto,
            "crypto_challengers": crypto_challengers,
            "crypto_dvol_challenger": crypto_dvol_challenger,
            "crypto_technical_challenger": crypto_technical_challenger,
            "weather": weather,
            "written_total": (
                crypto["written"]
                + crypto_challengers["written"]
                + crypto_dvol_challenger["written"]
                + crypto_technical_challenger["written"]
                + weather["written"]
            ),
            "debias_samples": len(verified_live_samples),
            "debias_samples_from_candles": 0,
            "debias_retro_candle_samples_quarantined": len(self.debias_samples),
            "debias_evidence_mode": LIVE_EVIDENCE_MODE,
            "debias_prediction_authority": False,
            "debias_curve_path": str(curve_path),
            "flags": {"weather_prediction_backfill_retired": True},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        root = Path(os.environ.get("DUMMY_EVIDENCE_ROOT", "artifacts/dummy")) / "retro"
        root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        (root / f"RETRO_EVIDENCE_{stamp}.json").write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
        )
        return report


def _close_ts(raw: dict[str, Any]) -> int | None:
    try:
        close = datetime.fromisoformat(
            str(raw.get("close_time", "")).replace("Z", "+00:00")
        )
        return int(close.timestamp())
    except Exception:
        return None
