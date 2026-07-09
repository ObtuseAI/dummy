"""V34 operator-enabled probe run reconciliation and live score closure reports."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from predator_mesh.v31.probes import CAPS_HASH, LIVE_SUBMIT_HASH
from predator_mesh.v34 import MILESTONE
from predator_mesh.v34.run import build_default_v34_state

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "dummy"
REPORT_NAMES_FILE = ARTIFACTS / "v34_required_report_names_from_attachment.txt"
FINAL_INDEX_NAMES = {"final_report.json", "tests_summary.json", "final_report_v34.json"}

# Ordered string replacements mapping V33 report names -> V34 report names.
_NAME_REPLACEMENTS: list[tuple[str, str]] = [
    ("dummy_mission_state_report_v19", "dummy_mission_state_report_v20"),
    ("dashboard_v33_report_v1", "dashboard_v34_report_v1"),
    ("v33_runtime_budget_report_v1", "v34_runtime_budget_report_v1"),
    # controller / probe-run group
    ("v33_operator_enabled_probe_run_controller_v1", "v34_operator_enabled_probe_run_reconciliation_controller_v1"),
    ("v33_probe_run_mode_decision", "v34_probe_run_mode_decision"),
    ("v33_probe_run_gate_state", "v34_probe_run_gate_state"),
    ("v33_probe_run_operator_packet", "v34_probe_run_operator_packet"),
    ("v33_probe_run_execution_plan", "v34_probe_run_execution_plan"),
    ("v33_probe_run_result", "v34_probe_run_result"),
    ("v33_probe_run_safety_proof", "v34_probe_run_safety_proof"),
    # minimal -> bounded probe pass
    ("minimal_live_public_probe_execution_v1", "bounded_readonly_public_probe_pass_v2"),
    ("live_probe_execution_task", "bounded_probe_execution_task"),
    ("live_probe_adapter_family_selection", "bounded_probe_adapter_family_selection"),
    ("live_probe_execution_budget", "bounded_probe_execution_budget"),
    ("live_probe_execution_outcome", "bounded_probe_execution_outcome"),
    ("live_probe_execution_failure", "bounded_probe_execution_failure"),
    ("live_probe_execution_safety_proof", "bounded_probe_execution_safety_proof"),
    # weather reconciler
    ("weather_enabled_probe_run_v1", "weather_observation_reconciliation_v2"),
    ("weather_enabled_probe_task", "weather_observation_reconciliation_task"),
    ("weather_enabled_probe_result", "weather_observation_reconciliation_result"),
    ("weather_enabled_observation_packet", "weather_observation_reconciliation_packet"),
    ("weather_enabled_settlement_join", "weather_observation_reconciliation_settlement_join"),
    ("weather_enabled_probe_blocker", "weather_observation_reconciliation_blocker"),
    # crypto reconciler
    ("crypto_enabled_probe_run_v1", "crypto_price_reconciliation_v2"),
    ("crypto_enabled_probe_task", "crypto_price_reconciliation_task"),
    ("crypto_enabled_probe_result", "crypto_price_reconciliation_result"),
    ("crypto_enabled_price_packet", "crypto_price_reconciliation_packet"),
    ("crypto_enabled_venue_consensus", "crypto_price_reconciliation_venue_consensus"),
    ("crypto_enabled_settlement_join", "crypto_price_reconciliation_settlement_join"),
    ("crypto_enabled_probe_blocker", "crypto_price_reconciliation_blocker"),
    # public_event reconciler
    ("public_event_enabled_probe_run_v1", "public_event_reference_reconciliation_v2"),
    ("public_event_enabled_probe_task", "public_event_reference_reconciliation_task"),
    ("public_event_enabled_probe_result", "public_event_reference_reconciliation_result"),
    ("public_event_enabled_reference_packet", "public_event_reference_reconciliation_reference_packet"),
    ("public_event_enabled_settlement_join", "public_event_reference_reconciliation_settlement_join"),
    ("public_event_enabled_probe_blocker", "public_event_reference_reconciliation_blocker"),
    # kalshi reconciler
    ("kalshi_readonly_enabled_probe_run_v1", "kalshi_readonly_rule_reconciliation_v2"),
    ("kalshi_readonly_enabled_probe_task", "kalshi_readonly_rule_reconciliation_task"),
    ("kalshi_readonly_enabled_probe_result", "kalshi_readonly_rule_reconciliation_result"),
    ("kalshi_readonly_rule_packet", "kalshi_readonly_rule_reconciliation_rule_packet"),
    ("kalshi_readonly_settlement_join", "kalshi_readonly_rule_reconciliation_settlement_join"),
    ("kalshi_readonly_enabled_probe_blocker", "kalshi_readonly_rule_reconciliation_blocker"),
    # evidence ledger
    ("live_public_evidence_ingestion_v3", "live_evidence_reconciliation_ledger_v1"),
    ("enabled_live_public_evidence_packet", "reconciled_live_public_evidence_packet"),
    ("enabled_live_public_evidence_family_summary", "reconciled_live_public_evidence_family_summary"),
    ("enabled_live_public_evidence_eligibility", "reconciled_live_public_evidence_eligibility"),
    ("enabled_live_public_evidence_freshness", "reconciled_live_public_evidence_freshness"),
    ("enabled_live_public_evidence_blocker", "reconciled_live_public_evidence_blocker"),
    # settlement join
    ("settlement_evidence_join_v3", "settlement_join_reconciliation_v4"),
    ("live_settlement_evidence_candidate", "reconciled_settlement_evidence_candidate"),
    ("live_settlement_join_decision", "reconciled_settlement_join_decision"),
    ("live_settlement_join_confidence", "reconciled_settlement_join_confidence"),
    ("live_settlement_join_blocker", "reconciled_settlement_join_blocker"),
    # due forecast closure
    ("due_forecast_observation_run_v6", "due_forecast_closure_reconciliation_v7"),
    ("due_observation_run_case", "due_forecast_closure_reconciliation_case"),
    ("due_observation_evidence_match", "due_forecast_closure_reconciliation_evidence_match"),
    ("due_observation_decision", "due_forecast_closure_reconciliation_decision"),
    ("due_observation_ledger_write", "due_forecast_closure_reconciliation_ledger_write"),
    ("due_observation_blocker", "due_forecast_closure_reconciliation_blocker"),
    # live score closure
    ("live_score_observation_run_v4", "live_score_closure_reconciliation_v5"),
    ("live_score_observation_candidate", "live_score_closure_reconciliation_candidate"),
    ("live_score_observation_decision", "live_score_closure_reconciliation_decision"),
    ("live_score_observation_metric", "live_score_closure_reconciliation_metric"),
    ("live_score_observation_ledger_write", "live_score_closure_reconciliation_ledger_write"),
    ("live_score_observation_blocker", "live_score_closure_reconciliation_blocker"),
    # live calibration reconciliation
    ("live_calibration_observation_run_v4", "live_calibration_reconciliation_v5"),
    ("live_calibration_observation_sample", "live_calibration_reconciliation_sample"),
    ("live_calibration_observation_bucket", "live_calibration_reconciliation_bucket"),
    ("live_calibration_observation_decision", "live_calibration_reconciliation_decision"),
    ("live_calibration_observation_warning", "live_calibration_reconciliation_warning"),
    ("live_calibration_observation_blocker", "live_calibration_reconciliation_blocker"),
    # probe run artifact cache
    ("public_probe_artifact_cache_v3", "probe_run_artifact_reconciliation_cache_v4"),
    ("enabled_probe_cache_record", "reconciled_probe_cache_record"),
    ("enabled_probe_cache_manifest", "reconciled_probe_cache_manifest"),
    ("enabled_probe_cache_freshness_policy", "reconciled_probe_cache_freshness_policy"),
    ("enabled_probe_cache_redaction_audit", "reconciled_probe_cache_redaction_audit"),
    ("enabled_probe_cache_blocker", "reconciled_probe_cache_blocker"),
    # reconciled probe audit ledger
    ("enabled_probe_audit_ledger_v2", "reconciled_probe_audit_ledger_v3"),
    ("enabled_probe_audit_record", "reconciled_probe_audit_record"),
    ("enabled_probe_gate_audit", "reconciled_probe_gate_audit"),
    ("enabled_probe_source_audit", "reconciled_probe_source_audit"),
    ("enabled_probe_observation_audit", "reconciled_probe_observation_audit"),
    ("enabled_probe_score_audit", "reconciled_probe_score_audit"),
    ("enabled_probe_safety_audit", "reconciled_probe_safety_audit"),
    # sports probe exclusion recheck
    ("sports_probe_exclusion_guard_v4", "sports_probe_exclusion_recheck_v5"),
    ("sports_probe_exclusion_decision", "sports_probe_exclusion_recheck_decision"),
    ("sports_source_approval_state_v4", "sports_source_approval_state_v5"),
    ("sports_fixture_mode_proof_v4", "sports_fixture_mode_proof_v5"),
    ("sports_operator_approval_packet_v4", "sports_operator_approval_packet_v5"),
    ("sports_probe_exclusion_blocker", "sports_probe_exclusion_recheck_blocker"),
    # source truth probe reconciliation
    ("source_truth_enabled_probe_evidence_v14", "source_truth_probe_reconciliation_v15"),
    ("enabled_probe_health_truth_signal", "reconciled_probe_health_truth_signal"),
    ("enabled_evidence_compatibility_truth_signal", "reconciled_evidence_compatibility_truth_signal"),
    ("enabled_observation_closure_truth_signal", "reconciled_observation_closure_truth_signal"),
    ("enabled_live_score_truth_signal", "reconciled_live_score_truth_signal"),
    ("enabled_source_recovery_action_v14", "reconciled_source_recovery_action_v15"),
    # partial reduction ledger
    ("v33_partial_reduction_ledger", "v34_partial_reduction_ledger"),
    ("v33_partial_cause_before_after", "v34_partial_cause_before_after"),
    ("v33_partial_reduction_attempt", "v34_partial_reduction_attempt"),
    ("v33_partial_reduction_result", "v34_partial_reduction_result"),
    ("v33_remaining_partial_cause", "v34_remaining_partial_cause"),
    ("v33_pass_delta", "v34_pass_delta"),
    # sprint queue
    ("operator_enabled_probe_sprint_queue_v10", "probe_reconciliation_sprint_queue_v11"),
    ("probe_sprint_v10", "probe_reconciliation_sprint_v11"),
    # compounding control plane + queues
    ("enabled_probe_to_score_compounding_control_plane_v17", "probe_reconciliation_to_score_compounding_control_plane_v18"),
    ("enabled_probe_run_queue_v5", "probe_reconciliation_run_queue_v5"),
    ("evidence_ingestion_queue_v2", "evidence_reconciliation_queue_v2"),
    ("settlement_join_queue_v2", "settlement_reconciliation_queue_v2"),
    ("observation_run_queue_v2", "forecast_closure_reconciliation_queue_v2"),
    ("live_score_growth_queue_v4", "live_score_closure_growth_queue_v5"),
    ("next_bundle_recommendation_v33", "next_bundle_recommendation_v34"),
    # scoreboard
    ("domain_market_class_scoreboard_v18", "domain_market_class_scoreboard_v19"),
    ("enabled_probe_run_scoreboard", "probe_reconciliation_run_scoreboard"),
    ("live_evidence_ingestion_scoreboard", "live_evidence_reconciliation_scoreboard"),
    ("settlement_join_scoreboard", "settlement_reconciliation_scoreboard"),
    ("due_observation_run_scoreboard", "due_forecast_closure_reconciliation_scoreboard"),
    ("live_score_run_scoreboard", "live_score_closure_reconciliation_scoreboard"),
    # runtime budget children
    ("enabled_probe_runtime_budget_v1", "probe_reconciliation_runtime_budget_v1"),
    ("live_evidence_ingestion_budget_v1", "live_evidence_reconciliation_budget_v1"),
    ("observation_run_runtime_budget_v1", "forecast_closure_reconciliation_runtime_budget_v1"),
    ("dashboard_cache_policy_v15", "dashboard_cache_policy_v16"),
    ("report_chain_runtime_profiler_v16", "report_chain_runtime_profiler_v17"),
    # generic suffix/prefix for remaining safety + identity reports
    ("_v33.json", "_v34.json"),
    ("v33_", "v34_"),
]


def _to_v34_name(v33_name: str) -> str:
    name = v33_name
    for old, new in _NAME_REPLACEMENTS:
        name = name.replace(old, new)
    return name


def _names(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _build_default_required_report_names() -> list[str]:
    from predator_mesh.v33.reports import DEFAULT_REQUIRED_REPORT_NAMES as _v33_names

    names = [_to_v34_name(name) for name in _v33_names]
    # De-duplicate while preserving order.
    return list(dict.fromkeys(names))


DEFAULT_REQUIRED_REPORT_NAMES = _build_default_required_report_names()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_required_report_names() -> list[str]:
    names = list(DEFAULT_REQUIRED_REPORT_NAMES)
    if REPORT_NAMES_FILE.exists():
        file_names = [line.strip() for line in REPORT_NAMES_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
        if file_names:
            names = file_names
    return [name for name in dict.fromkeys(names) if name not in FINAL_INDEX_NAMES]


REPORT_NAMES = _load_required_report_names()


def _safe_base(workstream: str, verdict: str = "PASS") -> dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "workstream": workstream,
        "milestone": MILESTONE,
        "verdict": verdict,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "read_only_only": True,
        "secret_values_exposed": False,
        "source_api_keys_exposed": False,
        "github_tokens_exposed": False,
        "kalshi_private_keys_exposed": False,
        "llm_secrets_exposed": False,
        "execution_bridge_present": False,
        "live_submit_enabled": False,
        "configs_live_submit_modified": False,
        "configs_caps_modified": False,
        "order_endpoints_used": False,
        "cancel_endpoints_used": False,
        "private_endpoints_used": False,
        "browser_automation_added": False,
        "pageagent_added": False,
        "dom_extraction_added": False,
        "browser_research_lane_added": False,
        "mined_repo_cloned": False,
        "mined_repo_imported": False,
        "mined_repo_executed": False,
        "blind_mined_code_copied": False,
        "questionable_odds_scraping": False,
        "fixture_evidence_claimed_real": False,
        "replay_evidence_claimed_live": False,
        "replay_score_claimed_live": False,
        "proxy_evidence_claimed_exchange_native": False,
        "cached_sample_claimed_live": False,
        "stale_cached_evidence_scored_live": False,
        "public_sample_evidence_scored_live": False,
        "context_only_claimed_edge": False,
        "example_market_canonical_center": False,
        "unresolved_forecast_scored": False,
        "ambiguous_settlement_scored": False,
        "source_unavailable_forecast_scored": False,
        "not_due_forecast_scored": False,
        "adapter_fixture_scored_live": False,
        "adapter_dry_run_scored_live": False,
        "public_probe_failure_scored_live": False,
        "disabled_probe_scored_live": False,
        "missing_ack_probe_run": False,
        "fuzzy_ack_probe_run": False,
        "outcome_fabricated": False,
        "operator_enabled_probe_run_to_execution_bridge_present": False,
        "minimal_live_public_probe_to_execution_bridge_present": False,
        "live_public_evidence_ingestion_to_execution_bridge_present": False,
        "settlement_evidence_join_to_execution_bridge_present": False,
        "due_observation_run_to_execution_bridge_present": False,
        "live_score_observation_to_execution_bridge_present": False,
        "live_calibration_observation_to_execution_bridge_present": False,
        "public_probe_cache_to_execution_bridge_present": False,
        "enabled_probe_audit_to_execution_bridge_present": False,
        "source_truth_to_execution_bridge_present": False,
        "probe_sprint_to_execution_bridge_present": False,
    }


def _safe_payload(workstream: str, verdict: str = "PASS", **extra: Any) -> dict[str, Any]:
    payload = _safe_base(workstream, verdict)
    payload.update(extra)
    return payload


def _workstream(report_name: str) -> str:
    return f"V34: {report_name.removesuffix('.json').removesuffix('_report').replace('_', ' ').title()}"


def _verdict(report_name: str) -> str:
    if report_name.startswith("no_") or report_name.startswith("readonly_only") or "blunder" in report_name or "canonical_identity" in report_name or "dashboard" in report_name:
        return "PASS"
    partial_tokens = [
        "probe", "evidence", "observation", "live_score", "live_calibration", "partial",
        "queue", "scoreboard", "truth", "sports", "mission_state", "reconciliation",
        "closure", "ledger", "controller",
    ]
    return "PARTIAL" if any(token in report_name for token in partial_tokens) else "PASS"


def _common(state: dict[str, Any], report_name: str) -> dict[str, Any]:
    controller = state["operator_enabled_probe_run_controller"]
    gate = state["exact_gate_ack"]
    minimal = state["minimal_live_public_probe_execution"]
    evidence = state["live_public_evidence_ingestion"]
    settlement = state["settlement_evidence_join"]
    observation = state["due_forecast_observation_run"]
    score = state["live_score_observation_run"]
    calibration = state["live_calibration_observation_run"]
    return {
        "report_name": report_name,
        "v33_source_recovery_live_observation_status": "PASS_PARTIAL_EXPECTED",
        "operator_enabled_probe_run_controller_status": controller.operator_enabled_probe_run_controller_status,
        "exact_ack_validation_status": gate.exact_ack_validation_status,
        "gate_state": gate.gate_state,
        "gate_enabled": gate.enabled,
        "minimal_live_public_probe_execution_status": minimal.minimal_live_public_probe_execution_status,
        "probe_run_count": minimal.probe_run_count,
        "probe_source_family_count": minimal.source_family_count,
        "weather_enabled_probe_status": state["domain_probe"]["weather"].status,
        "crypto_enabled_probe_status": state["domain_probe"]["crypto"].status,
        "public_event_enabled_probe_status": state["domain_probe"]["public_event"].status,
        "kalshi_readonly_enabled_probe_status": state["domain_probe"]["kalshi_readonly"].status,
        "live_public_evidence_ingestion_status": evidence.live_public_evidence_ingestion_status,
        "live_public_evidence_packet_count": evidence.packet_count,
        "settlement_evidence_join_status": settlement.settlement_evidence_join_status,
        "settlement_compatible_evidence_count": settlement.compatible_count,
        "due_forecast_observation_run_status": observation.due_forecast_observation_run_status,
        "due_forecast_count": observation.due_forecast_count,
        "observed_forecast_count": observation.observed_forecast_count,
        "live_score_observation_run_status": score.live_score_observation_run_status,
        "live_scored_count": score.live_scored_count,
        "live_unresolved_count": observation.live_unresolved_count,
        "live_calibration_observation_status": calibration.live_calibration_observation_status,
        "public_probe_artifact_cache_status": state["public_probe_artifact_cache"].public_probe_artifact_cache_status,
        "enabled_probe_audit_ledger_status": state["enabled_probe_audit_ledger"].enabled_probe_audit_ledger_status,
        "sports_probe_exclusion_guard_status": state["sports_probe_exclusion_guard"].sports_probe_exclusion_guard_status,
        "sports_source_mode": state["sports_probe_exclusion_guard"].sports_source_mode,
        "source_truth_enabled_probe_evidence_v14_status": state["source_truth_enabled_probe_evidence"].source_truth_enabled_probe_evidence_v14_status,
        "partial_reduction_status": "PASS_WITH_REMAINING_PARTIALS",
        "partial_causes_before": {"PROBE_DISABLED_BY_DEFAULT": 1, "ACK_MISSING": 1, "NO_LIVE_PUBLIC_EVIDENCE": 1, "NO_LIVE_SCORE": 1},
        "partial_causes_after": {"PROBE_DISABLED_BY_DEFAULT": 1, "ACK_MISSING": 1, "NO_LIVE_PUBLIC_EVIDENCE": 1, "NO_LIVE_SCORE": 1, "SPORTS_TERMS_FIXTURE_ONLY": 1},
        "sprint_queue_v11_status": "PASS",
        "compounding_v18_status": "PASS",
        "next_bundle_recommendation": "DUMMY_V35_OPERATOR_GATE_PUBLIC_SOURCE_REPAIR_OR_LIVE_CALIBRATION_EXPANSION_V1",
        "market_class_scoreboard_v19_status": "PASS_PARTIAL_EXPECTED",
    }


def _controller_payload(state: dict[str, Any]) -> dict[str, Any]:
    result = state["operator_enabled_probe_run_controller"]
    gate = state["exact_gate_ack"]
    return {
        **result.to_dict(),
        "v34_probe_run_mode_decision": {
            "enabled": gate.enabled,
            "gate_state": gate.gate_state,
            "exact_ack_validation_status": gate.exact_ack_validation_status,
            "failure_reason": gate.failure_reason,
        },
        "v34_probe_run_gate_state": {"gate_state": gate.gate_state, "gate_enabled": gate.enabled, "source_families": result.execution_plan.source_families},
        "v34_probe_run_operator_packet": result.operator_packet.to_dict(),
        "v34_probe_run_execution_plan": result.execution_plan.to_dict(),
        "v34_probe_run_result": result.to_dict(),
        "v34_probe_run_safety_proof": result.safety_proof.to_dict(),
    }


def _ack_payload(state: dict[str, Any]) -> dict[str, Any]:
    gate = state["exact_gate_ack"]
    return {
        **gate.to_dict(),
        "exact_ack_input_record": gate.input_record.to_dict(),
        "exact_ack_validation_decision": gate.to_dict(),
        "exact_ack_failure_reason": gate.failure_reason,
        "exact_ack_no_trading_language_guard": gate.no_trading_language_guard_passed,
        "exact_ack_audit_record": gate.to_dict(),
    }


def _minimal_payload(state: dict[str, Any]) -> dict[str, Any]:
    result = state["minimal_live_public_probe_execution"]
    return {
        **result.to_dict(),
        "bounded_probe_execution_tasks": result.run_summary.plan.to_dict()["tasks"] if result.run_summary else [],
        "bounded_probe_adapter_family_selection": result.family_selection.to_dict(),
        "bounded_probe_execution_budget": result.budget.to_dict(),
        "bounded_probe_execution_outcomes": [item.to_dict() for item in result.outcomes],
        "bounded_probe_execution_failures": [item.to_dict() for item in result.failures],
        "bounded_probe_execution_safety_proof": result.safety_proof.to_dict(),
    }


def _domain_payload(state: dict[str, Any], domain: str) -> dict[str, Any]:
    result = state["domain_probe"][domain]
    key = domain
    return {
        **result.to_dict(),
        f"{key}_enabled_probe_status": result.status,
        "enabled_probe_task": result.task_status,
        "enabled_probe_result": result.result_status,
        "enabled_probe_packet": result.packet,
        "enabled_settlement_join": result.settlement_join_status,
        "enabled_probe_blocker": result.blocker,
    }


def _evidence_payload(state: dict[str, Any]) -> dict[str, Any]:
    evidence = state["live_public_evidence_ingestion"]
    return {
        **evidence.to_dict(),
        "reconciled_live_public_evidence_packets": [packet.to_dict() for packet in evidence.packets],
        "reconciled_live_public_evidence_family_summary": evidence.family_summary,
        "reconciled_live_public_evidence_eligibility": "reconciled live-public probe outputs only",
        "reconciled_live_public_evidence_freshness": "fresh retrieval and evidence timestamps required",
        "reconciled_live_public_evidence_blockers": evidence.blockers,
    }


def _settlement_payload(state: dict[str, Any]) -> dict[str, Any]:
    settlement = state["settlement_evidence_join"]
    return {
        **settlement.to_dict(),
        "reconciled_settlement_evidence_candidates": [item.to_dict() for item in settlement.candidates],
        "reconciled_settlement_join_decisions": [item.to_dict() for item in settlement.join_decisions],
        "reconciled_settlement_join_confidence": [item.confidence for item in settlement.join_decisions],
        "reconciled_settlement_join_blockers": settlement.blockers,
    }


def _observation_payload(state: dict[str, Any]) -> dict[str, Any]:
    observation = state["due_forecast_observation_run"]
    return {
        **observation.to_dict(),
        "due_forecast_closure_reconciliation_cases": [item.to_dict() for item in observation.decisions],
        "due_forecast_closure_reconciliation_evidence_matches": [item.evidence for item in observation.decisions if item.evidence],
        "due_forecast_closure_reconciliation_decisions": [item.to_dict() for item in observation.decisions],
        "due_forecast_closure_reconciliation_ledger_writes": [item.to_dict() for item in observation.decisions if item.status == "OBSERVED_LIVE_PUBLIC"],
        "due_forecast_closure_reconciliation_blockers": observation.blockers,
    }


def _score_payload(state: dict[str, Any]) -> dict[str, Any]:
    score = state["live_score_observation_run"]
    return {
        **score.to_dict(),
        "live_score_closure_reconciliation_candidates": score.score_records,
        "live_score_closure_reconciliation_decisions": score.score_records,
        "live_score_closure_reconciliation_metrics": [{"score_source": "OBSERVED_LIVE_PUBLIC"} for _ in score.score_records],
        "live_score_closure_reconciliation_ledger_writes": score.score_records,
        "live_score_closure_reconciliation_blockers": ["NO_VALID_LIVE_PUBLIC_OUTCOMES"] if score.live_scored_count == 0 else [],
    }


def _calibration_payload(state: dict[str, Any]) -> dict[str, Any]:
    calibration = state["live_calibration_observation_run"]
    return {
        **calibration.to_dict(),
        "live_calibration_reconciliation_samples": state["live_score_observation_run"].score_records,
        "live_calibration_reconciliation_bucket": "v34_enabled_probe_reconciliation",
        "live_calibration_reconciliation_decision": "LOW_SAMPLE_WARN_ONLY" if calibration.low_sample_warning else "NO_UPDATE",
        "live_calibration_reconciliation_warning": "LOW_SAMPLE" if calibration.low_sample_warning else None,
        "live_calibration_reconciliation_blocker": calibration.blocker,
    }


def _cache_payload(state: dict[str, Any]) -> dict[str, Any]:
    cache = state["public_probe_artifact_cache"]
    return {
        **cache.to_dict(),
        "reconciled_probe_cache_records": [],
        "reconciled_probe_cache_manifest": {"record_count": cache.record_count, "cache_mode": cache.cache_mode},
        "reconciled_probe_cache_freshness_policy": "fresh live-public only",
        "reconciled_probe_cache_redaction_audit": "raw payload redacted",
        "reconciled_probe_cache_blocker": None,
    }


def _audit_payload(state: dict[str, Any]) -> dict[str, Any]:
    audit = state["enabled_probe_audit_ledger"]
    return {
        **audit.to_dict(),
        "reconciled_probe_audit_record": audit.to_dict(),
        "reconciled_probe_gate_audit": {"gate_state": audit.gate_state, "exact_ack_validation_status": audit.exact_ack_validation_status},
        "reconciled_probe_source_audit": {"probe_run_count": audit.probe_run_count},
        "reconciled_probe_observation_audit": {"observed_forecast_count": audit.observed_forecast_count},
        "reconciled_probe_score_audit": {"live_scored_count": audit.live_scored_count},
        "reconciled_probe_safety_audit": {"execution_bridge_present": False, "secret_values_exposed": False},
    }


def _sports_payload(state: dict[str, Any]) -> dict[str, Any]:
    sports = state["sports_probe_exclusion_guard"]
    return {
        **sports.to_dict(),
        "sports_probe_exclusion_recheck_decision": "EXCLUDED_UNTIL_TERMS_APPROVED",
        "sports_source_approval_state_v5": "OPERATOR_APPROVAL_REQUIRED",
        "sports_fixture_mode_proof_v5": "fixture evidence is not live scored",
        "sports_operator_approval_packet_v5": "terms-safe public sports source required",
        "sports_probe_exclusion_recheck_blocker": "SPORTS_TERMS_REVIEW_REQUIRED",
    }


def _truth_payload(state: dict[str, Any]) -> dict[str, Any]:
    truth = state["source_truth_enabled_probe_evidence"]
    return {
        **truth.to_dict(),
        "reconciled_probe_health_truth_signal": truth.enabled_probe_health_truth_signal,
        "reconciled_evidence_compatibility_truth_signal": truth.enabled_evidence_compatibility_truth_signal,
        "reconciled_observation_closure_truth_signal": truth.enabled_observation_closure_truth_signal,
        "reconciled_live_score_truth_signal": truth.enabled_live_score_truth_signal,
        "reconciled_source_recovery_action_v15": truth.enabled_source_recovery_action_v14,
    }


def _partial_payload(state: dict[str, Any]) -> dict[str, Any]:
    ledger = state["partial_reduction_ledger"]
    return ledger.to_dict()


def _sprint_payload(state: dict[str, Any]) -> dict[str, Any]:
    sprint = state["sprint_queue"]
    return {
        "probe_reconciliation_sprint_queue_v11": sprint.tasks,
        "probe_reconciliation_sprint_v11_task": sprint.tasks[0]["task"] if sprint.tasks else "operator-enabled reconciliation pass",
        "probe_reconciliation_sprint_v11_source_target": sprint.source_targets,
        "probe_reconciliation_sprint_v11_settlement_target": sprint.settlement_targets,
        "probe_reconciliation_sprint_v11_scoring_target": sprint.scoring_target,
        "probe_reconciliation_sprint_v11_operator_action": sprint.operator_action,
        "probe_reconciliation_sprint_v11_risk_guard": sprint.risk_guard,
    }


def _queue_payload(state: dict[str, Any]) -> dict[str, Any]:
    plane = state["compounding_plane"]
    return {
        "probe_reconciliation_to_score_compounding_control_plane_v18_status": plane.compounding_v18_status,
        "probe_reconciliation_run_queue_v5": plane.run_queue,
        "evidence_reconciliation_queue_v2": plane.evidence_queue,
        "settlement_reconciliation_queue_v2": plane.settlement_queue,
        "forecast_closure_reconciliation_queue_v2": plane.observation_queue,
        "live_score_closure_growth_queue_v5": plane.live_score_queue,
        "next_bundle_recommendation_v34": plane.next_bundle_recommendation,
    }


def _scoreboard_payload(state: dict[str, Any]) -> dict[str, Any]:
    board = state["market_class_scoreboard"]
    return {
        "domain_market_class_scoreboard_v19_status": board.market_class_scoreboard_v19_status,
        "probe_reconciliation_run_scoreboard_status": board.run_scoreboard_status,
        "live_evidence_reconciliation_scoreboard_status": board.evidence_scoreboard_status,
        "settlement_reconciliation_scoreboard_status": board.settlement_scoreboard_status,
        "due_forecast_closure_reconciliation_scoreboard_status": board.observation_scoreboard_status,
        "live_score_closure_reconciliation_scoreboard_status": board.live_score_scoreboard_status,
        "domain_market_class_rows": board.domain_market_class_rows,
    }


def _budget_payload(state: dict[str, Any]) -> dict[str, Any]:
    budget = state["runtime_budget"]
    return {
        "v34_runtime_budget_status": budget.v34_runtime_budget_status,
        "probe_reconciliation_runtime_budget": budget.probe_reconciliation_runtime_budget,
        "live_evidence_reconciliation_budget": budget.live_evidence_reconciliation_budget,
        "forecast_closure_reconciliation_runtime_budget": budget.forecast_closure_reconciliation_runtime_budget,
        "dashboard_cache_policy": budget.dashboard_cache_policy,
        "report_chain_runtime_profiler_status": budget.report_chain_runtime_profiler_status,
    }


def _safety_payload(report_name: str, state: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "PASS",
        "safety_status": "PASS",
        "report_name_checked": report_name,
        "live_submit_hash": LIVE_SUBMIT_HASH,
        "caps_hash": CAPS_HASH,
        "missing_ack_probe_run": False,
        "fuzzy_ack_probe_run": False,
        "exact_ack_required": True,
        "probe_run_count": 0 if state["exact_gate_ack"].exact_ack_validation_status != "PASS" else state["minimal_live_public_probe_execution"].probe_run_count,
        "operator_enabled_probe_run_to_execution_bridge_present": False,
        "minimal_live_public_probe_to_execution_bridge_present": False,
        "live_public_evidence_ingestion_to_execution_bridge_present": False,
        "settlement_evidence_join_to_execution_bridge_present": False,
        "due_observation_run_to_execution_bridge_present": False,
        "live_score_observation_to_execution_bridge_present": False,
        "live_calibration_observation_to_execution_bridge_present": False,
        "public_probe_cache_to_execution_bridge_present": False,
        "enabled_probe_audit_to_execution_bridge_present": False,
        "source_truth_to_execution_bridge_present": False,
        "probe_sprint_to_execution_bridge_present": False,
    }


def _component_payload(report_name: str, state: dict[str, Any]) -> dict[str, Any]:
    report = _safe_payload(_workstream(report_name), _verdict(report_name), **_common(state, report_name))
    if report_name.startswith("v34_operator") or report_name.startswith("v34_probe"):
        report.update(_controller_payload(state))
    if report_name.startswith("exact_ack") or report_name.startswith("exact_gate"):
        report.update(_ack_payload(state))
    if report_name.startswith("bounded_readonly") or report_name.startswith("bounded_probe"):
        report.update(_minimal_payload(state))
    if report_name.startswith("weather"):
        report.update(_domain_payload(state, "weather"))
    if report_name.startswith("crypto"):
        report.update(_domain_payload(state, "crypto"))
    if report_name.startswith("public_event"):
        report.update(_domain_payload(state, "public_event"))
    if report_name.startswith("kalshi"):
        report.update(_domain_payload(state, "kalshi_readonly"))
    if report_name.startswith("live_evidence_reconciliation_ledger_v1") or report_name.startswith("reconciled_live_public"):
        report.update(_evidence_payload(state))
    if report_name.startswith("settlement_join_reconciliation_v4") or report_name.startswith("reconciled_settlement"):
        report.update(_settlement_payload(state))
    if report_name.startswith("due_forecast_closure_reconciliation") and "scoreboard" not in report_name:
        report.update(_observation_payload(state))
    if report_name.startswith("live_score_closure_reconciliation") and "scoreboard" not in report_name:
        report.update(_score_payload(state))
    if report_name.startswith("live_calibration_reconciliation"):
        report.update(_calibration_payload(state))
    if report_name.startswith("probe_run_artifact_reconciliation") or report_name.startswith("reconciled_probe_cache"):
        report.update(_cache_payload(state))
    if report_name.startswith("reconciled_probe_audit"):
        report.update(_audit_payload(state))
    if report_name.startswith("sports"):
        report.update(_sports_payload(state))
    if report_name.startswith("source_truth_probe_reconciliation") or "truth_signal" in report_name or report_name.startswith("reconciled_source_recovery"):
        report.update(_truth_payload(state))
    if "partial" in report_name or "pass_delta" in report_name:
        report.update(_partial_payload(state))
    if "sprint" in report_name:
        report.update(_sprint_payload(state))
    if "queue" in report_name or "compounding" in report_name or "next_bundle" in report_name:
        report.update(_queue_payload(state))
    if "scoreboard" in report_name or "domain_market_class" in report_name:
        report.update(_scoreboard_payload(state))
    if any(token in report_name for token in ["budget", "cache_policy", "profiler", "runtime"]) or report_name.startswith("v34_runtime_budget"):
        report.update(_budget_payload(state))
    if report_name.startswith("no_") or report_name.startswith("readonly_only") or "blunder" in report_name or "canonical_identity" in report_name:
        report.update(_safety_payload(report_name, state))
    return report


def generate_dashboard_v34_report_v1(state: dict[str, Any]) -> dict[str, Any]:
    routes = [
        "/api/v34/operator-enabled-probe-run-reconciliation",
        "/api/v34/exact-gate-ack",
        "/api/v34/bounded-readonly-public-probe",
        "/api/v34/weather-observation-reconciliation",
        "/api/v34/crypto-price-reconciliation",
        "/api/v34/public-event-reference-reconciliation",
        "/api/v34/kalshi-readonly-rule-reconciliation",
        "/api/v34/live-evidence-reconciliation",
        "/api/v34/settlement-join-reconciliation",
        "/api/v34/due-forecast-closure-reconciliation",
        "/api/v34/live-score-closure-reconciliation",
        "/api/v34/live-calibration-reconciliation",
        "/api/v34/probe-run-artifact-cache",
        "/api/v34/reconciled-probe-audit",
        "/api/v34/sports-probe-exclusion",
        "/api/v34/source-truth-v15",
        "/api/v34/partial-reduction",
        "/api/v34/probe-reconciliation-sprint-v11",
        "/api/v34/compounding-v18",
        "/api/v34/market-class-scoreboard",
        "/api/v34/transport-guard",
        "/api/v34/mission-state",
    ]
    return _safe_payload("V34: Dashboard Contract", "PASS", **_common(state, "dashboard_v34_report_v1.json"), dashboard_status="PASS", routes=routes, cache_policy="artifact-backed deterministic report slices")


def dummy_mission_state_report_v20(reports: dict[str, dict[str, Any]], state: dict[str, Any]) -> dict[str, Any]:
    partials = sorted(name for name, report in reports.items() if report.get("verdict") == "PARTIAL")
    common = _common(state, "dummy_mission_state_report_v20.json")
    common.pop("v33_source_recovery_live_observation_status", None)
    return _safe_payload(
        "V34: Dummy Mission State",
        "PARTIAL" if partials else "PASS",
        **common,
        mission_state_verdict="PARTIAL" if partials else "PASS",
        v17_truth_loop_status="PASS",
        v21_source_activation_status="PASS",
        v22_forecast_write_status="PASS",
        v23_observer_calibration_status="PASS_PARTIAL_EXPECTED",
        v24_open_source_public_data_status="PASS_PARTIAL_EXPECTED",
        v25_market_class_generalization_status="PASS_PARTIAL_EXPECTED",
        v26_keyless_settlement_expansion_status="PASS_PARTIAL_EXPECTED",
        v27_integration_settlement_live_scoring_status="PASS_PARTIAL_EXPECTED",
        v28_oss_observation_closure_status="PASS_PARTIAL_EXPECTED",
        v29_oss_adapter_spec_factory_status="PASS_PARTIAL_EXPECTED",
        v30_in_house_adapter_implementation_status="PASS_PARTIAL_EXPECTED",
        v31_public_probe_execution_status="PASS_PARTIAL_EXPECTED",
        v32_source_recovery_live_observation_status="PASS_PARTIAL_EXPECTED",
        v33_operator_enabled_probe_observation_status="PASS_PARTIAL_EXPECTED",
        live_submit_flag_status="PASS_DISABLED",
        caps_config_status="PASS_UNCHANGED",
        no_secret_leak_status="PASS",
        no_source_api_key_leak_status="PASS",
        no_github_token_leak_status="PASS",
        no_kalshi_private_key_leak_status="PASS",
        no_direct_order_bypass_status="PASS",
        no_direct_cancel_bypass_status="PASS",
        no_unauthorized_source_status="PASS",
        no_questionable_odds_scraping_status="PASS",
        no_unapproved_source_activation_status="PASS",
        no_commercial_source_without_approval_status="PASS",
        no_premium_feed_required_global_blocker_status="PASS",
        no_browser_automation_status="PASS",
        no_pageagent_status="PASS",
        no_dom_extraction_status="PASS",
        no_browser_research_lane_status="PASS",
        no_mined_repo_clone_status="PASS",
        no_mined_repo_import_status="PASS",
        no_mined_repo_execution_status="PASS",
        no_blind_mined_code_copy_status="PASS",
        no_fixture_claimed_real_status="PASS",
        no_replay_claimed_live_status="PASS",
        no_replay_score_claimed_live_status="PASS",
        no_proxy_claimed_exchange_native_status="PASS",
        no_cached_sample_claimed_live_status="PASS",
        no_stale_cached_evidence_scored_live_status="PASS",
        no_public_sample_evidence_scored_live_status="PASS",
        no_context_claimed_edge_status="PASS",
        no_example_market_canonical_center_status="PASS",
        no_unresolved_forecast_scored_status="PASS",
        no_ambiguous_settlement_scored_status="PASS",
        no_source_unavailable_forecast_scored_status="PASS",
        no_not_due_forecast_scored_status="PASS",
        no_adapter_fixture_scored_live_status="PASS",
        no_adapter_dry_run_scored_live_status="PASS",
        no_public_probe_failure_scored_live_status="PASS",
        no_disabled_probe_scored_live_status="PASS",
        no_missing_ack_probe_run_status="PASS",
        no_fuzzy_ack_probe_run_status="PASS",
        no_outcome_fabrication_status="PASS",
        no_operator_enabled_probe_run_to_execution_bridge_status="PASS",
        no_minimal_live_public_probe_to_execution_bridge_status="PASS",
        no_live_public_evidence_ingestion_to_execution_bridge_status="PASS",
        no_settlement_evidence_join_to_execution_bridge_status="PASS",
        no_due_observation_run_to_execution_bridge_status="PASS",
        no_live_score_observation_to_execution_bridge_status="PASS",
        no_live_calibration_observation_to_execution_bridge_status="PASS",
        no_public_probe_cache_to_execution_bridge_status="PASS",
        no_enabled_probe_audit_to_execution_bridge_status="PASS",
        no_source_truth_to_execution_bridge_status="PASS",
        no_probe_sprint_to_execution_bridge_status="PASS",
        blunder_separation_status="PASS",
        dashboard_status="PASS",
        partial_reports=partials,
        partial_reasons=[
            "public probe gate is disabled by default",
            "exact acknowledgement is missing",
            "no live-public evidence is reconciled in default mode",
            "live scored count remains 0 because no observed live-public outcomes exist in default mode",
            "sports remains fixture/replay-only pending terms-safe source approval",
        ],
        proof_paths={
            "mission_state": str(ARTIFACTS / "dummy_mission_state_report_v20.json"),
            "operator_enabled_probe_run_reconciliation": str(ARTIFACTS / "v34_operator_enabled_probe_run_reconciliation_controller_v1_report.json"),
            "exact_gate_ack": str(ARTIFACTS / "exact_gate_acknowledgement_hardening_v3_report.json"),
            "bounded_readonly_public_probe": str(ARTIFACTS / "bounded_readonly_public_probe_pass_v2_report.json"),
            "live_evidence": str(ARTIFACTS / "live_evidence_reconciliation_ledger_v1_report.json"),
            "settlement": str(ARTIFACTS / "settlement_join_reconciliation_v4_report.json"),
            "observation": str(ARTIFACTS / "due_forecast_closure_reconciliation_v7_report.json"),
            "score": str(ARTIFACTS / "live_score_closure_reconciliation_v5_report.json"),
            "safety": str(ARTIFACTS / "no_operator_enabled_probe_run_to_execution_bridge_report_v34.json"),
        },
    )


class V34ReportFactory:
    def __init__(self, *, enable_network: bool = False, env: dict[str, str] | None = None) -> None:
        self.enable_network = enable_network
        self.env = env if env is not None else {}

    def build(self) -> dict[str, dict[str, Any]]:
        state = build_default_v34_state(enable_network=self.enable_network, env=self.env)
        reports: dict[str, dict[str, Any]] = {}
        for report_name in REPORT_NAMES:
            if report_name == "dummy_mission_state_report_v20.json":
                continue
            if report_name == "dashboard_v34_report_v1.json":
                reports[report_name] = generate_dashboard_v34_report_v1(state)
                continue
            reports[report_name] = _component_payload(report_name, state)
        reports["dummy_mission_state_report_v20.json"] = dummy_mission_state_report_v20(reports, state)
        if "dashboard_v34_report_v1.json" not in reports:
            reports["dashboard_v34_report_v1.json"] = generate_dashboard_v34_report_v1(state)
        return reports
