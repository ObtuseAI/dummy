"""Fail-closed Kalshi hierarchy metadata resolution for compliance policy."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from core.ontology import MarketComplianceMetadata


SOURCE = "kalshi_read_only_market_event_series_v1"


class ComplianceMetadataError(RuntimeError):
    """Raised when Kalshi metadata cannot be linked and verified exactly."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _normalise(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip().casefold()


def _object(raw: Any, envelope: str, *, code: str) -> Mapping[str, Any]:
    if not isinstance(raw, Mapping):
        raise ComplianceMetadataError(code, f"{envelope} response is not an object")
    nested = raw.get(envelope)
    if nested is not None:
        if not isinstance(nested, Mapping):
            raise ComplianceMetadataError(code, f"{envelope} envelope is not an object")
        return nested
    return raw


def _required_text(record: Mapping[str, Any], field: str, *, code: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ComplianceMetadataError(code, f"missing or invalid {field}")
    return value.strip()


def _optional_text(record: Mapping[str, Any], field: str) -> str | None:
    value = record.get(field)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ComplianceMetadataError("INVALID_EVENT_CATEGORY", f"invalid {field}")
    return value.strip() or None


async def fetch_verified_kalshi_compliance_metadata(
    client: Any,
    market_ticker: str,
    *,
    market_raw: Any | None = None,
) -> MarketComplianceMetadata:
    """Fetch and verify market -> event -> series category metadata.

    Only read-only GET methods are used. Every hierarchy identifier is checked
    for an exact, case-insensitive match so a caller cannot attach safe
    metadata from a different market. Series category and tags are canonical;
    the event category is retained as a corroborating field while Kalshi
    completes its documented market/event metadata migrations.
    """
    requested_market = str(market_ticker or "").strip()
    if not requested_market:
        raise ComplianceMetadataError("INVALID_MARKET_TICKER", "market ticker is empty")

    if market_raw is None:
        try:
            market_raw = await client.get_market(requested_market)
        except Exception as exc:
            raise ComplianceMetadataError("MARKET_METADATA_UNAVAILABLE", type(exc).__name__) from exc
    market = _object(market_raw, "market", code="INVALID_MARKET_RESPONSE")
    actual_market = _required_text(market, "ticker", code="INVALID_MARKET_RESPONSE")
    if _normalise(actual_market) != _normalise(requested_market):
        raise ComplianceMetadataError("MARKET_TICKER_MISMATCH", actual_market)
    event_ticker = _required_text(market, "event_ticker", code="INVALID_MARKET_RESPONSE")

    try:
        event_raw = await client.get_event(event_ticker)
    except Exception as exc:
        raise ComplianceMetadataError("EVENT_METADATA_UNAVAILABLE", type(exc).__name__) from exc
    event = _object(event_raw, "event", code="INVALID_EVENT_RESPONSE")
    actual_event = _required_text(event, "event_ticker", code="INVALID_EVENT_RESPONSE")
    if _normalise(actual_event) != _normalise(event_ticker):
        raise ComplianceMetadataError("EVENT_TICKER_MISMATCH", actual_event)
    series_ticker = _required_text(event, "series_ticker", code="INVALID_EVENT_RESPONSE")
    event_category = _optional_text(event, "category")

    try:
        series_raw = await client.get_series(series_ticker)
    except Exception as exc:
        raise ComplianceMetadataError("SERIES_METADATA_UNAVAILABLE", type(exc).__name__) from exc
    series = _object(series_raw, "series", code="INVALID_SERIES_RESPONSE")
    actual_series = _required_text(series, "ticker", code="INVALID_SERIES_RESPONSE")
    if _normalise(actual_series) != _normalise(series_ticker):
        raise ComplianceMetadataError("SERIES_TICKER_MISMATCH", actual_series)
    series_category = _required_text(series, "category", code="INVALID_SERIES_RESPONSE")

    if event_category and _normalise(event_category) != _normalise(series_category):
        raise ComplianceMetadataError(
            "CATEGORY_MISMATCH",
            f"event={event_category!r}, series={series_category!r}",
        )

    raw_tags = series.get("tags")
    if raw_tags is None:
        tags: list[str] = []
    elif isinstance(raw_tags, list) and all(isinstance(tag, str) for tag in raw_tags):
        tags = [tag.strip() for tag in raw_tags if tag.strip()]
    else:
        raise ComplianceMetadataError("INVALID_SERIES_TAGS", "series tags must be a string list or null")

    return MarketComplianceMetadata(
        source=SOURCE,
        received_at=datetime.now(timezone.utc),
        market_ticker=actual_market,
        event_ticker=actual_event,
        series_ticker=actual_series,
        series_category=series_category,
        event_category=event_category,
        series_tags=tags,
        verified=True,
    )
