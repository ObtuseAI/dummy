from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v23.reports import V23ReportFactory

router = APIRouter(prefix="/api/v23", tags=["v23"])


def _reports() -> dict[str, dict[str, Any]]:
    return V23ReportFactory(enable_network=False).build()


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    payload["live_submit_disabled"] = True
    payload["caps_unchanged"] = True
    return payload


@router.get("/forecast-observer-closure")
async def forecast_observer_closure() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "v22_forecast_observer_closure": reports["v22_forecast_observer_closure_report_v1.json"],
            "forecast_observation_attempt": reports["forecast_observation_attempt_report_v1.json"],
            "forecast_observation_decision": reports["forecast_observation_decision_report_v1.json"],
            "forecast_observation_blocker": reports["forecast_observation_blocker_report_v1.json"],
        }
    )


@router.get("/crypto-outcome-observer")
async def crypto_outcome_observer() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "crypto_forecast_outcome_observer": reports["crypto_forecast_outcome_observer_v1_report.json"],
            "crypto_spot_settlement_probe": reports["crypto_spot_settlement_probe_report_v1.json"],
            "crypto_forecast_outcome_status": reports["crypto_forecast_outcome_status_report_v1.json"],
            "crypto_forecast_settlement_blocker": reports["crypto_forecast_settlement_blocker_report_v1.json"],
        }
    )


@router.get("/weather-outcome-observer")
async def weather_outcome_observer() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "weather_forecast_outcome_observer": reports["weather_forecast_outcome_observer_v1_report.json"],
            "weather_station_settlement_probe": reports["weather_station_settlement_probe_report_v1.json"],
            "weather_forecast_outcome_status": reports["weather_forecast_outcome_status_report_v1.json"],
            "weather_forecast_settlement_blocker": reports["weather_forecast_settlement_blocker_report_v1.json"],
        }
    )


@router.get("/forecast-scoring")
async def forecast_scoring() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "forecast_scoring_engine": reports["forecast_scoring_engine_v2_report.json"],
            "forecast_score_candidate": reports["forecast_score_candidate_report_v1.json"],
            "forecast_score_result": reports["forecast_score_result_report_v1.json"],
            "forecast_score_blocker": reports["forecast_score_blocker_report_v1.json"],
            "forecast_score_integrity_proof": reports["forecast_score_integrity_proof_v1.json"],
        }
    )


@router.get("/calibration-update")
async def calibration_update() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "calibration_update_engine": reports["calibration_update_engine_v3_report.json"],
            "domain_calibration_update": reports["domain_calibration_update_report_v1.json"],
            "calibration_bucket_update": reports["calibration_bucket_update_report_v1.json"],
            "low_sample_calibration_warning": reports["low_sample_calibration_warning_report_v1.json"],
            "calibration_queue_state": reports["calibration_queue_state_report_v1.json"],
        }
    )


@router.get("/forecast-attribution")
async def forecast_attribution() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "forecast_attribution_engine": reports["forecast_attribution_engine_v2_report.json"],
            "edge_forecast_attribution": reports["edge_forecast_attribution_report_v1.json"],
            "source_attribution_update": reports["source_attribution_update_report_v1.json"],
            "no_trade_attribution": reports["no_trade_attribution_v2_report.json"],
            "outcome_pending_attribution": reports["outcome_pending_attribution_report_v1.json"],
        }
    )


@router.get("/source-truth-score")
async def source_truth_score() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "source_truth_score": reports["source_truth_score_v4_report.json"],
            "source_truth_update": reports["source_truth_update_report_v1.json"],
            "edge_source_reliability_state": reports["edge_source_reliability_state_report_v1.json"],
            "context_source_reliability_state": reports["context_source_reliability_state_report_v1.json"],
            "source_truth_promotion_gate": reports["source_truth_promotion_gate_report_v1.json"],
        }
    )


@router.get("/tier0-adapter-closure")
async def tier0_adapter_closure() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "tier0_adapter_closure_planner": reports["tier0_adapter_closure_planner_report_v1.json"],
            "tier0_adapter_closure_candidate": reports["tier0_adapter_closure_candidate_report_v1.json"],
            "tier0_adapter_closure_status": reports["tier0_adapter_closure_status_report_v1.json"],
            "tier0_adapter_proof_requirement": reports["tier0_adapter_proof_requirement_report_v1.json"],
            "tier0_adapter_operator_action": reports["tier0_adapter_operator_action_report_v1.json"],
        }
    )


@router.get("/cme-adapter-gate")
async def cme_adapter_gate() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "cme_readonly_adapter_gate": reports["cme_readonly_adapter_gate_v1_report.json"],
            "cme_futures_source_requirement": reports["cme_futures_source_requirement_report_v1.json"],
            "cme_credential_presence_check": reports["cme_credential_presence_check_report_v1.json"],
            "cme_readonly_probe_plan": reports["cme_readonly_probe_plan_report_v1.json"],
            "cme_adapter_blocker": reports["cme_adapter_blocker_report_v1.json"],
        }
    )


@router.get("/databento-adapter-gate")
async def databento_adapter_gate() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "databento_readonly_adapter_gate": reports["databento_readonly_adapter_gate_v1_report.json"],
            "databento_dataset_requirement": reports["databento_dataset_requirement_report_v1.json"],
            "databento_credential_presence_check": reports["databento_credential_presence_check_report_v1.json"],
            "databento_readonly_probe_plan": reports["databento_readonly_probe_plan_report_v1.json"],
            "databento_adapter_blocker": reports["databento_adapter_blocker_report_v1.json"],
        }
    )


@router.get("/eia-activation-closure")
async def eia_activation_closure() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "eia_adapter_activation_closure": reports["eia_adapter_activation_closure_v2_report.json"],
            "eia_key_presence_check": reports["eia_key_presence_check_report_v1.json"],
            "eia_dataset_probe_plan": reports["eia_dataset_probe_plan_v2_report.json"],
            "eia_inventory_series_mapper": reports["eia_inventory_series_mapper_report_v1.json"],
            "eia_oil_fundamental_evidence_gate": reports["eia_oil_fundamental_evidence_gate_report_v1.json"],
            "eia_activation_blocker": reports["eia_activation_blocker_v2_report.json"],
        }
    )


@router.get("/rates-dxy-context")
async def rates_dxy_context() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "rates_dxy_public_context_adapter": reports["rates_dxy_public_context_adapter_v1_report.json"],
            "treasury_yield_evidence": reports["treasury_yield_evidence_v1_report.json"],
            "dxy_proxy_evidence": reports["dxy_proxy_evidence_v1_report.json"],
            "rates_freshness_gate": reports["rates_freshness_gate_report_v1.json"],
            "rates_dxy_context_guard": reports["rates_dxy_context_guard_report_v1.json"],
        }
    )


@router.get("/nasdaq-oil-readiness")
async def nasdaq_oil_readiness() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "nasdaq_edge_readiness": reports["nasdaq_edge_readiness_v2_report.json"],
            "oil_edge_readiness": reports["oil_edge_readiness_v2_report.json"],
            "nasdaq_evidence_gap_state": reports["nasdaq_evidence_gap_state_v2_report.json"],
            "oil_evidence_gap_state": reports["oil_evidence_gap_state_v2_report.json"],
            "directional_forecast_readiness_decision": reports["directional_forecast_readiness_decision_v2_report.json"],
        }
    )


@router.get("/forecast-lifecycle")
async def forecast_lifecycle() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "forecast_lifecycle_ledger": reports["forecast_lifecycle_ledger_v1_report.json"],
            "forecast_lifecycle_record": reports["forecast_lifecycle_record_report_v1.json"],
            "forecast_lifecycle_transition": reports["forecast_lifecycle_transition_report_v1.json"],
            "forecast_lifecycle_integrity_check": reports["forecast_lifecycle_integrity_check_report_v1.json"],
        }
    )


@router.get("/compounding-v6")
async def compounding_v6() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "compounding_control_plane": reports["compounding_control_plane_v6_report.json"],
            "observer_follow_through_work_queue": reports["observer_follow_through_work_queue_report_v1.json"],
            "calibration_work_queue": reports["calibration_work_queue_v2_report.json"],
            "tier0_closure_work_queue": reports["tier0_closure_work_queue_report_v1.json"],
            "adapter_activation_work_queue": reports["adapter_activation_work_queue_v2_report.json"],
            "next_bundle_recommendation": reports["next_bundle_recommendation_v23_report.json"],
        }
    )


@router.get("/domain-scoreboard-v7")
async def domain_scoreboard_v7() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "domain_scoreboard": reports["domain_scoreboard_v7_report.json"],
            "observer_calibration_scoreboard": reports["observer_calibration_scoreboard_v1.json"],
            "tier0_adapter_closure_scoreboard": reports["tier0_adapter_closure_scoreboard_v1.json"],
            "source_truth_scoreboard": reports["source_truth_scoreboard_v4_report.json"],
        }
    )


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    reports = _reports()
    return _safe({"mission_state": reports["dummy_mission_state_report_v9.json"]})
