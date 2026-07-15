"""Normalized health variables and immutable Phase 7 readings."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from dummy.organisms.models import iso, parse_iso


class HealthVariable(str, Enum):
    CALIBRATION_ERROR = "calibration_error"
    SOURCE_CONCENTRATION = "source_concentration"
    MODEL_FAMILY_CONCENTRATION = "model_family_concentration"
    CONTESTED_PERFORMANCE = "contested_performance"
    FORECAST_DIVERSITY = "forecast_diversity"
    MARKET_COVERAGE = "market_coverage"
    DATA_FRESHNESS = "data_freshness"
    LEDGER_HEALTH = "ledger_health"
    FILL_REALISM = "fill_realism"
    SETTLEMENT_LAG = "settlement_lag"
    SIMULATION_DETERMINISM = "simulation_determinism"
    QUEUE_PRESSURE = "queue_pressure"
    COMPUTE_PRESSURE = "compute_pressure"
    MUTATION_PRESSURE = "mutation_pressure"
    CHALLENGER_SURVIVAL = "challenger_survival"
    OVERCONFIDENCE_RATE = "overconfidence_rate"
    ABSTENTION_RATE = "abstention_rate"
    LIVE_GATE_DISTANCE = "live_gate_distance"
    DRIFT_ALERTS = "drift_alerts"


class RiskDirection(str, Enum):
    HIGHER_IS_WORSE = "HIGHER_IS_WORSE"
    LOWER_IS_WORSE = "LOWER_IS_WORSE"
    DISTANCE_FROM_TARGET = "DISTANCE_FROM_TARGET"


@dataclass(frozen=True, slots=True)
class HealthPolicy:
    variable: HealthVariable
    direction: RiskDirection
    healthy_boundary: float
    warning_boundary: float
    critical_boundary: float
    target: float | None
    interventions: tuple[str, ...]

    def __post_init__(self) -> None:
        values = (
            float(self.healthy_boundary),
            float(self.warning_boundary),
            float(self.critical_boundary),
        )
        if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in values):
            raise ValueError("health thresholds must be finite values in [0, 1]")
        if self.direction is RiskDirection.HIGHER_IS_WORSE:
            valid = values[0] < values[1] < values[2]
        elif self.direction is RiskDirection.LOWER_IS_WORSE:
            valid = values[0] > values[1] > values[2]
        else:
            valid = values[0] < values[1] < values[2]
            if self.target is None or not 0.0 <= float(self.target) <= 1.0:
                raise ValueError("distance policies require a target in [0, 1]")
            if max(float(self.target), 1.0 - float(self.target)) < values[2]:
                raise ValueError("critical distance exceeds the target's possible range")
        if self.direction is not RiskDirection.DISTANCE_FROM_TARGET and self.target is not None:
            raise ValueError("non-distance health policies cannot define a target")
        if not valid:
            raise ValueError("health thresholds are not ordered for their risk direction")
        interventions = tuple(sorted(str(item).strip() for item in self.interventions))
        if not interventions or any(not item for item in interventions):
            raise ValueError("health policy requires named interventions")
        if len(interventions) != len(set(interventions)):
            raise ValueError("health interventions must be unique")
        object.__setattr__(self, "interventions", interventions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variable": self.variable.value,
            "direction": self.direction.value,
            "healthy_boundary": self.healthy_boundary,
            "warning_boundary": self.warning_boundary,
            "critical_boundary": self.critical_boundary,
            "target": self.target,
            "interventions": list(self.interventions),
        }


@dataclass(frozen=True, slots=True)
class HealthReading:
    variable: HealthVariable
    value: float | None
    observed_at: datetime
    evidence_ids: tuple[str, ...]
    source_reference: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", parse_iso(self.observed_at))
        evidence_ids = tuple(sorted(str(item).strip() for item in self.evidence_ids))
        if any(not item for item in evidence_ids) or len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("health evidence IDs must be non-empty and unique")
        object.__setattr__(self, "evidence_ids", evidence_ids)
        if not self.source_reference.strip():
            raise ValueError("health source reference must be non-empty")
        if self.value is not None:
            parsed = float(self.value)
            if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
                raise ValueError("normalized health readings must be in [0, 1]")
            if not evidence_ids:
                raise ValueError("measured health readings require evidence IDs")
            object.__setattr__(self, "value", parsed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variable": self.variable.value,
            "value": self.value,
            "observed_at": iso(self.observed_at),
            "evidence_ids": list(self.evidence_ids),
            "source_reference": self.source_reference,
        }


__all__ = ["HealthPolicy", "HealthReading", "HealthVariable", "RiskDirection"]
