from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import pytest

from dummy.metabolism import (
    ResourceBudget,
    account_messages,
    allocation_recommendation,
    calculate_marginal_utility,
    estimate_costs,
    estimate_information_gain_proxy,
)
from dummy.metacognition import (
    ConfidenceDecomposition,
    ControlAction,
    ControlRecommendation,
    MetaCalibrationEvidence,
    MetacognitiveEvaluationCase,
    MetacognitiveValidationError,
    abstention_value_report,
    confidence_calibration_report,
    resource_efficiency_report,
    unavailable_meta_calibration,
)
from dummy.protocols import MessageEnvelope, MessageType


NOW = datetime(2026, 7, 15, 1, 0, tzinfo=timezone.utc)


def _case(index: int) -> MetacognitiveEvaluationCase:
    abstained = index % 2 == 0
    result = False if abstained else True
    prediction = 0.9
    return MetacognitiveEvaluationCase(
        case_id=f"case-{index:03d}",
        event_cluster_id=f"cluster-{index:03d}",
        prediction_probability=prediction,
        fixed_coverage_probability=prediction,
        result_yes=result,
        abstained=abstained,
        confidence_score=0.1 if abstained else 0.9,
        difficulty_score=0.9 if abstained else 0.1,
        baseline_resource_cost=1.0,
        resource_aware_cost=0.5,
        resource_aware_probability=prediction,
        settlement_verified=True,
        evidence_ids=(f"settlement-{index}",),
    )


def test_confidence_final_is_weakest_component_not_an_average() -> None:
    values = {
        "model": 0.9,
        "evidence_completeness": 0.8,
        "evidence_freshness": 0.7,
        "data_reliability": 0.6,
        "regime_familiarity": 0.5,
        "historical_analogue_strength": 0.4,
        "calibration_reliability": 0.3,
        "market_prior_agreement": 0.8,
        "source_independence": 0.9,
        "causal_confidence": 0.7,
        "forecast_stability": 0.6,
        "settlement_sample_support": 0.2,
    }
    confidence = ConfidenceDecomposition(**values)
    assert confidence.final == 0.2
    assert confidence.limiting_components == ("settlement_sample_support",)


def test_uncalibrated_metacognition_cannot_apply_continue_or_expand() -> None:
    with pytest.raises(MetacognitiveValidationError, match="cannot expand"):
        ControlRecommendation(
            action=ControlAction.CONTINUE,
            reasons=("test",),
            calibrated=False,
            applied=True,
        )
    calibration = unavailable_meta_calibration()
    assert calibration.verified is False
    assert calibration.state.value == "UNCALIBRATED_SHADOW"


def test_empty_evidence_reports_make_no_phase5_claims() -> None:
    assert abstention_value_report(())["status"] == "INSUFFICIENT_SETTLED_EVIDENCE"
    assert resource_efficiency_report(())["status"] == "INSUFFICIENT_SETTLED_EVIDENCE"
    report = confidence_calibration_report(())
    assert report["status"] == "INSUFFICIENT_SETTLED_EVIDENCE"
    assert report["calibration_verified"] is False


def test_verified_unique_cluster_evidence_can_pass_explicit_gates() -> None:
    cases = tuple(_case(index) for index in range(100))
    abstention = abstention_value_report(cases)
    resources = resource_efficiency_report(cases)
    calibration = confidence_calibration_report(cases)
    assert abstention["status"] == "PASS"
    assert abstention["coverage_valid"] is True
    assert abstention["decision_loss_improvement"] > 0.0
    assert resources["status"] == "PASS"
    assert resources["cost_reduction_fraction"] == 0.5
    assert resources["brier_regression"] == 0.0
    assert calibration["status"] == "EVALUATED"
    assert calibration["confidence_brier"] < 0.02


def test_duplicate_event_cluster_cannot_inflate_evidence() -> None:
    first = _case(0)
    duplicate = MetacognitiveEvaluationCase(
        **{
            **_case(1).to_dict(),
            "event_cluster_id": first.event_cluster_id,
        }
    )
    with pytest.raises(MetacognitiveValidationError, match="unique cases"):
        abstention_value_report((first, duplicate), minimum_cases=1)


def test_unmeasured_compute_blocks_utility_and_recommends_narrow_scope() -> None:
    message = MessageEnvelope.create(
        message_type=MessageType.FORECAST,
        sender="phase5-test",
        market_id="KXTEST",
        issued_at=NOW,
        effective_time=NOW,
        received_at=NOW,
        model_version="test-v1",
        policy_version="test-policy",
        evidence_ids=("evidence",),
        payload={"probability": 0.6, "uncertainty": 0.1},
    )
    usage = account_messages((message,))
    info = estimate_information_gain_proxy(
        (0.4, 0.6),
        source_independence=1.0,
        calibration_reliability=0.5,
    )
    costs = estimate_costs(
        usage,
        ResourceBudget(),
        duplication_fraction=0.0,
        execution_relevance=1.0,
    )
    utility = calculate_marginal_utility(
        info,
        costs,
        expected_calibration_value=0.0,
        expected_decision_improvement=0.01,
    )
    assert utility.utility is None
    assert utility.status.value == "UNRESOLVED_UNMEASURED_COST"
    assert allocation_recommendation(utility)["action"] == "NARROW_SCOPE"


def test_measured_cost_uses_dedicated_cpu_memory_and_latency_budgets() -> None:
    message = MessageEnvelope.create(
        message_type=MessageType.FORECAST,
        sender="phase5-measured-test",
        market_id="KXTEST",
        issued_at=NOW,
        effective_time=NOW,
        received_at=NOW,
        model_version="test-v1",
        policy_version="test-policy",
        evidence_ids=("evidence",),
        payload={"probability": 0.6, "uncertainty": 0.1},
    )
    budget = ResourceBudget()
    usage = account_messages(
        (message,),
        cpu_ms=budget.max_cpu_ms,
        peak_memory_bytes=budget.max_peak_memory_bytes,
        wall_clock_ms=budget.max_wall_clock_ms,
    )
    costs = estimate_costs(
        usage,
        budget,
        duplication_fraction=0.0,
        execution_relevance=1.0,
    )
    assert costs.compute_cost is not None
    assert costs.latency_cost == 1.0
    assert costs.normalized_cost is not None
    assert costs.unmeasured == ()


def test_verified_meta_calibration_requires_metrics_and_evidence() -> None:
    with pytest.raises(MetacognitiveValidationError, match="requires settled"):
        MetaCalibrationEvidence(
            calibration_identity="bad-verified-map",
            sample_size=10,
            brier=None,
            ece=None,
            verified=True,
            evidence_ids=(),
        )


def test_phase5_audit_is_deterministic_and_honest_without_cases(
    tmp_path: Path,
) -> None:
    script = Path(__file__).parents[1] / "scripts" / "run_vnext_phase5_audit.py"
    command = [
        sys.executable,
        str(script),
        "--output-dir",
        str(tmp_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    first = {
        path.name: path.read_bytes() for path in sorted(tmp_path.glob("*.json"))
    }
    subprocess.run(command, check=True, capture_output=True, text=True)
    second = {
        path.name: path.read_bytes() for path in sorted(tmp_path.glob("*.json"))
    }
    assert first == second
    policy = json.loads(first["VNEXT_PHASE5_CONTROL_POLICY.json"])
    assert len(policy["guards"]) == 8
    assert policy["guard_authority"] == "CONTRACTION_ONLY"
    assert policy["synthesis"]["market_prior_floor"] == 0.50
    assert policy["execution_authority"] is False
    for name in (
        "VNEXT_PHASE5_ABSTENTION_VALUE.json",
        "VNEXT_PHASE5_RESOURCE_EFFICIENCY.json",
        "VNEXT_PHASE5_METACOGNITION_CALIBRATION.json",
    ):
        report = json.loads(first[name])
        assert report["status"] == "INSUFFICIENT_SETTLED_EVIDENCE"
