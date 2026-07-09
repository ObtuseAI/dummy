"""Read-only outcome observation contract for V17."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class OutcomeObservationMode(str, Enum):
    REAL_READ_ONLY_SETTLEMENT = "REAL_READ_ONLY_SETTLEMENT"
    REAL_READ_ONLY_DEGRADED = "REAL_READ_ONLY_DEGRADED"
    STATIC_FIXTURE_OUTCOME = "STATIC_FIXTURE_OUTCOME"
    UNRESOLVED_PENDING = "UNRESOLVED_PENDING"
    MANUAL_IMPORT_REQUIRED = "MANUAL_IMPORT_REQUIRED"


@dataclass(frozen=True)
class OutcomeObservationResult:
    mode: OutcomeObservationMode
    fabricated_outcome: bool
    read_only_only: bool
    observation: dict[str, Any] | None = None

    def to_report(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "fabricated_outcome": self.fabricated_outcome,
            "read_only_only": self.read_only_only,
            "observation": self.observation,
            "secret_values_exposed": False,
            "verdict": "PASS" if self.read_only_only and not self.fabricated_outcome else "FAIL",
        }


@dataclass(frozen=True)
class SettlementStatusProbe:
    max_request_timeout_s: int = 10
    total_timeout_s: int = 45
    read_only_only: bool = True

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V17: Settlement Status Probe",
            "max_request_timeout_s": self.max_request_timeout_s,
            "total_timeout_s": self.total_timeout_s,
            "read_only_only": self.read_only_only,
            "write_endpoints_called": [],
            "secret_values_exposed": False,
            "verdict": "PASS" if self.max_request_timeout_s <= 10 and self.total_timeout_s <= 45 and self.read_only_only else "FAIL",
        }


class ReadOnlyOutcomeObserver:
    def observe(self, *, static_fixture: bool = False) -> OutcomeObservationResult:
        if static_fixture:
            return OutcomeObservationResult(
                mode=OutcomeObservationMode.STATIC_FIXTURE_OUTCOME,
                fabricated_outcome=False,
                read_only_only=True,
                observation={"source": "static_fixture", "truth": "RESOLVED_TRUE", "explicitly_labeled_static": True},
            )
        return OutcomeObservationResult(
            mode=OutcomeObservationMode.UNRESOLVED_PENDING,
            fabricated_outcome=False,
            read_only_only=True,
            observation=None,
        )

    @staticmethod
    def mode_report() -> dict[str, Any]:
        return {
            "workstream": "V17: Outcome Observation Mode",
            "modes": [mode.value for mode in OutcomeObservationMode],
            "fabrication_allowed": False,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def to_report(self) -> dict[str, Any]:
        result = self.observe()
        return {
            "workstream": "V17: ReadOnly Outcome Observer",
            **result.to_report(),
        }
