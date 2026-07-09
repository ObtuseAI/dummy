from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v38.reports import V38ReportFactory

router = APIRouter(prefix="/api/v38", tags=["v38"])


def _reports() -> dict[str, dict[str, Any]]:
    return V38ReportFactory().build()


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    payload["live_submit_disabled"] = True
    payload["caps_unchanged"] = True
    payload["execution_bridge_present"] = False
    payload["api_can_trigger_probes"] = False
    payload["api_can_trigger_trading"] = False
    return payload


def _slice(*names: str) -> dict[str, Any]:
    reports = _reports()
    return _safe({name.removesuffix(".json"): reports[name] for name in names})


@router.get("/gate-runtime")
async def gate_runtime() -> dict[str, Any]:
    return _slice(
        "operator_gated_real_readonly_probe_completion_v1_report.json",
        "v38_exact_operator_gate_recheck_v1_report.json",
        "v38_runtime_gate_metadata_v1_report.json",
    )


@router.get("/probe-run")
async def probe_run() -> dict[str, Any]:
    return _slice(
        "v38_real_probe_run_plan_v1_report.json",
        "v38_real_probe_run_result_v1_report.json",
    )


@router.get("/evidence-chain")
async def evidence_chain() -> dict[str, Any]:
    return _slice(
        "v38_real_probe_evidence_score_chain_v1_report.json",
        "v38_live_public_evidence_ledger_v1_report.json",
    )


@router.get("/settlement-closure")
async def settlement_closure() -> dict[str, Any]:
    return _slice(
        "v38_settlement_join_validation_v1_report.json",
        "v38_due_observation_closure_v1_report.json",
    )


@router.get("/live-score")
async def live_score() -> dict[str, Any]:
    return _slice("v38_first_real_live_score_v1_report.json")


@router.get("/calibration-source-truth")
async def calibration_source_truth() -> dict[str, Any]:
    return _slice(
        "v38_calibration_update_v1_report.json",
        "v38_source_truth_v19_report.json",
    )


@router.get("/operator-packet")
async def operator_packet() -> dict[str, Any]:
    return _slice(
        "v38_operator_packet_v1_report.json",
        "v38_next_action_v1_report.json",
    )


@router.get("/api-surface")
async def api_surface() -> dict[str, Any]:
    return _slice("v38_api_surface_report_v1.json")


@router.get("/dashboard")
async def dashboard() -> dict[str, Any]:
    return _slice(
        "dashboard_v38_report_v1.json",
        "v38_dashboard_payload_safety_report_v1.json",
    )


@router.get("/safety")
async def safety() -> dict[str, Any]:
    return _slice(
        "v38_safety_invariant_report_v1.json",
        "no_secret_leak_report_v38.json",
        "no_direct_order_bypass_report_v38.json",
        "no_live_submit_still_disabled_report_v38.json",
        "no_caps_config_modification_report_v38.json",
        "no_browser_automation_report_v38.json",
        "no_mined_repo_execution_report_v38.json",
        "no_fake_transport_score_claimed_live_report_v38.json",
        "no_missing_ack_probe_run_report_v38.json",
        "no_fuzzy_ack_probe_run_report_v38.json",
        "no_v38_workflow_to_execution_bridge_report.json",
        "no_v38_evidence_scoring_to_execution_bridge_report.json",
        "no_v38_operator_packet_to_execution_bridge_report.json",
    )


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    return _slice(
        "dummy_mission_state_report_v24.json",
        "runtime_loop_budget_v38_report.json",
        "blunder_separation_recheck_v38.json",
        "dummy_canonical_identity_report_v38.json",
        "v37_still_passes_or_partial_expected_v38_report.json",
    )

