from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from core.ontology import (
    CapConfig,
    ComplianceVerdict,
    MarketComplianceMetadata,
)
from core.config_loader import load_caps


_SELECTOR_FIELDS = {"category", "tag", "series", "event"}


def _normalise(value: Any) -> str:
    """Canonicalise metadata for exact, case-insensitive comparisons."""
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip().casefold()


def _coerce_metadata(
    metadata: MarketComplianceMetadata | Mapping[str, Any] | None,
) -> MarketComplianceMetadata | None:
    if metadata is None:
        return None
    if isinstance(metadata, MarketComplianceMetadata):
        return metadata
    try:
        return MarketComplianceMetadata.model_validate(dict(metadata))
    except Exception:
        return None


def _parse_selector(policy: str) -> tuple[str, str] | None:
    raw = str(policy or "").strip()
    if not raw:
        return None
    if ":" not in raw:
        # CapConfig historically called these entries blocked_categories, so a
        # bare value remains an exact category selector.
        return "category", _normalise(raw)
    field, value = raw.split(":", 1)
    field = _normalise(field)
    value = _normalise(value)
    if field not in _SELECTOR_FIELDS or not value:
        return None
    return field, value


def _metadata_values(metadata: MarketComplianceMetadata) -> dict[str, set[str]]:
    categories = {_normalise(metadata.series_category)}
    if metadata.event_category:
        categories.add(_normalise(metadata.event_category))
    return {
        "category": {value for value in categories if value},
        "tag": {_normalise(tag) for tag in metadata.series_tags if _normalise(tag)},
        "series": {_normalise(metadata.series_ticker)},
        "event": {_normalise(metadata.event_ticker)},
    }


def assess_compliance(
    market_ticker: str,
    contract_ticker: str,
    caps: CapConfig | None = None,
    *,
    metadata: MarketComplianceMetadata | Mapping[str, Any] | None = None,
    require_verified_metadata: bool = False,
) -> ComplianceVerdict:
    """Apply compliance policy to verified Kalshi hierarchy metadata.

    For live submission, callers must pass ``require_verified_metadata=True``
    and metadata fetched independently from Kalshi's read-only market, event,
    and series endpoints. Tickers are opaque and are never an acceptable live
    category oracle. The legacy prefix fallback remains only for non-live
    compatibility while old callers migrate.
    """
    if caps is None:
        caps = load_caps()
    policies = [str(item) for item in caps.blocked_categories if str(item).strip()]
    if not policies:
        return ComplianceVerdict(passed=True, blocked_categories=[], reason="Compliant")

    resolved = _coerce_metadata(metadata)
    if metadata is not None and resolved is None:
        return ComplianceVerdict(
            passed=False,
            blocked_categories=[],
            reason="Compliance metadata malformed; verified Kalshi metadata required",
        )

    if resolved is not None:
        if not resolved.verified:
            return ComplianceVerdict(
                passed=False,
                blocked_categories=[],
                reason="Compliance metadata is not verified",
            )
        if _normalise(resolved.market_ticker) != _normalise(market_ticker):
            return ComplianceVerdict(
                passed=False,
                blocked_categories=[],
                reason="Compliance metadata market ticker mismatch",
            )
        if not all(
            (
                _normalise(resolved.event_ticker),
                _normalise(resolved.series_ticker),
                _normalise(resolved.series_category),
                _normalise(resolved.source),
            )
        ):
            return ComplianceVerdict(
                passed=False,
                blocked_categories=[],
                reason="Compliance metadata incomplete",
            )

        values = _metadata_values(resolved)
        blocked: list[str] = []
        invalid: list[str] = []
        for policy in policies:
            selector = _parse_selector(policy)
            if selector is None:
                invalid.append(policy)
                continue
            field, value = selector
            if value in values[field]:
                blocked.append(policy)
        if invalid:
            return ComplianceVerdict(
                passed=False,
                blocked_categories=invalid,
                reason=f"Invalid compliance selectors: {invalid}",
            )
        if blocked:
            return ComplianceVerdict(
                passed=False,
                blocked_categories=blocked,
                reason=f"Blocked Kalshi metadata selectors: {blocked}",
            )
        return ComplianceVerdict(passed=True, blocked_categories=[], reason="Compliant")

    if require_verified_metadata:
        return ComplianceVerdict(
            passed=False,
            blocked_categories=[],
            reason="Verified Kalshi compliance metadata required",
        )

    # Non-live compatibility only. Do not use this path at the live sink.
    market = market_ticker.strip().lower()
    contract = contract_ticker.strip().lower()
    blocked = [
        category
        for category in policies
        if market.startswith(category.strip().lower()) or contract.startswith(category.strip().lower())
    ]
    if blocked:
        return ComplianceVerdict(
            passed=False,
            blocked_categories=blocked,
            reason=f"Blocked legacy ticker prefixes: {blocked}",
        )
    return ComplianceVerdict(passed=True, blocked_categories=[], reason="Compliant (legacy non-live metadata fallback)")
