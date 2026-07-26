"""Provider-neutral public market-data adapters.

Only unauthenticated, read-only endpoints are implemented. TradingView,
browser automation, private exchange methods, and arbitrary URLs are absent by
construction.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol
from urllib.parse import urlsplit

from autonomy.market_observer.contracts import (
    ALLOWED_ASSETS,
    ALLOWED_TIMEFRAMES,
    CandleBar,
    ObservationStatus,
    SourceProvenance,
    is_tradingview_url,
    sha256_json,
)

COINBASE_BASE_URL = "https://api.exchange.coinbase.com"
COINBASE_PRODUCTS = {"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD"}
TIMEFRAME_SECONDS = {
    "15m": 15 * 60,
    "1h": 60 * 60,
    "4h": 4 * 60 * 60,
    "1d": 24 * 60 * 60,
    "1w": 7 * 24 * 60 * 60,
}
SOURCE_INTERVAL_SECONDS = {
    "15m": 15 * 60,
    "1h": 60 * 60,
    "4h": 60 * 60,
    "1d": 24 * 60 * 60,
    "1w": 24 * 60 * 60,
}
MAX_SOURCE_BARS = 300
APPROVED_PUBLIC_PROVIDER_HOSTS = frozenset({"api.exchange.coinbase.com"})


class ProviderUnavailable(RuntimeError):
    pass


class ProviderSchemaDrift(RuntimeError):
    pass


class ProviderConfigurationError(RuntimeError):
    pass


def _validated_provider_base_url(value: str) -> str:
    candidate = str(value).rstrip("/")
    if is_tradingview_url(candidate):
        raise ProviderConfigurationError("TradingView domains are prohibited")
    parsed = urlsplit(candidate)
    host = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or host not in APPROVED_PUBLIC_PROVIDER_HOSTS
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ProviderConfigurationError("provider base URL is not allowlisted")
    return f"https://{host}"


@dataclass(frozen=True, slots=True)
class ProviderBatch:
    candles: tuple[CandleBar, ...]
    provenance: SourceProvenance
    requested_at_s: float
    received_at_s: float
    raw_payload: dict[str, Any]
    status: ObservationStatus
    warnings: tuple[str, ...] = ()


class CandleProvider(Protocol):
    def fetch_candles(
        self,
        asset: str,
        timeframe: str,
        *,
        limit: int,
    ) -> ProviderBatch: ...


def _iso_utc(timestamp_s: int) -> str:
    return datetime.fromtimestamp(timestamp_s, tz=timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def _bucket_start(open_time_s: int, target_interval_s: int) -> int:
    if target_interval_s == TIMEFRAME_SECONDS["1w"]:
        # Unix epoch was Thursday. Shift by three days so weekly candles are
        # aligned Monday 00:00 UTC.
        shift = 3 * 24 * 60 * 60
        return ((open_time_s + shift) // target_interval_s) * target_interval_s - shift
    return (open_time_s // target_interval_s) * target_interval_s


def _aggregate_closed_bars(
    bars: list[CandleBar],
    *,
    timeframe: str,
    received_at_s: float,
) -> tuple[list[CandleBar], list[str]]:
    target_interval_s = TIMEFRAME_SECONDS[timeframe]
    if not bars:
        return [], []
    if bars[0].interval_s == target_interval_s:
        return bars, []
    source_interval_s = bars[0].interval_s
    if target_interval_s % source_interval_s:
        raise ProviderSchemaDrift("target interval is not divisible by source interval")
    required = target_interval_s // source_interval_s
    groups: dict[int, list[CandleBar]] = {}
    for bar in bars:
        groups.setdefault(
            _bucket_start(bar.open_time_s, target_interval_s), []
        ).append(bar)
    output: list[CandleBar] = []
    dropped = 0
    for bucket, group in sorted(groups.items()):
        group.sort(key=lambda item: item.open_time_s)
        expected_times = [
            bucket + index * source_interval_s for index in range(required)
        ]
        if (
            len(group) != required
            or [bar.open_time_s for bar in group] != expected_times
            or bucket + target_interval_s > received_at_s
        ):
            dropped += 1
            continue
        raw = [bar.to_dict() for bar in group]
        observed_times = [
            bar.provider_observed_at_s
            for bar in group
            if bar.provider_observed_at_s is not None
        ]
        output.append(
            CandleBar(
                asset=group[0].asset,
                venue=group[0].venue,
                timeframe=timeframe,
                interval_s=target_interval_s,
                open_time_s=bucket,
                close_time_s=bucket + target_interval_s,
                received_at_s=received_at_s,
                open=group[0].open,
                high=max(bar.high for bar in group),
                low=min(bar.low for bar in group),
                close=group[-1].close,
                volume=sum(bar.volume for bar in group),
                source=f"{group[0].source}:local_aggregate",
                raw_sha256=sha256_json(raw),
                provider_observed_at_s=(
                    max(observed_times)
                    if len(observed_times) == len(group)
                    else None
                ),
            )
        )
    warnings = [f"dropped_{dropped}_incomplete_aggregate_buckets"] if dropped else []
    return output, warnings


class CoinbasePublicCandleProvider:
    """Coinbase Exchange public-candle adapter with deterministic aggregation."""

    ADAPTER_VERSION = "coinbase-public-candles-v1"

    def __init__(
        self,
        client_factory: Callable[[], Any] | None = None,
        clock: Callable[[], float] | None = None,
        base_url: str = COINBASE_BASE_URL,
    ) -> None:
        self.client_factory = client_factory
        self.clock = clock or time.time
        self.base_url = _validated_provider_base_url(base_url)

    def _client(self) -> Any:
        if self.client_factory is not None:
            return self.client_factory()
        import httpx

        return httpx.Client(
            timeout=20.0,
            follow_redirects=False,
            headers={"User-Agent": "DummyMarketObserver/0.1 (public-read-only)"},
        )

    def fetch_candles(
        self,
        asset: str,
        timeframe: str,
        *,
        limit: int = 120,
    ) -> ProviderBatch:
        normalized_asset = str(asset).upper()
        normalized_timeframe = str(timeframe)
        if normalized_asset not in ALLOWED_ASSETS:
            raise ValueError(f"unsupported asset: {normalized_asset}")
        if normalized_timeframe not in ALLOWED_TIMEFRAMES:
            raise ValueError(f"unsupported timeframe: {normalized_timeframe}")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
            raise ValueError("limit must be an integer from 1 through 200")

        requested_at_s = float(self.clock())
        source_interval_s = SOURCE_INTERVAL_SECONDS[normalized_timeframe]
        target_interval_s = TIMEFRAME_SECONDS[normalized_timeframe]
        # Request only fully elapsed source buckets. Filtering after receipt is
        # still mandatory because providers may include their current open bar.
        closed_boundary_s = int(requested_at_s // source_interval_s) * source_interval_s
        source_count = min(
            MAX_SOURCE_BARS,
            max(limit * (target_interval_s // source_interval_s) + 2, 32),
        )
        start_s = closed_boundary_s - source_count * source_interval_s
        endpoint = (
            f"{self.base_url}/products/"
            f"{COINBASE_PRODUCTS[normalized_asset]}/candles"
        )
        params = {
            "granularity": source_interval_s,
            "start": _iso_utc(start_s),
            "end": _iso_utc(closed_boundary_s),
        }
        client = self._client()
        close = getattr(client, "close", None)
        try:
            response = client.get(endpoint, params=params)
            response.raise_for_status()
            rows = response.json()
            received_at_s = float(self.clock())
        except Exception as exc:
            raise ProviderUnavailable(f"coinbase public candle read failed: {type(exc).__name__}") from exc
        finally:
            if callable(close):
                close()
        if not isinstance(rows, list):
            raise ProviderSchemaDrift("coinbase candle payload is not a list")

        raw_payload = {
            "provider": "coinbase_exchange",
            "endpoint": endpoint,
            "params": params,
            "requested_at_s": requested_at_s,
            "received_at_s": received_at_s,
            "rows": rows,
        }
        by_open_time: dict[int, CandleBar] = {}
        invalid_rows = 0
        open_rows = 0
        for row in rows:
            if not isinstance(row, list) or len(row) < 6:
                invalid_rows += 1
                continue
            try:
                open_time_s = int(row[0])
                close_time_s = open_time_s + source_interval_s
                if close_time_s > received_at_s:
                    open_rows += 1
                    continue
                candle = CandleBar(
                    asset=normalized_asset,
                    venue="coinbase_exchange",
                    timeframe=(
                        normalized_timeframe
                        if source_interval_s == target_interval_s
                        else (
                            "1h" if source_interval_s == TIMEFRAME_SECONDS["1h"] else "1d"
                        )
                    ),
                    interval_s=source_interval_s,
                    open_time_s=open_time_s,
                    close_time_s=close_time_s,
                    received_at_s=received_at_s,
                    low=float(row[1]),
                    high=float(row[2]),
                    open=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                    source=self.ADAPTER_VERSION,
                    raw_sha256=sha256_json(row),
                    # Coinbase supplies the bucket-open time, not an
                    # independent provider observation timestamp.
                    provider_observed_at_s=None,
                )
            except (TypeError, ValueError):
                invalid_rows += 1
                continue
            existing = by_open_time.get(open_time_s)
            if existing is not None and existing.raw_sha256 != candle.raw_sha256:
                raise ProviderSchemaDrift(
                    f"conflicting duplicate candle at {open_time_s}"
                )
            by_open_time[open_time_s] = candle

        source_bars = sorted(by_open_time.values(), key=lambda item: item.open_time_s)
        candles, aggregate_warnings = _aggregate_closed_bars(
            source_bars,
            timeframe=normalized_timeframe,
            received_at_s=received_at_s,
        )
        candles = candles[-limit:]
        warnings = list(aggregate_warnings)
        if invalid_rows:
            warnings.append(f"ignored_{invalid_rows}_invalid_rows")
        if open_rows:
            warnings.append(f"excluded_{open_rows}_open_rows")
        if not candles:
            raise ProviderUnavailable("no closed Coinbase candles available")
        gaps = sum(
            current.open_time_s != previous.close_time_s
            for previous, current in zip(candles, candles[1:])
        )
        if gaps:
            warnings.append(f"detected_{gaps}_candle_gaps")
        max_from_window = MAX_SOURCE_BARS // max(
            1, target_interval_s // source_interval_s
        )
        if limit > max_from_window:
            warnings.append(
                f"provider_window_limits_{normalized_timeframe}_to_{max_from_window}_bars"
            )
        status = ObservationStatus.COMPLETE
        if gaps or invalid_rows or len(candles) < min(limit, max_from_window):
            status = ObservationStatus.PARTIAL
        provenance = SourceProvenance(
            provider="coinbase_exchange",
            venue="coinbase_exchange",
            endpoint=endpoint,
            documentation_url=(
                "https://docs.cdp.coinbase.com/api-reference/"
                "exchange-api/rest-api/products/get-product-candles"
            ),
            adapter_version=self.ADAPTER_VERSION,
            rights_identifier="coinbase-cdp-limited-api-license-2026-06-23",
            terms_review_identifier=(
                "dummy-terms-review-coinbase-cdp-2026-07-25-v1"
            ),
            terms_url=(
                "https://www.coinbase.com/legal/developer-platform/"
                "terms-of-service"
            ),
            automated_use_permitted=True,
        )
        return ProviderBatch(
            candles=tuple(candles),
            provenance=provenance,
            requested_at_s=requested_at_s,
            received_at_s=received_at_s,
            raw_payload=raw_payload,
            status=status,
            warnings=tuple(warnings),
        )
