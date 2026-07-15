from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from dummy.world_model import (
    WorldModelEvaluationCase,
    WorldModelValidationError,
    regime_transfer_report,
    world_state_ablation_report,
)


NOW = datetime(2026, 7, 14, 22, 0, tzinfo=timezone.utc)


def _case(index: int) -> WorldModelEvaluationCase:
    result_yes = index % 2 == 0
    return WorldModelEvaluationCase(
        case_id=f"case-{index:03d}",
        event_cluster_id=f"cluster-{index:03d}",
        snapshot_id=f"snapshot-{index:03d}",
        decision_at=NOW + timedelta(minutes=index),
        settlement_received_at=NOW + timedelta(days=1, minutes=index),
        settlement_verified=True,
        result_yes=result_yes,
        full_probability=0.75 if result_yes else 0.25,
        ablated_probabilities={
            "crypto.realized_volatility": 0.60 if result_yes else 0.40,
        },
        training_regime="normal-liquidity",
        target_regime=(
            "normal-liquidity" if index < 15 else "weekend-thin-liquidity"
        ),
    )


def test_empty_reports_state_insufficient_evidence_without_claims() -> None:
    ablation = world_state_ablation_report(())
    transfer = regime_transfer_report(())
    assert ablation["status"] == "INSUFFICIENT_SETTLED_EVIDENCE"
    assert transfer["status"] == "INSUFFICIENT_SETTLED_EVIDENCE"
    assert ablation["settlement_verified_only"] is True
    assert transfer["settlement_verified_only"] is True
    assert ablation["report_id"]
    assert transfer["report_id"]


def test_evaluation_case_round_trips_without_semantic_drift() -> None:
    case = _case(0)
    assert WorldModelEvaluationCase.from_dict(case.to_dict()) == case


def test_ablation_reports_only_after_minimum_unique_settled_clusters() -> None:
    cases = tuple(_case(index) for index in range(30))
    report = world_state_ablation_report(cases)
    field = report["fields"][0]
    assert report["status"] == "EVALUATED"
    assert field["case_count"] == 30
    assert field["brier_degradation_when_ablated"] > 0.0


def test_regime_transfer_separates_in_domain_and_out_of_domain_pairs() -> None:
    cases = tuple(_case(index) for index in range(30))
    report = regime_transfer_report(cases, minimum_cases=15)
    assert report["status"] == "EVALUATED"
    assert len(report["transfers"]) == 2
    assert {item["in_domain"] for item in report["transfers"]} == {True, False}
    assert all(item["mean_brier"] is not None for item in report["transfers"])


def test_duplicate_event_clusters_are_rejected_not_counted_twice() -> None:
    first = _case(0)
    duplicate = replace(
        _case(1),
        event_cluster_id=first.event_cluster_id,
    )
    with pytest.raises(WorldModelValidationError, match="unique event clusters"):
        world_state_ablation_report((first, duplicate), minimum_cases=1)


def test_unverified_or_predecision_settlement_cannot_enter_evaluation() -> None:
    with pytest.raises(WorldModelValidationError, match="verified boolean settlement"):
        replace(_case(0), settlement_verified=False)
    with pytest.raises(WorldModelValidationError, match="settlement precedes"):
        replace(
            _case(0),
            settlement_received_at=NOW - timedelta(seconds=1),
        )
