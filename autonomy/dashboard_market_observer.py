"""Validated, artifact-only market-observer reads for the dashboard.

This module deliberately imports only the observer's contracts and immutable
artifact store.  It never imports a provider or ``MarketObserver``, so a
dashboard request cannot trigger a public-data refresh.
"""
from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any, Mapping

from autonomy.market_observer.artifacts import ContentAddressedArtifactStore
from autonomy.market_observer.contracts import (
    ALLOWED_ASSETS,
    ALLOWED_TIMEFRAMES,
    CandleBar,
    ChartBundle,
    ObservationStatus,
    canonical_json,
    sha256_json,
)

DEFAULT_MARKET_OBSERVER_ROOT = Path("artifacts/dummy/market_observer")
LIGHTWEIGHT_CHARTS_VERSION = "5.2.0"
LIGHTWEIGHT_CHARTS_ASSET = (
    Path(__file__).with_name("dashboard_assets")
    / "vendor"
    / "lightweight-charts"
    / LIGHTWEIGHT_CHARTS_VERSION
    / "lightweight-charts.standalone.production.js"
)

_AUTHORITY_FIELDS = {
    "execution",
    "order",
    "cancel",
    "amend",
    "allocation",
    "promotion",
}
_DISPLAYABLE_STATUSES = {
    ObservationStatus.COMPLETE.value,
    ObservationStatus.PARTIAL.value,
    ObservationStatus.STALE.value,
}
_MAX_CANDLES = 200
_MAX_PATTERN_ROWS = 200
_MAX_FUTURE_SKEW_SECONDS = 300.0


class ChartArtifactError(ValueError):
    """Raised when an immutable chart artifact fails its stored contract."""


def _false_authority(value: Any) -> bool:
    return (
        isinstance(value, Mapping)
        and set(value) == _AUTHORITY_FIELDS
        and all(value[field] is False for field in _AUTHORITY_FIELDS)
    )


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _validate_chart_envelope(
    value: Any,
    *,
    asset: str,
    timeframe: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(value, dict):
        raise ChartArtifactError("chart observation is not an object")
    observation_id = value.get("observation_id")
    if (
        not isinstance(observation_id, str)
        or len(observation_id) != 64
        or any(character not in "0123456789abcdef" for character in observation_id)
    ):
        raise ChartArtifactError("chart observation identity is invalid")
    identity = {key: item for key, item in value.items() if key != "observation_id"}
    if sha256_json(identity) != observation_id:
        raise ChartArtifactError("chart observation content hash does not match")
    if value.get("kind") != "chart_bundle":
        raise ChartArtifactError("artifact is not a chart bundle")
    if value.get("status") not in _DISPLAYABLE_STATUSES:
        raise ChartArtifactError("chart artifact status is not displayable")
    requested = value.get("requested")
    resolved = value.get("resolved")
    if (
        not isinstance(requested, dict)
        or requested.get("asset") != asset
        or requested.get("timeframe") != timeframe
        or not isinstance(resolved, dict)
        or resolved.get("asset") != asset
        or resolved.get("timeframe") != timeframe
    ):
        raise ChartArtifactError("chart artifact identity does not match request")
    source = value.get("source")
    if (
        not isinstance(source, dict)
        or source.get("public_read_only") is not True
        or not all(
            isinstance(source.get(field), str) and source[field].strip()
            for field in (
                "provider",
                "venue",
                "endpoint",
                "documentation_url",
                "adapter_version",
            )
        )
    ):
        raise ChartArtifactError("chart source provenance is invalid")
    if not _false_authority(value.get("authority")):
        raise ChartArtifactError("chart observation carries invalid authority")

    payload = value.get("payload")
    stored_bundle = payload.get("chart_bundle") if isinstance(payload, dict) else None
    if not isinstance(stored_bundle, dict):
        raise ChartArtifactError("chart bundle payload is missing")
    if (
        stored_bundle.get("schema_version") != 1
        or stored_bundle.get("asset") != asset
        or stored_bundle.get("timeframe") != timeframe
        or not _false_authority(stored_bundle.get("authority"))
    ):
        raise ChartArtifactError("chart bundle identity or authority is invalid")
    candle_rows = stored_bundle.get("candles")
    if (
        not isinstance(candle_rows, list)
        or not candle_rows
        or len(candle_rows) > _MAX_CANDLES
    ):
        raise ChartArtifactError("chart candle count is invalid")
    try:
        candles = tuple(CandleBar.from_dict(row) for row in candle_rows)
    except (TypeError, ValueError) as exc:
        raise ChartArtifactError("chart candle contract is invalid") from exc
    indicators = stored_bundle.get("indicators")
    patterns = stored_bundle.get("patterns")
    if not isinstance(indicators, dict):
        raise ChartArtifactError("chart indicators are invalid")
    if (
        not isinstance(patterns, list)
        or len(patterns) > _MAX_PATTERN_ROWS
        or any(not isinstance(pattern, dict) for pattern in patterns)
    ):
        raise ChartArtifactError("chart patterns are invalid")
    try:
        normalized_bundle = ChartBundle(
            asset=asset,
            timeframe=timeframe,
            generated_at_s=stored_bundle.get("generated_at_s"),
            candles=candles,
            indicators=indicators,
            patterns=tuple(patterns),
            observation_id=stored_bundle.get("observation_id"),
            schema_version=stored_bundle.get("schema_version"),
        ).to_dict()
    except (TypeError, ValueError) as exc:
        raise ChartArtifactError("chart bundle contract is invalid") from exc
    if canonical_json(normalized_bundle) != canonical_json(stored_bundle):
        raise ChartArtifactError("chart bundle contains unknown or altered fields")
    received_at_s = _finite(value.get("received_at_s"))
    if (
        received_at_s is None
        or normalized_bundle["generated_at_s"] > received_at_s
    ):
        raise ChartArtifactError("chart observation clock is invalid")
    return value, normalized_bundle


def _failure_summary(
    value: dict[str, Any] | None,
    *,
    asset: str,
    timeframe: str,
) -> dict[str, Any] | None:
    if value is None:
        return None
    envelope, _bundle = _validate_chart_envelope(
        value,
        asset=asset,
        timeframe=timeframe,
    )
    return {
        "observation_id": envelope["observation_id"],
        "status": envelope["status"],
        "received_at_s": envelope["received_at_s"],
        "warnings": list(envelope.get("warnings") or ()),
    }


def read_market_chart(
    root: Path | str,
    asset: str,
    timeframe: str,
    *,
    now_s: float | None = None,
) -> dict[str, Any]:
    """Read and validate one persisted chart without contacting a provider."""
    normalized_asset = str(asset).upper()
    normalized_timeframe = str(timeframe)
    if normalized_asset not in ALLOWED_ASSETS:
        raise ChartArtifactError(f"unsupported asset: {normalized_asset}")
    if normalized_timeframe not in ALLOWED_TIMEFRAMES:
        raise ChartArtifactError(f"unsupported timeframe: {normalized_timeframe}")
    current_time = time.time() if now_s is None else float(now_s)
    if not math.isfinite(current_time):
        raise ChartArtifactError("dashboard clock is invalid")

    store = ContentAddressedArtifactStore(root)
    try:
        complete = store.read_latest(
            "chart_bundle",
            normalized_asset,
            normalized_timeframe,
        )
        failure = store.read_latest(
            "chart_bundle",
            normalized_asset,
            normalized_timeframe,
            include_failure=True,
        )
    except (OSError, TypeError, ValueError) as exc:
        raise ChartArtifactError(
            "chart artifact content hash or pointer is invalid"
        ) from exc
    failure_summary = _failure_summary(
        failure,
        asset=normalized_asset,
        timeframe=normalized_timeframe,
    )
    selected = complete
    serving_last_complete = complete is not None
    if selected is None and failure is not None:
        selected = failure
        serving_last_complete = False
    if selected is None:
        return {
            "schema_version": 1,
            "available": False,
            "artifact_status": ObservationStatus.UNAVAILABLE.value,
            "asset": normalized_asset,
            "timeframe": normalized_timeframe,
            "chart_bundle": None,
            "source": None,
            "warnings": ["no_persisted_chart_bundle"],
            "latest_refresh": None,
            "authority": {
                field: False for field in sorted(_AUTHORITY_FIELDS)
            },
            "rendering": {
                "library": "lightweight-charts",
                "version": LIGHTWEIGHT_CHARTS_VERSION,
                "data_provider": False,
            },
        }

    envelope, bundle = _validate_chart_envelope(
        selected,
        asset=normalized_asset,
        timeframe=normalized_timeframe,
    )
    last_candle = bundle["candles"][-1]
    close_time_s = float(last_candle["close_time_s"])
    age_seconds = current_time - close_time_s
    threshold_seconds = float(last_candle["interval_s"]) * 2.0
    time_status = (
        "FUTURE_SKEW"
        if age_seconds < -_MAX_FUTURE_SKEW_SECONDS
        else ("STALE" if age_seconds > threshold_seconds else "FRESH")
    )
    artifact_status = str(envelope["status"])
    if time_status != "FRESH" and artifact_status == ObservationStatus.COMPLETE.value:
        artifact_status = ObservationStatus.STALE.value
    latest_refresh = failure_summary
    if (
        latest_refresh is not None
        and float(latest_refresh["received_at_s"]) <= float(envelope["received_at_s"])
    ):
        latest_refresh = None
    return {
        "schema_version": 1,
        "available": True,
        "artifact_status": artifact_status,
        "persisted_status": envelope["status"],
        "asset": normalized_asset,
        "timeframe": normalized_timeframe,
        "observation_id": envelope["observation_id"],
        "received_at_s": envelope["received_at_s"],
        "latest_bar_close_time_s": last_candle["close_time_s"],
        "data_age_seconds": round(age_seconds, 1),
        "freshness_threshold_seconds": threshold_seconds,
        "time_status": time_status,
        "serving_last_complete": serving_last_complete,
        "chart_bundle": bundle,
        "source": dict(envelope["source"]),
        "warnings": list(envelope.get("warnings") or ()),
        "latest_refresh": latest_refresh,
        "authority": {
            field: False for field in sorted(_AUTHORITY_FIELDS)
        },
        "rendering": {
            "library": "lightweight-charts",
            "version": LIGHTWEIGHT_CHARTS_VERSION,
            "data_provider": False,
        },
    }
