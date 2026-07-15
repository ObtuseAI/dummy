"""Settlement-only ablation and regime-transfer evidence for world models."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping

from .models import (
    WorldModelValidationError,
    digest_json,
    freeze_json,
    iso,
    parse_iso,
    thaw_json,
    utc,
)


def _probability(value: float, name: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
        raise WorldModelValidationError(f"{name} must be in [0, 1]")
    return parsed


def _brier(probability: float, result_yes: bool) -> float:
    return (probability - float(result_yes)) ** 2


def _log_loss(probability: float, result_yes: bool) -> float:
    clipped = min(1.0 - 1e-12, max(1e-12, probability))
    return -(
        float(result_yes) * math.log(clipped)
        + (1.0 - float(result_yes)) * math.log(1.0 - clipped)
    )


@dataclass(frozen=True, slots=True)
class WorldModelEvaluationCase:
    case_id: str
    event_cluster_id: str
    snapshot_id: str
    decision_at: datetime
    settlement_received_at: datetime
    settlement_verified: bool
    result_yes: bool
    full_probability: float
    ablated_probabilities: Mapping[str, float]
    training_regime: str
    target_regime: str

    def __post_init__(self) -> None:
        for field_name in (
            "case_id",
            "event_cluster_id",
            "snapshot_id",
            "training_regime",
            "target_regime",
        ):
            if not getattr(self, field_name).strip():
                raise WorldModelValidationError(
                    f"evaluation {field_name} must be non-empty"
                )
        decision = utc(self.decision_at)
        settled = utc(self.settlement_received_at)
        if settled < decision:
            raise WorldModelValidationError("settlement precedes world-state decision")
        if self.settlement_verified is not True or type(self.result_yes) is not bool:
            raise WorldModelValidationError(
                "world-model evaluation requires verified boolean settlement"
            )
        full = _probability(self.full_probability, "full_probability")
        ablated: dict[str, float] = {}
        for field_key, probability in self.ablated_probabilities.items():
            if not str(field_key).strip():
                raise WorldModelValidationError("ablation field key cannot be blank")
            ablated[str(field_key)] = _probability(
                probability,
                f"ablated probability for {field_key}",
            )
        object.__setattr__(self, "decision_at", decision)
        object.__setattr__(self, "settlement_received_at", settled)
        object.__setattr__(self, "full_probability", full)
        object.__setattr__(
            self,
            "ablated_probabilities",
            MappingProxyType(dict(sorted(ablated.items()))),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "event_cluster_id": self.event_cluster_id,
            "snapshot_id": self.snapshot_id,
            "decision_at": iso(self.decision_at),
            "settlement_received_at": iso(self.settlement_received_at),
            "settlement_verified": self.settlement_verified,
            "result_yes": self.result_yes,
            "full_probability": self.full_probability,
            "ablated_probabilities": thaw_json(
                freeze_json(self.ablated_probabilities)
            ),
            "training_regime": self.training_regime,
            "target_regime": self.target_regime,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> WorldModelEvaluationCase:
        ablated = data.get("ablated_probabilities", {})
        if not isinstance(ablated, Mapping):
            raise WorldModelValidationError(
                "ablated_probabilities must be a mapping"
            )
        return cls(
            case_id=str(data["case_id"]),
            event_cluster_id=str(data["event_cluster_id"]),
            snapshot_id=str(data["snapshot_id"]),
            decision_at=parse_iso(data["decision_at"]),
            settlement_received_at=parse_iso(data["settlement_received_at"]),
            settlement_verified=data.get("settlement_verified") is True,
            result_yes=data["result_yes"],
            full_probability=float(data["full_probability"]),
            ablated_probabilities={
                str(key): float(value) for key, value in ablated.items()
            },
            training_regime=str(data["training_regime"]),
            target_regime=str(data["target_regime"]),
        )


def _validated_cases(
    cases: tuple[WorldModelEvaluationCase, ...],
) -> tuple[WorldModelEvaluationCase, ...]:
    ordered = tuple(sorted(cases, key=lambda item: item.case_id))
    ids = tuple(item.case_id for item in ordered)
    clusters = tuple(item.event_cluster_id for item in ordered)
    if len(set(ids)) != len(ids):
        raise WorldModelValidationError("evaluation case_ids contain duplicates")
    if len(set(clusters)) != len(clusters):
        raise WorldModelValidationError(
            "world-model evaluation requires unique event clusters"
        )
    return ordered


def world_state_ablation_report(
    cases: tuple[WorldModelEvaluationCase, ...],
    *,
    minimum_cases: int = 30,
) -> dict[str, object]:
    """Compare full and field-ablated forecasts on verified settled cases."""

    if minimum_cases <= 0:
        raise WorldModelValidationError("minimum_cases must be positive")
    ordered = _validated_cases(cases)
    field_keys = sorted(
        {
            key
            for case in ordered
            for key in case.ablated_probabilities
        }
    )
    fields: list[dict[str, object]] = []
    for field_key in field_keys:
        eligible = tuple(
            case for case in ordered if field_key in case.ablated_probabilities
        )
        full_brier = (
            sum(_brier(case.full_probability, case.result_yes) for case in eligible)
            / len(eligible)
            if eligible
            else None
        )
        ablated_brier = (
            sum(
                _brier(case.ablated_probabilities[field_key], case.result_yes)
                for case in eligible
            )
            / len(eligible)
            if eligible
            else None
        )
        enough = len(eligible) >= minimum_cases
        fields.append(
            {
                "field_key": field_key,
                "status": "EVALUATED" if enough else "INSUFFICIENT_SETTLED_EVIDENCE",
                "case_count": len(eligible),
                "minimum_cases": minimum_cases,
                "full_mean_brier": round(full_brier, 12) if enough else None,
                "ablated_mean_brier": round(ablated_brier, 12) if enough else None,
                "brier_degradation_when_ablated": (
                    round(ablated_brier - full_brier, 12) if enough else None
                ),
            }
        )
    evaluated = sum(item["status"] == "EVALUATED" for item in fields)
    status = (
        "EVALUATED"
        if fields and evaluated == len(fields)
        else (
            "PARTIALLY_EVALUATED"
            if evaluated
            else "INSUFFICIENT_SETTLED_EVIDENCE"
        )
    )
    body: dict[str, object] = {
        "schema_version": 1,
        "report_kind": "world_state_ablation",
        "status": status,
        "case_count": len(ordered),
        "unique_event_cluster_count": len(ordered),
        "minimum_cases_per_field": minimum_cases,
        "settlement_verified_only": True,
        "fields": fields,
        "limitations": (
            []
            if status == "EVALUATED"
            else ["no_claim_without_minimum_verified_settled_cluster_count"]
        ),
    }
    body["report_id"] = digest_json(body)
    return body


def regime_transfer_report(
    cases: tuple[WorldModelEvaluationCase, ...],
    *,
    minimum_cases: int = 30,
) -> dict[str, object]:
    """Measure verified forecast performance across training/target regimes."""

    if minimum_cases <= 0:
        raise WorldModelValidationError("minimum_cases must be positive")
    ordered = _validated_cases(cases)
    pairs = sorted({(case.training_regime, case.target_regime) for case in ordered})
    transfers: list[dict[str, object]] = []
    for training_regime, target_regime in pairs:
        eligible = tuple(
            case
            for case in ordered
            if case.training_regime == training_regime
            and case.target_regime == target_regime
        )
        enough = len(eligible) >= minimum_cases
        transfers.append(
            {
                "training_regime": training_regime,
                "target_regime": target_regime,
                "in_domain": training_regime == target_regime,
                "status": "EVALUATED" if enough else "INSUFFICIENT_SETTLED_EVIDENCE",
                "case_count": len(eligible),
                "minimum_cases": minimum_cases,
                "mean_brier": (
                    round(
                        sum(
                            _brier(case.full_probability, case.result_yes)
                            for case in eligible
                        )
                        / len(eligible),
                        12,
                    )
                    if enough
                    else None
                ),
                "mean_log_loss": (
                    round(
                        sum(
                            _log_loss(case.full_probability, case.result_yes)
                            for case in eligible
                        )
                        / len(eligible),
                        12,
                    )
                    if enough
                    else None
                ),
            }
        )
    evaluated = sum(item["status"] == "EVALUATED" for item in transfers)
    status = (
        "EVALUATED"
        if transfers and evaluated == len(transfers)
        else (
            "PARTIALLY_EVALUATED"
            if evaluated
            else "INSUFFICIENT_SETTLED_EVIDENCE"
        )
    )
    body: dict[str, object] = {
        "schema_version": 1,
        "report_kind": "world_model_regime_transfer",
        "status": status,
        "case_count": len(ordered),
        "unique_event_cluster_count": len(ordered),
        "minimum_cases_per_transfer": minimum_cases,
        "settlement_verified_only": True,
        "transfers": transfers,
        "limitations": (
            []
            if status == "EVALUATED"
            else ["no_transfer_claim_without_verified_settled_evidence"]
        ),
    }
    body["report_id"] = digest_json(body)
    return body
