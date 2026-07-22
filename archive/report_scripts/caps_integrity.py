"""Separate archived caps evidence from current runtime caps integrity.

The V11-V19 reports are historical phase evidence.  A worktree diff observed
today cannot truthfully be attributed to one of those old phases.  This module
therefore validates a versioned historical evidence manifest and reports the
current runtime configuration independently.

Neither report grants execution authority or changes ``configs/caps.json``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CAPS_PATH = ROOT / "configs" / "caps.json"
DEFAULT_MANIFEST_PATH = ROOT / "archive" / "evidence" / "caps_history_v11_v19.json"

_MAXIMUM_CAP_FIELDS = {
    "max_single_order_cents",
    "max_market_exposure_cents",
    "max_daily_loss_cents",
    "max_total_live_exposure_cents",
    "max_open_markets",
    "max_orders_per_hour",
    "max_spread_cents",
}
_MINIMUM_SAFETY_FIELDS = {"min_liquidity", "min_edge_bps"}
_SAFE_BOOLEAN_VALUES = {
    "allow_market_orders": False,
    "limit_orders_only": True,
    "auto_cancel_stale_orders": True,
    "kill_switch_required": True,
}
_SEMANTIC_POLICY_FIELDS = {"allowed_markets", "blocked_categories"}
_AUTHORITY_MIGRATION_FIELDS = {
    "schema_version",
    "authority_epoch",
    "authority_registration_required",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _raw_sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _load_object(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [f"missing file: {path}"]
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, [f"unreadable JSON: {type(exc).__name__}"]
    if not isinstance(value, dict):
        return None, ["JSON root must be an object"]
    return value, []


def _validate_caps_shape(caps: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = _MAXIMUM_CAP_FIELDS | _MINIMUM_SAFETY_FIELDS | set(_SAFE_BOOLEAN_VALUES) | _SEMANTIC_POLICY_FIELDS
    missing = sorted(required - set(caps))
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")

    for field in sorted(_MAXIMUM_CAP_FIELDS | _MINIMUM_SAFETY_FIELDS):
        value = caps.get(field)
        if type(value) is not int or value <= 0:
            errors.append(f"{field} must be a positive integer")

    for field in sorted(_SAFE_BOOLEAN_VALUES):
        if type(caps.get(field)) is not bool:
            errors.append(f"{field} must be boolean")

    for field in sorted(_SEMANTIC_POLICY_FIELDS):
        value = caps.get(field)
        if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
            errors.append(f"{field} must be a list of non-empty strings")

    if (
        type(caps.get("max_single_order_cents")) is int
        and type(caps.get("max_market_exposure_cents")) is int
        and caps["max_single_order_cents"] > caps["max_market_exposure_cents"]
    ):
        errors.append("max_single_order_cents exceeds max_market_exposure_cents")
    if (
        type(caps.get("max_market_exposure_cents")) is int
        and type(caps.get("max_total_live_exposure_cents")) is int
        and caps["max_market_exposure_cents"] > caps["max_total_live_exposure_cents"]
    ):
        errors.append("max_market_exposure_cents exceeds max_total_live_exposure_cents")
    return errors


def _classify_change(field: str, baseline: Any, current: Any) -> str:
    if field in _MAXIMUM_CAP_FIELDS and type(baseline) is int and type(current) is int:
        return "WEAKENED" if current > baseline else "TIGHTENED"
    if field in _MINIMUM_SAFETY_FIELDS and type(baseline) is int and type(current) is int:
        return "WEAKENED" if current < baseline else "TIGHTENED"
    if field in _SAFE_BOOLEAN_VALUES:
        return "WEAKENED" if current != _SAFE_BOOLEAN_VALUES[field] else "TIGHTENED"
    if field in _SEMANTIC_POLICY_FIELDS:
        return "SEMANTIC_POLICY_CHANGE_REVIEW_REQUIRED"
    if field in _AUTHORITY_MIGRATION_FIELDS:
        return "CAPS_AUTHORITY_MIGRATION_REQUIRED"
    return "UNCLASSIFIED_REVIEW_REQUIRED"


def generate_current_runtime_caps_integrity_report(
    *,
    caps_path: Path = DEFAULT_CAPS_PATH,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> dict[str, Any]:
    """Report current caps validity and drift without rewriting history."""

    manifest, manifest_errors = _load_object(manifest_path)
    current, current_errors = _load_object(caps_path)
    baseline: dict[str, Any] | None = None
    if manifest is not None:
        candidate = manifest.get("historical_caps")
        if isinstance(candidate, dict):
            baseline = candidate
        else:
            manifest_errors.append("manifest historical_caps must be an object")

    validation_errors = list(current_errors)
    if current is not None:
        validation_errors.extend(_validate_caps_shape(current))

    changes: list[dict[str, Any]] = []
    if baseline is not None and current is not None:
        for field in sorted(set(baseline) | set(current)):
            before = baseline.get(field)
            after = current.get(field)
            if before != after:
                changes.append(
                    {
                        "field": field,
                        "historical_value": before,
                        "current_value": after,
                        "classification": _classify_change(field, before, after),
                    }
                )

    weakening_detected = any(change["classification"] == "WEAKENED" for change in changes)
    semantic_policy_review_required = any(
        change["classification"] == "SEMANTIC_POLICY_CHANGE_REVIEW_REQUIRED"
        for change in changes
    )
    authority_migration_required = any(
        change["classification"] == "CAPS_AUTHORITY_MIGRATION_REQUIRED"
        for change in changes
    )
    unclassified_review_required = any(
        change["classification"] == "UNCLASSIFIED_REVIEW_REQUIRED"
        for change in changes
    )
    review_required = (
        semantic_policy_review_required
        or authority_migration_required
        or unclassified_review_required
    )
    config_diff_empty = baseline is not None and current is not None and not changes
    if manifest_errors or validation_errors or weakening_detected:
        verdict = "FAIL"
    elif not config_diff_empty or review_required:
        verdict = "REVIEW_REQUIRED"
    else:
        verdict = "PASS"

    return {
        "generated_at": _now_iso(),
        "workstream": "Current Runtime Caps Config Integrity",
        "report_scope": "CURRENT_RUNTIME_CONFIG_ONLY",
        "caps_path": str(caps_path),
        "historical_manifest_path": str(manifest_path),
        "config_diff_empty": config_diff_empty,
        "config_changed_from_historical_baseline": not config_diff_empty,
        "current_caps_raw_sha256": _raw_sha256(caps_path),
        "current_caps_canonical_sha256": _canonical_sha256(current) if current is not None else None,
        "historical_caps_raw_sha256": manifest.get("historical_caps_raw_sha256") if manifest else None,
        "historical_caps_canonical_sha256": _canonical_sha256(baseline) if baseline is not None else None,
        "changes": changes,
        "weakening_detected": weakening_detected,
        "semantic_policy_review_required": semantic_policy_review_required,
        "authority_migration_required": authority_migration_required,
        "unclassified_review_required": unclassified_review_required,
        "config_valid": not validation_errors,
        "validation_errors": validation_errors,
        "manifest_errors": manifest_errors,
        "execution_authority": False,
        "verdict": verdict,
    }


def generate_historical_caps_phase_report(
    phase: str,
    *,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    caps_path: Path = DEFAULT_CAPS_PATH,
) -> dict[str, Any]:
    """Validate one immutable V11-V19 evidence record.

    The legacy ``config_diff_empty`` field is retained for old report readers,
    but its scope is now explicit.  Current drift is always exposed separately.
    """

    phase_id = phase.strip().upper()
    manifest, errors = _load_object(manifest_path)
    phase_record: dict[str, Any] | None = None
    baseline: dict[str, Any] | None = None
    if manifest is not None:
        if manifest.get("schema_version") != 1:
            errors.append("unsupported manifest schema_version")
        if manifest.get("record_kind") != "immutable_historical_caps_phase_evidence":
            errors.append("unexpected manifest record_kind")
        candidate = manifest.get("historical_caps")
        if isinstance(candidate, dict):
            baseline = candidate
            expected_hash = manifest.get("historical_caps_canonical_sha256")
            if _canonical_sha256(candidate) != expected_hash:
                errors.append("historical caps canonical hash mismatch")
            errors.extend(_validate_caps_shape(candidate))
        else:
            errors.append("manifest historical_caps must be an object")

        phases = manifest.get("phases")
        candidate_record = phases.get(phase_id) if isinstance(phases, dict) else None
        if isinstance(candidate_record, dict):
            phase_record = candidate_record
            if candidate_record.get("modified") is not False:
                errors.append(f"{phase_id} evidence does not record an unchanged caps config")
            digest = candidate_record.get("source_report_sha256")
            if not isinstance(digest, str) or len(digest) != 64:
                errors.append(f"{phase_id} source report digest is invalid")
            if not candidate_record.get("source_report_generated_at"):
                errors.append(f"{phase_id} source report timestamp is missing")
        else:
            errors.append(f"missing phase evidence: {phase_id}")

    historical_evidence_valid = not errors and phase_record is not None and baseline is not None
    modified_value: bool | None = False if historical_evidence_valid else None
    current_report = generate_current_runtime_caps_integrity_report(
        caps_path=caps_path,
        manifest_path=manifest_path,
    )
    modified_key = f"modified_by_{phase_id.lower()}"
    return {
        "generated_at": _now_iso(),
        "workstream": f"{phase_id}: No Caps Config Modification",
        "report_scope": "IMMUTABLE_HISTORICAL_PHASE_EVIDENCE",
        "historical_phase": phase_id,
        "historical_manifest_path": str(manifest_path),
        "historical_caps_raw_sha256": manifest.get("historical_caps_raw_sha256") if manifest else None,
        "historical_caps_canonical_sha256": _canonical_sha256(baseline) if baseline is not None else None,
        "historical_evidence": phase_record,
        "historical_evidence_valid": historical_evidence_valid,
        "historical_evidence_errors": errors,
        "config_diff_scope": "HISTORICAL_PHASE_BASELINE_ONLY",
        "config_diff_empty": historical_evidence_valid,
        modified_key: modified_value,
        "current_runtime_config_diff_empty": current_report["config_diff_empty"],
        "current_runtime_integrity_verdict": current_report["verdict"],
        "current_runtime_integrity": current_report,
        "execution_authority": False,
        "verdict": "PASS" if historical_evidence_valid else "FAIL",
    }


def reconcile_v17_truth_loop_evidence(
    final_report: dict[str, Any],
    *,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    caps_path: Path = DEFAULT_CAPS_PATH,
) -> dict[str, Any]:
    """Reconcile an archived V17 aggregate without hiding current caps drift.

    A V17 aggregate that failed only because a later worktree diff was
    retroactively attributed to V17 can be recovered from the immutable V17
    caps record.  Any non-caps failure, missing evidence, or inconsistent
    unexplained failure remains fail-closed.
    """

    caps_report_name = "no_caps_config_modification_report_v17.json"
    historical_caps = generate_historical_caps_phase_report(
        "V17",
        manifest_path=manifest_path,
        caps_path=caps_path,
    )
    current_caps = historical_caps["current_runtime_integrity"]

    if not final_report:
        return {
            "historical_truth_loop_status": "UNKNOWN",
            "historical_truth_loop_scope": "IMMUTABLE_V17_PHASE_EVIDENCE",
            "archived_aggregate_verdict": "UNKNOWN",
            "historical_caps_status": historical_caps["verdict"],
            "current_runtime_caps_status": current_caps["verdict"],
            "current_runtime_config_diff_empty": current_caps["config_diff_empty"],
            "archived_failures": [],
            "non_caps_failures": [],
            "retroactive_caps_failure_reconciled": False,
            "reason": "V17 final report is unavailable",
            "execution_authority": False,
        }

    artifact_verdict = str(final_report.get("verdict", "UNKNOWN")).upper()
    report_verdicts = final_report.get("report_verdicts")
    failed_reports = {
        str(name)
        for name, verdict in (report_verdicts.items() if isinstance(report_verdicts, dict) else [])
        if str(verdict).upper() == "FAIL"
    }
    listed_failures = final_report.get("failures")
    if isinstance(listed_failures, list):
        failed_reports.update(str(name) for name in listed_failures)

    non_caps_failures = sorted(failed_reports - {caps_report_name})
    caps_only_failure = failed_reports == {caps_report_name}
    historical_caps_passed = historical_caps["verdict"] == "PASS"

    if non_caps_failures:
        historical_status = "FAIL"
        reason = "V17 aggregate contains non-caps failures"
        reconciled = False
    elif caps_only_failure and historical_caps_passed:
        historical_status = "PASS"
        reason = "V17 aggregate failure was isolated to retroactive current caps drift; immutable V17 caps evidence passed"
        reconciled = True
    elif artifact_verdict == "PASS" and not failed_reports:
        historical_status = "PASS"
        reason = "V17 archived aggregate passed with no failed component reports"
        reconciled = False
    elif artifact_verdict in {"PARTIAL", "UNKNOWN"} and not failed_reports:
        historical_status = artifact_verdict
        reason = "V17 archived aggregate did not contain a failed component report"
        reconciled = False
    else:
        historical_status = "FAIL"
        reason = "V17 aggregate failure could not be reconciled from immutable caps evidence"
        reconciled = False

    return {
        "historical_truth_loop_status": historical_status,
        "historical_truth_loop_scope": "IMMUTABLE_V17_PHASE_EVIDENCE",
        "archived_aggregate_verdict": artifact_verdict,
        "historical_caps_status": historical_caps["verdict"],
        "current_runtime_caps_status": current_caps["verdict"],
        "current_runtime_config_diff_empty": current_caps["config_diff_empty"],
        "archived_failures": sorted(failed_reports),
        "non_caps_failures": non_caps_failures,
        "retroactive_caps_failure_reconciled": reconciled,
        "reason": reason,
        "execution_authority": False,
    }


__all__ = [
    "DEFAULT_CAPS_PATH",
    "DEFAULT_MANIFEST_PATH",
    "generate_current_runtime_caps_integrity_report",
    "generate_historical_caps_phase_report",
    "reconcile_v17_truth_loop_evidence",
]
