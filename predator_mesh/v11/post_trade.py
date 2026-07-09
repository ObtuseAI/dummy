"""Post-trade attribution skeleton for simulated V11 fills."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FillQualityOutcome:
    expected_fill_drag: float
    realized_simulated_fill_drag: float

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class SlippageOutcome:
    expected_price: int
    simulated_fill_price: int
    slippage_cents: int

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class ReconcileOutcome:
    status: str
    simulated_only: bool

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class LiquidityPnLAttribution:
    expected_edge_after_fill_drag: float
    simulated_outcome_status: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class EdgeThesisAttribution:
    source_proof_refs: list[str]
    model_proof_refs: list[str]
    forecast_proof_refs: list[str]
    liquidity_proof_refs: list[str]

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class FillAttributionRecord:
    record_id: str
    expected_price: int
    simulated_fill_price: int
    expected_fill_drag: float
    realized_simulated_fill_drag: float
    expected_edge_after_fill_drag: float
    simulated_outcome_status: str
    source_proof_refs: list[str]
    model_proof_refs: list[str]
    forecast_proof_refs: list[str]
    liquidity_proof_refs: list[str]
    simulated_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class PostTradeLedgerSkeleton:
    def records(self) -> list[FillAttributionRecord]:
        return [
            FillAttributionRecord(
                record_id="fill-attr-v11-001",
                expected_price=52,
                simulated_fill_price=53,
                expected_fill_drag=2.0,
                realized_simulated_fill_drag=3.0,
                expected_edge_after_fill_drag=5.0,
                simulated_outcome_status="PARTIAL_FILL_SIMULATED",
                source_proof_refs=["source-bloodline-v10-crypto-btc"],
                model_proof_refs=["live-model-smoke-v3"],
                forecast_proof_refs=["forecast-proof-v11-001"],
                liquidity_proof_refs=["liq-proof-edge-v11-001"],
            )
        ]

    def to_report(self) -> dict[str, Any]:
        records = [record.to_dict() for record in self.records()]
        return {
            "workstream": "V11: Post Trade Ledger Skeleton",
            "records": records,
            "simulated_only": True,
            "verdict": "PASS" if records else "FAIL",
        }

    def schema_report(self) -> dict[str, Any]:
        fields = list(FillAttributionRecord.__dataclass_fields__.keys())
        return {
            "workstream": "V11: Fill Attribution Schema",
            "schema_fields": fields,
            "verdict": "PASS",
        }
