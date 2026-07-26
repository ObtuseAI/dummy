"""Strict, authority-free contracts for public crypto market observations.

The observer is an evidence sidecar, not a forecast or execution component.
Every candle is closed and point-in-time bounded, and every envelope carries
explicitly false production authority.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import urlsplit

SCHEMA_VERSION = 1
ALLOWED_ASSETS = frozenset({"BTC", "ETH", "SOL"})
ALLOWED_TIMEFRAMES = frozenset({"15m", "1h", "4h", "1d", "1w"})


def is_tradingview_url(value: str) -> bool:
    """Return true for every hostname carrying a TradingView domain label."""
    try:
        host = (urlsplit(str(value)).hostname or "").encode("idna").decode("ascii")
    except (UnicodeError, ValueError):
        return False
    return any("tradingview" in label for label in host.lower().split("."))


def canonical_json(value: Any) -> str:
    """Return the stable JSON representation used for every content hash."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _finite(name: str, value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"{name} must be finite")
    return parsed


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze_value(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    return value


def _thaw_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_value(item) for item in value]
    return value


def _freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    # Round-trip validates JSON safety and severs every caller-owned reference;
    # recursive proxies/tuples make the frozen dataclass deeply immutable.
    copied = json.loads(canonical_json(dict(value or {})))
    return _freeze_value(copied)


class ObservationStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"
    SCHEMA_DRIFT = "SCHEMA_DRIFT"


@dataclass(frozen=True, slots=True)
class CandleBar:
    """One fully closed OHLCV bar with source and receipt provenance."""

    asset: str
    venue: str
    timeframe: str
    interval_s: int
    open_time_s: int
    close_time_s: int
    received_at_s: float
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str
    raw_sha256: str
    provider_observed_at_s: float | None = None
    closed: bool = True
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        asset = str(self.asset).upper()
        timeframe = str(self.timeframe)
        if asset not in ALLOWED_ASSETS:
            raise ValueError(f"unsupported asset: {asset}")
        if timeframe not in ALLOWED_TIMEFRAMES:
            raise ValueError(f"unsupported timeframe: {timeframe}")
        if not self.venue or not self.source:
            raise ValueError("venue and source are required")
        if int(self.interval_s) <= 0:
            raise ValueError("interval_s must be positive")
        if int(self.open_time_s) < 0:
            raise ValueError("open_time_s must be non-negative")
        if int(self.close_time_s) != int(self.open_time_s) + int(self.interval_s):
            raise ValueError("close_time_s must equal open_time_s + interval_s")
        received = _finite("received_at_s", self.received_at_s)
        if not self.closed:
            raise ValueError("CandleBar accepts closed bars only")
        if self.close_time_s > received:
            raise ValueError("bar was not closed at receipt time")
        values = {
            "open": _finite("open", self.open),
            "high": _finite("high", self.high),
            "low": _finite("low", self.low),
            "close": _finite("close", self.close),
            "volume": _finite("volume", self.volume),
        }
        if min(values["open"], values["high"], values["low"], values["close"]) <= 0:
            raise ValueError("OHLC prices must be positive")
        if values["volume"] < 0:
            raise ValueError("volume must be non-negative")
        if values["high"] < max(values["open"], values["close"], values["low"]):
            raise ValueError("high is below an OHLC value")
        if values["low"] > min(values["open"], values["close"], values["high"]):
            raise ValueError("low is above an OHLC value")
        if len(self.raw_sha256) != 64:
            raise ValueError("raw_sha256 must be a SHA-256 hex digest")
        try:
            int(self.raw_sha256, 16)
        except ValueError as exc:
            raise ValueError("raw_sha256 must be a SHA-256 hex digest") from exc
        if self.provider_observed_at_s is not None:
            observed = _finite("provider_observed_at_s", self.provider_observed_at_s)
            if observed > received:
                raise ValueError("provider observation cannot follow receipt")
        if int(self.schema_version) != SCHEMA_VERSION:
            raise ValueError(f"unsupported CandleBar schema: {self.schema_version}")
        object.__setattr__(self, "asset", asset)
        object.__setattr__(self, "timeframe", timeframe)
        for name, value in values.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "received_at_s", received)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "asset": self.asset,
            "venue": self.venue,
            "timeframe": self.timeframe,
            "interval_s": self.interval_s,
            "open_time_s": self.open_time_s,
            "close_time_s": self.close_time_s,
            "received_at_s": self.received_at_s,
            "provider_observed_at_s": self.provider_observed_at_s,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "source": self.source,
            "raw_sha256": self.raw_sha256,
            "closed": self.closed,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CandleBar":
        return cls(**dict(value))


@dataclass(frozen=True, slots=True)
class SourceProvenance:
    provider: str
    venue: str
    endpoint: str
    documentation_url: str
    adapter_version: str
    rights_identifier: str
    terms_review_identifier: str
    terms_url: str
    automated_use_permitted: bool
    public_read_only: bool = True

    def __post_init__(self) -> None:
        if not all(
            str(value).strip()
            for value in (
                self.provider,
                self.venue,
                self.endpoint,
                self.documentation_url,
                self.adapter_version,
                self.rights_identifier,
                self.terms_review_identifier,
                self.terms_url,
            )
        ):
            raise ValueError("source provenance fields are required")
        for candidate in (self.endpoint, self.documentation_url, self.terms_url):
            if is_tradingview_url(candidate):
                raise ValueError("TradingView domains are prohibited data sources")
        if self.automated_use_permitted is not True:
            raise ValueError("source terms do not permit automated API use")
        if self.public_read_only is not True:
            raise ValueError("market observer sources must be public read-only")

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "venue": self.venue,
            "endpoint": self.endpoint,
            "documentation_url": self.documentation_url,
            "adapter_version": self.adapter_version,
            "rights_identifier": self.rights_identifier,
            "terms_review_identifier": self.terms_review_identifier,
            "terms_url": self.terms_url,
            "automated_use_permitted": self.automated_use_permitted,
            "public_read_only": self.public_read_only,
        }


@dataclass(frozen=True, slots=True)
class ProductionAuthority:
    execution: bool = False
    order: bool = False
    cancel: bool = False
    amend: bool = False
    allocation: bool = False
    promotion: bool = False

    def __post_init__(self) -> None:
        if any(
            (
                self.execution,
                self.order,
                self.cancel,
                self.amend,
                self.allocation,
                self.promotion,
            )
        ):
            raise ValueError("market observations cannot carry production authority")

    def to_dict(self) -> dict[str, bool]:
        return {
            "execution": False,
            "order": False,
            "cancel": False,
            "amend": False,
            "allocation": False,
            "promotion": False,
        }


@dataclass(frozen=True, slots=True)
class ObservationEnvelope:
    """Immutable observation persisted by content hash."""

    kind: str
    status: ObservationStatus
    requested_at_s: float
    received_at_s: float
    requested: Mapping[str, Any]
    resolved: Mapping[str, Any]
    source: SourceProvenance
    payload: Mapping[str, Any]
    raw_sha256: str | None = None
    raw_ref: str | None = None
    warnings: tuple[str, ...] = ()
    authority: ProductionAuthority = field(default_factory=ProductionAuthority)
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not str(self.kind).strip():
            raise ValueError("observation kind is required")
        requested_at = _finite("requested_at_s", self.requested_at_s)
        received_at = _finite("received_at_s", self.received_at_s)
        if received_at < requested_at:
            raise ValueError("received_at_s cannot precede requested_at_s")
        if int(self.schema_version) != SCHEMA_VERSION:
            raise ValueError(f"unsupported observation schema: {self.schema_version}")
        if self.raw_sha256 is not None:
            if len(self.raw_sha256) != 64:
                raise ValueError("raw_sha256 must be a SHA-256 hex digest")
            try:
                int(self.raw_sha256, 16)
            except ValueError as exc:
                raise ValueError("raw_sha256 must be a SHA-256 hex digest") from exc
        object.__setattr__(self, "status", ObservationStatus(self.status))
        object.__setattr__(self, "requested_at_s", requested_at)
        object.__setattr__(self, "received_at_s", received_at)
        object.__setattr__(self, "requested", _freeze_mapping(self.requested))
        object.__setattr__(self, "resolved", _freeze_mapping(self.resolved))
        object.__setattr__(self, "payload", _freeze_mapping(self.payload))
        object.__setattr__(
            self,
            "warnings",
            tuple(str(item) for item in self.warnings if str(item)),
        )

    def _identity_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "status": self.status.value,
            "requested_at_s": self.requested_at_s,
            "received_at_s": self.received_at_s,
            "requested": _thaw_value(self.requested),
            "resolved": _thaw_value(self.resolved),
            "source": self.source.to_dict(),
            "payload": _thaw_value(self.payload),
            "raw_sha256": self.raw_sha256,
            "raw_ref": self.raw_ref,
            "warnings": list(self.warnings),
            "authority": self.authority.to_dict(),
        }

    @property
    def observation_id(self) -> str:
        return sha256_json(self._identity_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"observation_id": self.observation_id, **self._identity_dict()}


@dataclass(frozen=True, slots=True)
class ChartBundle:
    """Facts-only chart payload. It intentionally has no probability field."""

    asset: str
    timeframe: str
    generated_at_s: float
    candles: tuple[CandleBar, ...]
    indicators: Mapping[str, Any] = field(default_factory=dict)
    patterns: tuple[Mapping[str, Any], ...] = ()
    observation_id: str | None = None
    authority: ProductionAuthority = field(default_factory=ProductionAuthority)
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        asset = str(self.asset).upper()
        timeframe = str(self.timeframe)
        if asset not in ALLOWED_ASSETS:
            raise ValueError(f"unsupported asset: {asset}")
        if timeframe not in ALLOWED_TIMEFRAMES:
            raise ValueError(f"unsupported timeframe: {timeframe}")
        generated = _finite("generated_at_s", self.generated_at_s)
        prior_close: int | None = None
        for candle in self.candles:
            if candle.asset != asset or candle.timeframe != timeframe:
                raise ValueError("chart candles do not match the requested identity")
            if candle.received_at_s > generated:
                raise ValueError("chart generation precedes candle receipt")
            if prior_close is not None and candle.open_time_s < prior_close:
                raise ValueError("chart candles overlap or are out of order")
            prior_close = candle.close_time_s
        object.__setattr__(self, "asset", asset)
        object.__setattr__(self, "timeframe", timeframe)
        object.__setattr__(self, "generated_at_s", generated)
        object.__setattr__(self, "indicators", _freeze_mapping(self.indicators))
        object.__setattr__(
            self,
            "patterns",
            tuple(_freeze_mapping(pattern) for pattern in self.patterns),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "asset": self.asset,
            "timeframe": self.timeframe,
            "generated_at_s": self.generated_at_s,
            "candles": [candle.to_dict() for candle in self.candles],
            "indicators": _thaw_value(self.indicators),
            "patterns": [_thaw_value(pattern) for pattern in self.patterns],
            "observation_id": self.observation_id,
            "authority": self.authority.to_dict(),
        }
