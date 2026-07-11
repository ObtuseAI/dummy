from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v24.reports import V24ReportFactory

router = APIRouter(prefix="/api/v24", tags=["v24"])


def _reports() -> dict[str, dict[str, Any]]:
    return V24ReportFactory(enable_network=False).build()


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    payload["live_submit_disabled"] = True
    payload["caps_unchanged"] = True
    return payload


@router.get("/open-source-doctrine")
async def open_source_doctrine() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "open_source_source_doctrine": reports["open_source_source_doctrine_v1_report.json"],
            "public_open_data_preference": reports["public_open_data_preference_report_v1.json"],
            "keyless_source_preference": reports["keyless_source_preference_report_v1.json"],
            "licensed_source_optionality_policy": reports["licensed_source_optionality_policy_report_v1.json"],
            "paid_feed_nonblocking_policy": reports["paid_feed_nonblocking_policy_report_v1.json"],
        }
    )


@router.get("/source-universe-reclassification")
async def source_universe_reclassification() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "open_source_source_universe_reclassifier": reports["open_source_source_universe_reclassifier_report_v1.json"],
            "open_source_candidate_score": reports["open_source_candidate_score_report_v1.json"],
            "open_data_candidate_score": reports["open_data_candidate_score_report_v1.json"],
            "keyless_public_candidate_score": reports["keyless_public_candidate_score_report_v1.json"],
            "commercial_optional_candidate_score": reports["commercial_optional_candidate_score_report_v1.json"],
            "source_progress_impact_class": reports["source_progress_impact_class_report_v1.json"],
        }
    )


@router.get("/keyless-public-expansion")
async def keyless_public_expansion() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "keyless_public_adapter_expansion": reports["keyless_public_adapter_expansion_v1_report.json"],
            "keyless_public_adapter_candidate": reports["keyless_public_adapter_candidate_report_v1.json"],
            "keyless_public_probe": reports["keyless_public_probe_report_v1.json"],
            "keyless_public_evidence_packet": reports["keyless_public_evidence_packet_report_v1.json"],
            "keyless_public_activation_decision": reports["keyless_public_activation_decision_report_v1.json"],
        }
    )


@router.get("/public-proxy-terrain")
async def public_proxy_terrain() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "public_proxy_edge_terrain": reports["public_proxy_edge_terrain_v1_report.json"],
            "public_proxy_evidence": reports["public_proxy_evidence_report_v1.json"],
            "proxy_edge_class": reports["proxy_edge_class_report_v1.json"],
            "proxy_edge_confidence": reports["proxy_edge_confidence_report_v1.json"],
            "proxy_overclaim_guard": reports["proxy_overclaim_guard_report_v1.json"],
            "proxy_no_trade_gate": reports["proxy_no_trade_gate_report_v1.json"],
        }
    )


@router.get("/nasdaq-open-proxy")
async def nasdaq_open_proxy() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "nasdaq_open_proxy_terrain": reports["nasdaq_open_proxy_terrain_v1_report.json"],
            "nasdaq_public_proxy_need": reports["nasdaq_public_proxy_need_report_v1.json"],
            "nasdaq_public_proxy_evidence": reports["nasdaq_public_proxy_evidence_report_v1.json"],
            "nasdaq_open_proxy_readiness": reports["nasdaq_open_proxy_readiness_report_v1.json"],
            "nasdaq_open_proxy_no_trade_gate": reports["nasdaq_open_proxy_no_trade_gate_report_v1.json"],
        }
    )


@router.get("/oil-open-proxy")
async def oil_open_proxy() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "oil_open_proxy_terrain": reports["oil_open_proxy_terrain_v1_report.json"],
            "oil_public_proxy_need": reports["oil_public_proxy_need_report_v1.json"],
            "oil_public_proxy_evidence": reports["oil_public_proxy_evidence_report_v1.json"],
            "oil_open_proxy_readiness": reports["oil_open_proxy_readiness_report_v1.json"],
            "oil_open_proxy_no_trade_gate": reports["oil_open_proxy_no_trade_gate_report_v1.json"],
        }
    )


@router.get("/open-data-replay")
async def open_data_replay() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "open_data_replay_dataset_builder": reports["open_data_replay_dataset_builder_v1_report.json"],
            "replay_dataset_source": reports["replay_dataset_source_report_v1.json"],
            "replay_dataset_provenance": reports["replay_dataset_provenance_report_v1.json"],
            "replay_dataset_license_class": reports["replay_dataset_license_class_report_v1.json"],
            "replay_dataset_integrity_check": reports["replay_dataset_integrity_check_report_v1.json"],
            "replay_dataset_limitations": reports["replay_dataset_limitations_report_v1.json"],
        }
    )


@router.get("/replay-calibration-v2")
async def replay_calibration_v2() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "replay_calibration_harness": reports["replay_calibration_harness_v2_report.json"],
            "replay_scenario_generator": reports["replay_scenario_generator_report_v1.json"],
            "replay_forecast_policy": reports["replay_forecast_policy_report_v1.json"],
            "replay_no_trade_policy": reports["replay_no_trade_policy_report_v1.json"],
            "replay_calibration_sample": reports["replay_calibration_sample_report_v1.json"],
            "replay_calibration_guard": reports["replay_calibration_guard_report_v1.json"],
        }
    )


@router.get("/open-source-baseline-lab")
async def open_source_baseline_lab() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "open_source_baseline_lab": reports["open_source_baseline_lab_v1_report.json"],
            "baseline_strategy_registry": reports["baseline_strategy_registry_report_v1.json"],
            "baseline_strategy_candidate": reports["baseline_strategy_candidate_report_v1.json"],
            "baseline_backtest_replay_result": reports["baseline_backtest_replay_result_report_v1.json"],
            "baseline_promotion_guard": reports["baseline_promotion_guard_report_v1.json"],
        }
    )


@router.get("/keyless-live-forecast-expansion")
async def keyless_live_forecast_expansion() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "keyless_live_forecast_expansion": reports["keyless_live_forecast_expansion_v2_report.json"],
            "keyless_forecast_candidate": reports["keyless_forecast_candidate_report_v1.json"],
            "keyless_forecast_decision": reports["keyless_forecast_decision_report_v1.json"],
            "keyless_forecast_ledger_write": reports["keyless_forecast_ledger_write_report_v1.json"],
            "keyless_forecast_observer_plan": reports["keyless_forecast_observer_plan_report_v1.json"],
        }
    )


@router.get("/open-source-adapter-work-queue")
async def open_source_adapter_work_queue() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "open_source_adapter_work_queue": reports["open_source_adapter_work_queue_v1_report.json"],
            "open_source_adapter_candidate": reports["open_source_adapter_candidate_report_v1.json"],
            "open_source_adapter_license_review": reports["open_source_adapter_license_review_report_v1.json"],
            "open_source_adapter_implementation_sketch": reports["open_source_adapter_implementation_sketch_report_v1.json"],
            "open_source_adapter_test_plan": reports["open_source_adapter_test_plan_report_v1.json"],
            "open_source_adapter_no_exec_guard": reports["open_source_adapter_no_exec_guard_report_v1.json"],
        }
    )


@router.get("/optional-premium-demotion")
async def optional_premium_demotion() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "optional_premium_feed_demotion": reports["optional_premium_feed_demotion_v1_report.json"],
            "premium_feed_optional_status": reports["premium_feed_optional_status_report_v1.json"],
            "premium_feed_upgrade_value": reports["premium_feed_upgrade_value_report_v1.json"],
            "premium_feed_nonblocking_proof": reports["premium_feed_nonblocking_proof_report_v1.json"],
            "premium_feed_operator_note": reports["premium_feed_operator_note_report_v1.json"],
        }
    )


@router.get("/source-truth-v6")
async def source_truth_v6() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "open_source_source_truth_score": reports["open_source_source_truth_score_v6_report.json"],
            "open_data_truth_state": reports["open_data_truth_state_report_v1.json"],
            "keyless_public_truth_state": reports["keyless_public_truth_state_report_v1.json"],
            "replay_truth_state": reports["replay_truth_state_report_v1.json"],
            "proxy_truth_state": reports["proxy_truth_state_report_v1.json"],
            "premium_optional_truth_state": reports["premium_optional_truth_state_report_v1.json"],
            "source_truth_overclaim_guard": reports["source_truth_overclaim_guard_v6_report.json"],
        }
    )


@router.get("/forecast-lifecycle-v3")
async def forecast_lifecycle_v3() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "forecast_lifecycle_ledger": reports["forecast_lifecycle_ledger_v3_report.json"],
            "forecast_source_mode_label": reports["forecast_source_mode_label_report_v1.json"],
            "forecast_proxy_label": reports["forecast_proxy_label_report_v1.json"],
            "forecast_replay_label": reports["forecast_replay_label_report_v1.json"],
            "forecast_lifecycle_mode_separation_proof": reports["forecast_lifecycle_mode_separation_proof_report_v1.json"],
        }
    )


@router.get("/open-source-compounding-v8")
async def open_source_compounding_v8() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "open_source_compounding_control_plane": reports["open_source_compounding_control_plane_v8_report.json"],
            "open_source_acceleration_work_queue": reports["open_source_acceleration_work_queue_report_v1.json"],
            "keyless_public_expansion_queue": reports["keyless_public_expansion_queue_report_v1.json"],
            "replay_calibration_expansion_queue": reports["replay_calibration_expansion_queue_report_v1.json"],
            "proxy_terrain_improvement_queue": reports["proxy_terrain_improvement_queue_report_v1.json"],
            "optional_premium_upgrade_queue": reports["optional_premium_upgrade_queue_report_v1.json"],
            "next_bundle_recommendation": reports["next_bundle_recommendation_v24_open_source_report.json"],
        }
    )


@router.get("/domain-scoreboard-v9")
async def domain_scoreboard_v9() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "domain_scoreboard": reports["domain_scoreboard_v9_report.json"],
            "open_source_progress_scoreboard": reports["open_source_progress_scoreboard_v1.json"],
            "keyless_public_source_scoreboard": reports["keyless_public_source_scoreboard_v1.json"],
            "replay_proxy_scoreboard": reports["replay_proxy_scoreboard_v1.json"],
            "optional_premium_scoreboard": reports["optional_premium_scoreboard_v1.json"],
        }
    )


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    reports = _reports()
    return _safe({"mission_state": reports["dummy_mission_state_report_v10.json"]})
