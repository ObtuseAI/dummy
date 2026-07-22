"""Governed, local-only view of repo-harvested strategy candidates.

Legacy extraction reports are research inventory, not capability manifests.
This sanitizer is applied both when reports are produced and when an older
report is read, so stale ``v1`` rows cannot regain prediction authority merely
because the harvester has not been rerun.  It performs no network calls and
writes nothing.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from autonomy.target_policy import (
    TARGET_POLICY_VERSION,
    is_data_only_target,
    is_equity_index_target,
)


STRATEGY_CATALOG_SCHEMA_VERSION = 2
STRATEGY_CATALOG_FILENAME = "strategy_extraction_report_v2.json"
LEGACY_STRATEGY_CATALOG_FILENAME = "strategy_extraction_report_v1.json"

_DATA_ONLY_NAMES = {
    "kalshiweatherforecaststrategy",
    "commoditiesenergystrategy",
}
_EQUITY_NAMES = {"stockmacromomentumstrategy"}


def _normalised_types(candidate: Mapping[str, Any]) -> set[str]:
    raw = candidate.get("market_types")
    if not isinstance(raw, list):
        return set()
    return {
        str(value).strip().casefold()
        for value in raw
        if str(value).strip()
    }


def _normalised_name(candidate: Mapping[str, Any]) -> str:
    return "".join(
        character
        for character in str(candidate.get("strategy_name") or "").casefold()
        if character.isalpha()
    )


def _is_data_only_candidate(candidate: Mapping[str, Any]) -> bool:
    name = _normalised_name(candidate)
    types = _normalised_types(candidate)
    return name in _DATA_ONLY_NAMES or any(
        is_data_only_target(category=market_type) for market_type in types
    )


def _is_equity_candidate(candidate: Mapping[str, Any]) -> bool:
    name = _normalised_name(candidate)
    types = _normalised_types(candidate)
    return name in _EQUITY_NAMES or any(
        is_equity_index_target(category=market_type) for market_type in types
    )


def _research_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    row = deepcopy(dict(candidate))
    # A catalog row is inventory only.  These fields override any stale or
    # self-authored capability claim in the source report.
    row.update({
        "catalog_role": "research_candidate",
        "prediction_authority": False,
        "trade_proposal_authority": False,
        "execution_authority": False,
        "authority_reason": "catalog_inventory_requires_separate_promotion_evidence",
    })
    return row


def _quarantined_candidate(
    candidate: Mapping[str, Any],
    *,
    reason: str,
) -> dict[str, Any]:
    row = deepcopy(dict(candidate))
    row.update({
        "catalog_role": "quarantined_research_inventory",
        "output": "ABSTAIN",
        "prediction_authority": False,
        "trade_proposal_authority": False,
        "execution_authority": False,
        "quarantine_reason": reason,
    })
    return row


def sanitize_strategy_extraction_report(report: Any) -> dict[str, Any]:
    """Return a deterministic governed view of a v1/v2 extraction report."""
    source = dict(report) if isinstance(report, Mapping) else {}
    raw_candidates = source.get("candidates")
    candidates: list[dict[str, Any]] = []
    data_only: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    unknown_target_count = 0

    if isinstance(raw_candidates, list):
        for raw in raw_candidates:
            if not isinstance(raw, Mapping):
                unknown_target_count += 1
                continue
            if _is_data_only_candidate(raw):
                data_only.append(_quarantined_candidate(
                    raw,
                    reason="weather_or_commodity_context_only",
                ))
                continue
            if _is_equity_candidate(raw):
                quarantined.append(_quarantined_candidate(
                    raw,
                    reason="outside_supported_prediction_targets",
                ))
                continue
            if not _normalised_types(raw):
                unknown_target_count += 1
                continue
            candidates.append(_research_candidate(raw))

    for raw in source.get("quarantined_candidates") or []:
        if isinstance(raw, Mapping):
            quarantined.append(_quarantined_candidate(
                raw,
                reason="outside_supported_prediction_targets",
            ))
    for raw in source.get("data_only_inputs") or []:
        if isinstance(raw, Mapping):
            data_only.append(_quarantined_candidate(
                raw,
                reason="weather_or_commodity_context_only",
            ))

    return {
        "schema_version": STRATEGY_CATALOG_SCHEMA_VERSION,
        "policy_version": TARGET_POLICY_VERSION,
        "generated_at": source.get("generated_at"),
        "source_schema_version": source.get("schema_version", 1),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "data_only_input_count": len(data_only),
        "data_only_inputs": data_only,
        "quarantined_candidate_count": len(quarantined),
        "quarantined_candidates": quarantined,
        "unknown_target_excluded_count": unknown_target_count,
        "catalog_grants_prediction_authority": False,
        "catalog_grants_execution_authority": False,
        "data_status": "governed_stored_research_inventory",
    }


def resolve_strategy_catalog_path(root: Path) -> Path:
    directory = root / "artifacts" / "repo_harvester"
    current = directory / STRATEGY_CATALOG_FILENAME
    return current if current.exists() else directory / LEGACY_STRATEGY_CATALOG_FILENAME
