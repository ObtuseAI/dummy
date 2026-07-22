from __future__ import annotations

import json

import pytest

from archive.report_scripts.caps_integrity import (
    DEFAULT_CAPS_PATH,
    DEFAULT_MANIFEST_PATH,
    generate_current_runtime_caps_integrity_report,
    generate_historical_caps_phase_report,
    reconcile_v17_truth_loop_evidence,
)


@pytest.mark.parametrize("phase", [f"V{version}" for version in range(11, 20)])
def test_historical_phase_evidence_is_not_rewritten_by_current_runtime_drift(phase: str) -> None:
    report = generate_historical_caps_phase_report(phase)

    assert report["report_scope"] == "IMMUTABLE_HISTORICAL_PHASE_EVIDENCE"
    assert report["config_diff_scope"] == "HISTORICAL_PHASE_BASELINE_ONLY"
    assert report["config_diff_empty"] is True
    assert report[f"modified_by_{phase.lower()}"] is False
    assert report["verdict"] == "PASS"

    assert report["current_runtime_config_diff_empty"] is False
    assert report["current_runtime_integrity_verdict"] == "REVIEW_REQUIRED"
    assert report["current_runtime_integrity"]["execution_authority"] is False


def test_current_runtime_report_discloses_semantic_block_category_change() -> None:
    report = generate_current_runtime_caps_integrity_report()

    assert report["report_scope"] == "CURRENT_RUNTIME_CONFIG_ONLY"
    assert report["config_valid"] is True
    assert report["config_diff_empty"] is False
    assert report["weakening_detected"] is False
    assert report["semantic_policy_review_required"] is True
    assert report["authority_migration_required"] is True
    assert report["unclassified_review_required"] is False
    assert report["verdict"] == "REVIEW_REQUIRED"
    assert report["changes"] == [
        {
            "field": "authority_epoch",
            "historical_value": None,
            "current_value": "caps-v2-kalshi-category-metadata-20260722",
            "classification": "CAPS_AUTHORITY_MIGRATION_REQUIRED",
        },
        {
            "field": "authority_registration_required",
            "historical_value": None,
            "current_value": True,
            "classification": "CAPS_AUTHORITY_MIGRATION_REQUIRED",
        },
        {
            "field": "blocked_categories",
            "historical_value": ["politics-elections-us", "sensitive-geo"],
            "current_value": ["Elections", "Politics"],
            "classification": "SEMANTIC_POLICY_CHANGE_REVIEW_REQUIRED",
        },
        {
            "field": "schema_version",
            "historical_value": None,
            "current_value": 2,
            "classification": "CAPS_AUTHORITY_MIGRATION_REQUIRED",
        },
    ]


def test_current_runtime_report_fails_closed_on_weakened_numeric_cap(tmp_path) -> None:
    caps = json.loads(DEFAULT_CAPS_PATH.read_text(encoding="utf-8"))
    caps["max_single_order_cents"] = 101
    caps_path = tmp_path / "caps.json"
    caps_path.write_text(json.dumps(caps), encoding="utf-8")

    report = generate_current_runtime_caps_integrity_report(caps_path=caps_path)

    assert report["weakening_detected"] is True
    assert report["verdict"] == "FAIL"
    assert any(
        change["field"] == "max_single_order_cents" and change["classification"] == "WEAKENED"
        for change in report["changes"]
    )


def test_historical_report_fails_closed_when_manifest_baseline_is_tampered(tmp_path) -> None:
    manifest = json.loads(DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["historical_caps"]["max_single_order_cents"] = 999
    manifest_path = tmp_path / "caps_history.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = generate_historical_caps_phase_report("V11", manifest_path=manifest_path)

    assert report["historical_evidence_valid"] is False
    assert report["modified_by_v11"] is None
    assert report["verdict"] == "FAIL"
    assert "historical caps canonical hash mismatch" in report["historical_evidence_errors"]


def test_v17_truth_loop_reconciles_only_a_retroactive_caps_failure() -> None:
    evidence = reconcile_v17_truth_loop_evidence(
        {
            "verdict": "FAIL",
            "failures": ["no_caps_config_modification_report_v17.json"],
            "report_verdicts": {"no_caps_config_modification_report_v17.json": "FAIL"},
        }
    )

    assert evidence["historical_truth_loop_status"] == "PASS"
    assert evidence["archived_aggregate_verdict"] == "FAIL"
    assert evidence["historical_caps_status"] == "PASS"
    assert evidence["current_runtime_caps_status"] == "REVIEW_REQUIRED"
    assert evidence["current_runtime_config_diff_empty"] is False
    assert evidence["retroactive_caps_failure_reconciled"] is True
    assert evidence["execution_authority"] is False


def test_v17_truth_loop_preserves_non_caps_failures() -> None:
    evidence = reconcile_v17_truth_loop_evidence(
        {
            "verdict": "FAIL",
            "failures": [
                "no_caps_config_modification_report_v17.json",
                "outcome_ledger_integrity_report_v1.json",
            ],
            "report_verdicts": {
                "no_caps_config_modification_report_v17.json": "FAIL",
                "outcome_ledger_integrity_report_v1.json": "FAIL",
            },
        }
    )

    assert evidence["historical_truth_loop_status"] == "FAIL"
    assert evidence["non_caps_failures"] == ["outcome_ledger_integrity_report_v1.json"]
    assert evidence["retroactive_caps_failure_reconciled"] is False
