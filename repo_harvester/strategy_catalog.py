"""Governed, local-only view of the repo harvester's strategy inventory.

Legacy extraction reports are research inventory, not capability manifests.
This sanitizer is applied both when reports are produced and when an older
report is read, so stale ``v1`` rows cannot regain prediction authority merely
because the harvester has not been rerun.  It performs no network calls and
writes nothing.

Wave-84 (2026-07-24 external audit, section 6): the harvester's rows are
keyword-counter templates, not extracted repo logic.  A row is treated as a
repo-derived candidate ONLY if it explicitly declares ``repo_derived_logic:
true``; everything else is reported as ``keyword_template_inventory`` and never
counted as an extracted candidate.  A stale ``v1`` artifact -- whose rows
predate the label -- therefore de-inflates to zero candidates on read instead
of presenting template fan-out as extraction.
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


STRATEGY_CATALOG_SCHEMA_VERSION = 3
STRATEGY_CATALOG_FILENAME = "strategy_extraction_report_v2.json"
LEGACY_STRATEGY_CATALOG_FILENAME = "strategy_extraction_report_v1.json"
# Schema of the report the harvester WRITES (the catalog is the governed READ
# view of it). Both live here so emitter and reader cannot drift.
STRATEGY_REPORT_SCHEMA_VERSION = 2
KEYWORD_TEMPLATE_DERIVATION = "keyword_template_not_repo_derived"
KEYWORD_TEMPLATE_EXTRACTION_METHOD = "manifest_keyword_counter_fan_out"

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


def _is_repo_derived(candidate: Mapping[str, Any]) -> bool:
    """Only an explicit, positive provenance claim counts as repo-derived.

    Absence of the label means the row came from the keyword-template fan-out
    (every row the harvester has ever emitted), so it fails closed.
    """
    return candidate.get("repo_derived_logic") is True


def _keyword_template_row(candidate: Mapping[str, Any]) -> dict[str, Any]:
    row = deepcopy(dict(candidate))
    row.update({
        "catalog_role": "keyword_template_inventory",
        "derivation": KEYWORD_TEMPLATE_DERIVATION,
        "repo_derived_logic": False,
        "output": "ABSTAIN",
        "prediction_authority": False,
        "trade_proposal_authority": False,
        "execution_authority": False,
        "authority_reason": "keyword_template_row_is_not_an_extracted_strategy",
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
    keyword_templates: list[dict[str, Any]] = []
    data_only: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    unknown_target_count = 0

    raw_rows: list[Any] = list(raw_candidates) if isinstance(raw_candidates, list) else []
    raw_inventory = source.get("keyword_template_inventory")
    if isinstance(raw_inventory, list):
        raw_rows.extend(raw_inventory)

    if isinstance(raw_candidates, list):
        for raw in raw_rows:
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
            if not _is_repo_derived(raw):
                keyword_templates.append(_keyword_template_row(raw))
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
        # Repo-derived, extracted candidates only. Keyword-template rows are
        # reported separately and are never counted here.
        "candidate_count": len(candidates),
        "candidates": candidates,
        "repo_derived_candidate_count": len(candidates),
        "keyword_template_inventory_count": len(keyword_templates),
        "keyword_template_inventory": keyword_templates,
        "count_semantics": (
            "candidate_count counts rows that declare repo_derived_logic. "
            "Keyword-counter template rows are inventory, never extractions."
        ),
        "data_only_input_count": len(data_only),
        "data_only_inputs": data_only,
        "quarantined_candidate_count": len(quarantined),
        "quarantined_candidates": quarantined,
        "unknown_target_excluded_count": unknown_target_count,
        "catalog_grants_prediction_authority": False,
        "catalog_grants_execution_authority": False,
        "data_status": "governed_stored_research_inventory",
    }


def relabel_legacy_report(
    report: Any,
    *,
    source_filename: str = LEGACY_STRATEGY_CATALOG_FILENAME,
) -> dict[str, Any]:
    """Re-label a stale v1 extraction report as the inventory it always was.

    Pure and offline: no repo is re-scanned and no row is invented or dropped.
    Legacy rows carry no provenance label, so they fail closed into
    ``keyword_template_inventory`` and the headline ``candidate_count`` becomes
    the number of rows that actually declare repo-derived logic (0 for every
    report the harvester has produced to date).
    """
    governed = sanitize_strategy_extraction_report(report)
    source = dict(report) if isinstance(report, Mapping) else {}
    return {
        "schema_version": STRATEGY_REPORT_SCHEMA_VERSION,
        "generated_at": source.get("generated_at"),
        "extraction_method": KEYWORD_TEMPLATE_EXTRACTION_METHOD,
        "inventory_only": True,
        "repo_derived_extraction_implemented": False,
        "candidate_count": governed["candidate_count"],
        "candidates": governed["candidates"],
        "repo_derived_candidate_count": governed["repo_derived_candidate_count"],
        "keyword_template_inventory_count": governed[
            "keyword_template_inventory_count"
        ],
        "keyword_template_inventory": governed["keyword_template_inventory"],
        "data_only_input_count": governed["data_only_input_count"],
        "data_only_inputs": governed["data_only_inputs"],
        "quarantined_candidate_count": governed["quarantined_candidate_count"],
        "quarantined_candidates": governed["quarantined_candidates"],
        "unknown_target_excluded_count": governed["unknown_target_excluded_count"],
        "relabelled_from": source_filename,
        "relabelled_without_rescan": True,
        "reported_candidate_count_before_relabel": source.get("candidate_count"),
        "count_semantics": governed["count_semantics"],
        "notes": (
            "Provenance relabel only (2026-07-24 audit, section 6). The rows "
            "are unchanged; the previous headline counted keyword-counter "
            "template emissions as extracted repo-derived candidates."
        ),
    }


def resolve_strategy_catalog_path(root: Path) -> Path:
    directory = root / "artifacts" / "repo_harvester"
    current = directory / STRATEGY_CATALOG_FILENAME
    return current if current.exists() else directory / LEGACY_STRATEGY_CATALOG_FILENAME
