"""Typed deterministic resource and marginal-utility contracts."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from numbers import Integral
from typing import Any


class MetabolismValidationError(ValueError):
    """A resource measurement or utility claim is malformed."""


def _nonnegative(value: int | float | None, name: str) -> int | float | None:
    if value is None:
        return None
    if not math.isfinite(float(value)) or float(value) < 0.0:
        raise MetabolismValidationError(f"{name} must be non-negative or unknown")
    return value


def _nonnegative_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
        raise MetabolismValidationError(f"{name} must be a non-negative integer")
    return int(value)


def _unit_interval(value: float, name: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
        raise MetabolismValidationError(f"{name} must be in [0, 1]")
    return parsed


@dataclass(frozen=True, slots=True)
class ResourceUsage:
    provider_calls: int
    cpu_ms: float | None
    peak_memory_bytes: int | None
    simulations: int
    monte_carlo_paths: int
    data_fetches: int
    storage_bytes: int
    replay_ms: float | None
    hydration_ms: float | None
    agent_count: int
    wall_clock_ms: float | None
    message_count: int
    payload_bytes: int

    def __post_init__(self) -> None:
        integer_fields = (
            "provider_calls",
            "peak_memory_bytes",
            "simulations",
            "monte_carlo_paths",
            "data_fetches",
            "storage_bytes",
            "agent_count",
            "message_count",
            "payload_bytes",
        )
        for field_name in integer_fields:
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _nonnegative_int(value, field_name))
        for field_name in ("cpu_ms", "replay_ms", "hydration_ms", "wall_clock_ms"):
            object.__setattr__(
                self,
                field_name,
                _nonnegative(getattr(self, field_name), field_name),
            )

    @property
    def unmeasured(self) -> tuple[str, ...]:
        return tuple(
            field_name
            for field_name in self.__dataclass_fields__
            if getattr(self, field_name) is None
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            field_name: getattr(self, field_name)
            for field_name in self.__dataclass_fields__
        } | {"unmeasured": list(self.unmeasured)}

    def guard_mapping(self) -> dict[str, int | float | None]:
        return {
            "agent_count": self.agent_count,
            "message_count": self.message_count,
            "payload_bytes": self.payload_bytes,
            "storage_bytes": self.storage_bytes,
            "cpu_ms": self.cpu_ms,
            "peak_memory_bytes": self.peak_memory_bytes,
            "wall_clock_ms": self.wall_clock_ms,
        }


@dataclass(frozen=True, slots=True)
class ResourceBudget:
    max_agent_count: int = 7
    max_message_count: int = 8
    max_payload_bytes: int = 512_000
    max_storage_bytes: int = 1_000_000
    max_cpu_ms: float = 5_000.0
    max_peak_memory_bytes: int = 536_870_912
    max_wall_clock_ms: float = 5_000.0

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            if isinstance(value, bool) or not math.isfinite(float(value)) or value <= 0:
                raise MetabolismValidationError("resource budgets must be positive")

    def guard_mapping(self) -> dict[str, int]:
        return {
            "agent_count": self.max_agent_count,
            "message_count": self.max_message_count,
            "payload_bytes": self.max_payload_bytes,
            "storage_bytes": self.max_storage_bytes,
            "cpu_ms": self.max_cpu_ms,
            "peak_memory_bytes": self.max_peak_memory_bytes,
            "wall_clock_ms": self.max_wall_clock_ms,
        }


class UtilityStatus(str, Enum):
    ESTIMATED_UNCALIBRATED = "ESTIMATED_UNCALIBRATED"
    UNRESOLVED_UNMEASURED_COST = "UNRESOLVED_UNMEASURED_COST"


@dataclass(frozen=True, slots=True)
class InformationGainEstimate:
    proxy_value: float
    disagreement_component: float
    independence_component: float
    calibration_component: float
    status: str = "UNCALIBRATED_PROXY"

    def __post_init__(self) -> None:
        for field_name in (
            "proxy_value",
            "disagreement_component",
            "independence_component",
            "calibration_component",
        ):
            value = _unit_interval(getattr(self, field_name), field_name)
            object.__setattr__(self, field_name, value)
        if self.status != "UNCALIBRATED_PROXY":
            raise MetabolismValidationError("information gain must remain an uncalibrated proxy")

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_information_gain_proxy": self.proxy_value,
            "disagreement_component": self.disagreement_component,
            "independence_component": self.independence_component,
            "calibration_component": self.calibration_component,
            "status": self.status,
            "claim": "proxy_not_calibrated_expected_information_gain",
        }


@dataclass(frozen=True, slots=True)
class CostEstimate:
    normalized_cost: float | None
    compute_cost: float | None
    latency_cost: float | None
    duplication_cost: float
    execution_irrelevance_cost: float
    unmeasured: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("normalized_cost", "compute_cost", "latency_cost"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _unit_interval(value, field_name))
        for field_name in ("duplication_cost", "execution_irrelevance_cost"):
            object.__setattr__(
                self,
                field_name,
                _unit_interval(getattr(self, field_name), field_name),
            )
        unmeasured = tuple(sorted(str(item).strip() for item in self.unmeasured))
        if any(not item for item in unmeasured) or len(set(unmeasured)) != len(unmeasured):
            raise MetabolismValidationError("unmeasured resource names must be unique")
        if self.normalized_cost is None:
            if not unmeasured or self.compute_cost is not None or self.latency_cost is not None:
                raise MetabolismValidationError("unknown normalized cost requires unknown compute")
        elif unmeasured or self.compute_cost is None or self.latency_cost is None:
            raise MetabolismValidationError("estimated cost requires complete measurements")
        object.__setattr__(self, "unmeasured", unmeasured)

    def to_dict(self) -> dict[str, Any]:
        return {
            "normalized_cost": self.normalized_cost,
            "compute_cost": self.compute_cost,
            "latency_cost": self.latency_cost,
            "duplication_cost": self.duplication_cost,
            "execution_irrelevance_cost": self.execution_irrelevance_cost,
            "unmeasured": list(self.unmeasured),
        }


@dataclass(frozen=True, slots=True)
class MarginalUtility:
    information_gain: InformationGainEstimate
    expected_calibration_value: float
    expected_decision_improvement: float
    costs: CostEstimate
    utility: float | None
    status: UtilityStatus

    def __post_init__(self) -> None:
        for field_name in (
            "expected_calibration_value",
            "expected_decision_improvement",
        ):
            object.__setattr__(
                self,
                field_name,
                _unit_interval(getattr(self, field_name), field_name),
            )
        if self.status is UtilityStatus.UNRESOLVED_UNMEASURED_COST:
            if self.utility is not None or self.costs.normalized_cost is not None:
                raise MetabolismValidationError("unresolved utility cannot contain an estimate")
        elif self.status is UtilityStatus.ESTIMATED_UNCALIBRATED:
            if (
                self.utility is None
                or not math.isfinite(float(self.utility))
                or self.costs.normalized_cost is None
            ):
                raise MetabolismValidationError("estimated utility requires measured finite cost")
        else:
            raise MetabolismValidationError("unknown marginal utility status")

    def to_dict(self) -> dict[str, Any]:
        return {
            "information_gain": self.information_gain.to_dict(),
            "expected_calibration_value": self.expected_calibration_value,
            "expected_decision_improvement": self.expected_decision_improvement,
            "costs": self.costs.to_dict(),
            "marginal_utility": self.utility,
            "status": self.status.value,
            "automatic_resource_expansion": False,
        }
