"""Facts-only market observer service used by the local stdio surface."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from autonomy.crypto_chartist import (
    Candle,
    detect_patterns,
    rsi_series,
    trend_score,
)
from autonomy.market_observer.artifacts import ContentAddressedArtifactStore
from autonomy.market_observer.contracts import (
    ALLOWED_ASSETS,
    ALLOWED_TIMEFRAMES,
    CandleBar,
    ChartBundle,
    ObservationEnvelope,
    ObservationStatus,
    SourceProvenance,
)
from autonomy.market_observer.providers import (
    CandleProvider,
    CoinbasePublicCandleProvider,
    ProviderBatch,
    ProviderSchemaDrift,
    ProviderUnavailable,
    TIMEFRAME_SECONDS,
)
from autonomy.market_observer.runtime import CircuitBreaker, RequestRateBudget
from autonomy.signals.crypto_ta_foundry import technical_foundry_features

LOCAL_PROVENANCE = SourceProvenance(
    provider="dummy_market_observer",
    venue="local",
    endpoint="stdio",
    documentation_url="docs/AUTONOMY.md",
    adapter_version="dummy-market-observer-v1",
    rights_identifier="dummy-owned-local-derived-data-v1",
    terms_review_identifier="dummy-internal-source-review-v1",
    terms_url="docs/MARKET_OBSERVER_MCP.md",
    automated_use_permitted=True,
)


def _analysis_candles(candles: tuple[CandleBar, ...]) -> list[Candle]:
    return [
        Candle(
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
        )
        for bar in candles
    ]


def _indicator_payload(candles: tuple[CandleBar, ...]) -> dict[str, Any]:
    rows = [
        {
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        }
        for bar in candles
    ]
    features = dict(technical_foundry_features(rows))
    # The foundry's fused directional score is a research prior. The observer
    # publishes the underlying deterministic indicator facts, not that score.
    features.pop("score", None)
    features.pop("components", None)
    closes = [bar.close for bar in candles]
    rsi = rsi_series(closes)
    features.update(
        {
            "rsi_wilder_14": rsi[-1] if rsi else None,
            "ema_channel_trend": trend_score(closes) if len(closes) >= 21 else None,
            "last_close": closes[-1] if closes else None,
            "bar_count": len(candles),
            "facts_only": True,
        }
    )
    return features


def _pattern_payload(candles: tuple[CandleBar, ...]) -> tuple[dict[str, Any], ...]:
    if not candles:
        return ()
    final = candles[-1]
    return tuple(
        {
            "name": hit.name,
            "direction": hit.direction,
            "strength": hit.strength,
            "bar_open_time_s": final.open_time_s,
            "bar_close_time_s": final.close_time_s,
        }
        for hit in detect_patterns(_analysis_candles(candles))
    )


class MarketObserver:
    """Read-only public observation coordinator with immutable sidecar output."""

    def __init__(
        self,
        *,
        provider: CandleProvider | None = None,
        artifact_root: Path | str = Path("artifacts/dummy/market_observer"),
        clock: Callable[[], float] | None = None,
        request_budget: RequestRateBudget | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self.clock = clock or time.time
        self.provider = provider or CoinbasePublicCandleProvider(clock=self.clock)
        self.store = ContentAddressedArtifactStore(artifact_root)
        self.request_budget = request_budget or RequestRateBudget()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

    @staticmethod
    def _request(asset: str, timeframe: str, limit: int) -> dict[str, Any]:
        normalized_asset = str(asset).upper()
        normalized_timeframe = str(timeframe)
        if normalized_asset not in ALLOWED_ASSETS:
            raise ValueError(f"unsupported asset: {normalized_asset}")
        if normalized_timeframe not in ALLOWED_TIMEFRAMES:
            raise ValueError(f"unsupported timeframe: {normalized_timeframe}")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
            raise ValueError("limit must be an integer from 1 through 200")
        return {
            "asset": normalized_asset,
            "timeframe": normalized_timeframe,
            "limit": limit,
        }

    def _fetch(
        self,
        *,
        asset: str,
        timeframe: str,
        limit: int,
    ) -> tuple[dict[str, Any], ProviderBatch, str, str, ObservationStatus, tuple[str, ...]]:
        requested = self._request(asset, timeframe, limit)
        self.request_budget.acquire()
        self.circuit_breaker.before_call()
        try:
            batch = self.provider.fetch_candles(
                requested["asset"],
                requested["timeframe"],
                limit=requested["limit"],
            )
        except Exception:
            self.circuit_breaker.record_failure()
            raise
        else:
            self.circuit_breaker.record_success()
        if not batch.candles:
            raise ProviderSchemaDrift("provider returned an empty candle batch")
        raw_ref, raw_sha256 = self.store.write_raw(batch.raw_payload)
        warnings = list(batch.warnings)
        status = batch.status
        last = batch.candles[-1]
        if batch.received_at_s - last.close_time_s > 2 * last.interval_s:
            status = ObservationStatus.STALE
            warnings.append("latest_closed_bar_is_stale")
        return requested, batch, raw_ref, raw_sha256, status, tuple(warnings)

    def _persist(
        self,
        *,
        kind: str,
        requested: dict[str, Any],
        batch: ProviderBatch,
        payload: dict[str, Any],
        raw_ref: str,
        raw_sha256: str,
        status: ObservationStatus,
        warnings: tuple[str, ...],
    ) -> ObservationEnvelope:
        envelope = ObservationEnvelope(
            kind=kind,
            status=status,
            requested_at_s=batch.requested_at_s,
            received_at_s=batch.received_at_s,
            requested=requested,
            resolved={
                "asset": batch.candles[-1].asset,
                "timeframe": batch.candles[-1].timeframe,
                "venue": batch.candles[-1].venue,
                "bar_count": len(batch.candles),
                "latest_close_time_s": batch.candles[-1].close_time_s,
            },
            source=batch.provenance,
            payload=payload,
            raw_sha256=raw_sha256,
            raw_ref=raw_ref,
            warnings=warnings,
        )
        self.store.write_observation(envelope)
        return envelope

    def get_candles(
        self,
        asset: str,
        timeframe: str,
        *,
        limit: int = 120,
    ) -> ObservationEnvelope:
        requested, batch, raw_ref, raw_sha256, status, warnings = self._fetch(
            asset=asset,
            timeframe=timeframe,
            limit=limit,
        )
        return self._persist(
            kind="candles",
            requested=requested,
            batch=batch,
            payload={"candles": [bar.to_dict() for bar in batch.candles]},
            raw_ref=raw_ref,
            raw_sha256=raw_sha256,
            status=status,
            warnings=warnings,
        )

    def get_market_snapshot(
        self,
        asset: str,
        timeframe: str,
        *,
        limit: int = 120,
    ) -> ObservationEnvelope:
        requested, batch, raw_ref, raw_sha256, status, warnings = self._fetch(
            asset=asset,
            timeframe=timeframe,
            limit=limit,
        )
        candles = batch.candles
        first = candles[0]
        last = candles[-1]
        change_bps = (
            10_000.0 * (last.close / first.close - 1.0) if first.close > 0 else None
        )
        payload = {
            "asset": last.asset,
            "timeframe": last.timeframe,
            "venue": last.venue,
            "last_close": last.close,
            "last_volume": last.volume,
            "window_change_bps": change_bps,
            "window_open_time_s": first.open_time_s,
            "window_close_time_s": last.close_time_s,
            "bar_count": len(candles),
            "facts_only": True,
        }
        return self._persist(
            kind="market_snapshot",
            requested=requested,
            batch=batch,
            payload=payload,
            raw_ref=raw_ref,
            raw_sha256=raw_sha256,
            status=status,
            warnings=warnings,
        )

    def compute_indicators(
        self,
        asset: str,
        timeframe: str,
        *,
        limit: int = 120,
    ) -> ObservationEnvelope:
        requested, batch, raw_ref, raw_sha256, status, warnings = self._fetch(
            asset=asset,
            timeframe=timeframe,
            limit=limit,
        )
        indicators = _indicator_payload(batch.candles)
        if len(batch.candles) < 30:
            status = ObservationStatus.PARTIAL
            warnings = (*warnings, "fewer_than_30_bars_for_indicator_coverage")
        return self._persist(
            kind="indicators",
            requested=requested,
            batch=batch,
            payload={"indicators": indicators},
            raw_ref=raw_ref,
            raw_sha256=raw_sha256,
            status=status,
            warnings=warnings,
        )

    def detect_candlestick_patterns(
        self,
        asset: str,
        timeframe: str,
        *,
        limit: int = 120,
    ) -> ObservationEnvelope:
        requested, batch, raw_ref, raw_sha256, status, warnings = self._fetch(
            asset=asset,
            timeframe=timeframe,
            limit=limit,
        )
        patterns = _pattern_payload(batch.candles)
        if len(batch.candles) < 25:
            status = ObservationStatus.PARTIAL
            warnings = (*warnings, "fewer_than_25_bars_for_pattern_detection")
        return self._persist(
            kind="candlestick_patterns",
            requested=requested,
            batch=batch,
            payload={"patterns": list(patterns), "facts_only": True},
            raw_ref=raw_ref,
            raw_sha256=raw_sha256,
            status=status,
            warnings=warnings,
        )

    def get_chart_bundle(
        self,
        asset: str,
        timeframe: str,
        *,
        limit: int = 120,
    ) -> ObservationEnvelope:
        requested, batch, raw_ref, raw_sha256, status, warnings = self._fetch(
            asset=asset,
            timeframe=timeframe,
            limit=limit,
        )
        indicators = _indicator_payload(batch.candles)
        patterns = _pattern_payload(batch.candles)
        candle_observation = self._persist(
            kind="candles",
            requested=requested,
            batch=batch,
            payload={"candles": [bar.to_dict() for bar in batch.candles]},
            raw_ref=raw_ref,
            raw_sha256=raw_sha256,
            status=status,
            warnings=warnings,
        )
        if len(batch.candles) < 30:
            status = ObservationStatus.PARTIAL
            warnings = (*warnings, "limited_chart_analysis_history")
        bundle = ChartBundle(
            asset=requested["asset"],
            timeframe=requested["timeframe"],
            generated_at_s=batch.received_at_s,
            candles=batch.candles,
            indicators=indicators,
            patterns=patterns,
            observation_id=candle_observation.observation_id,
        )
        return self._persist(
            kind="chart_bundle",
            requested=requested,
            batch=batch,
            payload={"chart_bundle": bundle.to_dict()},
            raw_ref=raw_ref,
            raw_sha256=raw_sha256,
            status=status,
            warnings=warnings,
        )

    def get_network_metrics(
        self,
        asset: str,
        *,
        timeframe: str = "1d",
        limit: int = 1,
    ) -> ObservationEnvelope:
        requested = self._request(asset, timeframe, limit)
        now = float(self.clock())
        envelope = ObservationEnvelope(
            kind="network_metrics",
            status=ObservationStatus.UNAVAILABLE,
            requested_at_s=now,
            received_at_s=now,
            requested=requested,
            resolved={},
            source=LOCAL_PROVENANCE,
            payload={
                "facts_only": True,
                "reason": "no_contract_reviewed_network_provider_configured",
            },
            warnings=("network_metrics_unavailable",),
        )
        self.store.write_observation(envelope)
        return envelope

    def source_health(
        self,
        asset: str,
        timeframe: str,
        *,
        limit: int = 1,
    ) -> ObservationEnvelope:
        requested = self._request(asset, timeframe, limit)
        now = float(self.clock())
        latest = self.store.read_latest(
            "candles",
            requested["asset"],
            requested["timeframe"],
        )
        latest_failure = self.store.read_latest(
            "candles",
            requested["asset"],
            requested["timeframe"],
            include_failure=True,
        )
        status = ObservationStatus.COMPLETE
        warnings: list[str] = []
        latest_age_s: float | None = None
        stale_after_s = float(2 * TIMEFRAME_SECONDS[requested["timeframe"]])
        latest_received_at_s: float | None = None
        if latest is None:
            status = ObservationStatus.UNAVAILABLE
            warnings.append("no_complete_candle_observation")
        else:
            try:
                latest_received_at_s = float(latest["received_at_s"])
                latest_close_time_s = float(
                    (latest.get("resolved") or {})["latest_close_time_s"]
                )
            except (KeyError, TypeError, ValueError):
                status = ObservationStatus.SCHEMA_DRIFT
                warnings.append("latest_complete_timestamp_invalid")
            else:
                latest_age_s = now - latest_close_time_s
                if (
                    latest_received_at_s > now
                    or latest_close_time_s > latest_received_at_s
                ):
                    status = ObservationStatus.SCHEMA_DRIFT
                    warnings.append("latest_complete_future_dated")
                elif latest_age_s > stale_after_s:
                    status = ObservationStatus.STALE
                    warnings.append("latest_complete_is_stale")

        failure_received_at_s: float | None = None
        if latest_failure is not None:
            try:
                failure_received_at_s = float(latest_failure["received_at_s"])
                failure_status = ObservationStatus(str(latest_failure["status"]))
            except (KeyError, TypeError, ValueError):
                status = ObservationStatus.SCHEMA_DRIFT
                warnings.append("latest_failure_metadata_invalid")
            else:
                if (
                    latest_received_at_s is not None
                    and failure_received_at_s > latest_received_at_s
                    and failure_status is not ObservationStatus.COMPLETE
                ):
                    # A newer partial/stale/error observation is the current
                    # source state even though the last complete candle bundle
                    # remains available for audit and recovery.
                    status = failure_status
                    warnings.append("newer_candle_failure_observation")
        payload = {
            "facts_only": True,
            "latest_complete": (
                {
                    "observation_id": latest.get("observation_id"),
                    "status": latest.get("status"),
                    "received_at_s": latest.get("received_at_s"),
                }
                if latest
                else None
            ),
            "latest_failure": (
                {
                    "observation_id": latest_failure.get("observation_id"),
                    "status": latest_failure.get("status"),
                    "received_at_s": latest_failure.get("received_at_s"),
                }
                if latest_failure
                else None
            ),
            "latest_complete_age_s": latest_age_s,
            "stale_after_s": stale_after_s,
            "latest_complete_fresh": (
                latest is not None and status is ObservationStatus.COMPLETE
            ),
            "request_budget": self.request_budget.snapshot(),
            "circuit_breaker": self.circuit_breaker.snapshot(),
        }
        envelope = ObservationEnvelope(
            kind="source_health",
            status=status,
            requested_at_s=now,
            received_at_s=now,
            requested=requested,
            resolved={"has_complete_observation": latest is not None},
            source=LOCAL_PROVENANCE,
            payload=payload,
            warnings=tuple(warnings),
        )
        self.store.write_observation(envelope)
        return envelope

    def record_failure(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        error: Exception,
    ) -> ObservationEnvelope:
        """Persist a bounded failure without leaking exception text or secrets."""
        now = float(self.clock())
        if isinstance(error, ProviderSchemaDrift):
            status = ObservationStatus.SCHEMA_DRIFT
        elif isinstance(error, ProviderUnavailable):
            status = ObservationStatus.UNAVAILABLE
        else:
            status = ObservationStatus.UNAVAILABLE
        asset = str(arguments.get("asset", "_")).upper()
        timeframe = str(arguments.get("timeframe", "_"))
        requested = {
            "asset": asset if asset in ALLOWED_ASSETS else "_",
            "timeframe": timeframe if timeframe in ALLOWED_TIMEFRAMES else "_",
            "tool": str(tool_name),
        }
        safe_arguments: dict[str, Any] = {}
        if asset in ALLOWED_ASSETS:
            safe_arguments["asset"] = asset
        if timeframe in ALLOWED_TIMEFRAMES:
            safe_arguments["timeframe"] = timeframe
        limit = arguments.get("limit")
        if (
            isinstance(limit, int)
            and not isinstance(limit, bool)
            and 1 <= limit <= 200
        ):
            safe_arguments["limit"] = limit
        envelope = ObservationEnvelope(
            kind="tool_failure",
            status=status,
            requested_at_s=now,
            received_at_s=now,
            requested=requested,
            resolved={},
            source=LOCAL_PROVENANCE,
            payload={
                "facts_only": True,
                "error_type": type(error).__name__,
                "requested_arguments": safe_arguments,
            },
            warnings=("tool_call_failed_closed",),
        )
        self.store.write_observation(envelope)
        return envelope
