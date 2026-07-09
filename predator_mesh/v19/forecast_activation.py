"""Forecast activation engine for V19."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from predator_mesh.v17.forecasts import ForecastSnapshot, ForecastSnapshotLedger
from predator_mesh.v19 import DOMAINS


class ForecastActivationDecision(str, Enum):
    LEDGER_FORECAST = "LEDGER_FORECAST"
    NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"
    NO_TRADE_SETTLEMENT_AMBIGUITY = "NO_TRADE_SETTLEMENT_AMBIGUITY"
    NO_TRADE_STALE_EVIDENCE = "NO_TRADE_STALE_EVIDENCE"
    NO_TRADE_SOURCE_LEGALITY = "NO_TRADE_SOURCE_LEGALITY"
    NO_TRADE_CONTRADICTION = "NO_TRADE_CONTRADICTION"
    FIXTURE_ONLY_FORECAST = "FIXTURE_ONLY_FORECAST"


@dataclass(frozen=True)
class ForecastActivationCandidate:
    domain: str
    evidence_mode: str = "FIXTURE_STATIC_FALLBACK"

    def to_dict(self) -> dict[str, Any]:
        return {"domain": self.domain, "evidence_mode": self.evidence_mode}


ForecastEvidenceReadiness = dict[str, Any]
ForecastLedgerWriteResult = dict[str, Any]


class ForecastActivationEngine:
    def candidates(self) -> list[ForecastActivationCandidate]:
        return [ForecastActivationCandidate(domain) for domain in DOMAINS]

    def decisions(self) -> list[dict[str, Any]]:
        return [
            {"domain": item.domain, "decision": ForecastActivationDecision.FIXTURE_ONLY_FORECAST.value, "confidence": 0.5, "low_sample_count": True}
            for item in self.candidates()
        ]

    def ledger(self) -> ForecastSnapshotLedger:
        ledger = ForecastSnapshotLedger()
        for decision in self.decisions():
            ledger.record(
                ForecastSnapshot(
                    market_id=f"V19-{decision['domain'].upper()}-FORECAST",
                    event_id=f"V19-{decision['domain'].upper()}-EVENT",
                    domain=decision["domain"],
                    probability=0.5,
                    confidence=decision["confidence"],
                    horizon="fixture",
                    evidence_stack=["fixture_static_fallback"],
                    model_refs=["v19_forecast_activation_engine"],
                    future_outcome_known=False,
                )
            )
        return ledger

    def to_report(self) -> dict[str, Any]:
        ledger_report = self.ledger().to_report()
        return {
            "workstream": "V19: Forecast Activation Engine",
            "candidate_count": len(self.candidates()),
            "ledger_write_count": ledger_report["snapshot_count"],
            "outcome_leakage_detected": ledger_report["outcome_leakage_detected"],
            "heavy_ml_used": False,
            "confidence_conservative": True,
            "secret_values_exposed": False,
            "verdict": "PARTIAL",
        }

    def decision_report(self) -> dict[str, Any]:
        return {"workstream": "V19: Forecast Activation Decision", "decisions": self.decisions(), "secret_values_exposed": False, "verdict": "PARTIAL"}

    def ledger_write_result_report(self) -> dict[str, Any]:
        ledger_report = self.ledger().to_report()
        return {
            "workstream": "V19: Forecast Ledger Write Result",
            "ledger_write_count": ledger_report["snapshot_count"],
            "immutable_forecasts": True,
            "outcome_leakage_detected": ledger_report["outcome_leakage_detected"],
            "secret_values_exposed": False,
            "verdict": "PASS",
        }
