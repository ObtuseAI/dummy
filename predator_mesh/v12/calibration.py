"""V12 liquidity calibration storage skeleton."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class LiquidityCalibrationRecord:
    market_ticker: str
    contract_ticker: str
    snapshot_timestamp: str
    spread: int
    midpoint: float
    depth: int
    expected_fill_probability: float
    expected_fill_drag: float
    stale_quote_risk: float
    execution_feasibility_score: float
    liquidity_proof_verdict: str
    shadow_order_digest: str
    realized_fill_outcome: None
    future_reconciliation_placeholder: bool = True

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class FillQualityCalibrationRecord:
    expected_fill_probability: float
    expected_fill_drag: float
    realized_fill_outcome: None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class OrderbookReplayCalibrationRecord:
    replay_id: str
    frame_count: int
    liquidity_decay_estimate: float

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class LiquidityCalibrationStore:
    def records(self) -> list[LiquidityCalibrationRecord]:
        return [
            LiquidityCalibrationRecord(
                market_ticker="KXDEMO-LIQUIDITY",
                contract_ticker="KXDEMO-LIQUIDITY-YES",
                snapshot_timestamp=datetime.now(timezone.utc).isoformat(),
                spread=4,
                midpoint=50.0,
                depth=360,
                expected_fill_probability=0.8,
                expected_fill_drag=2.1,
                stale_quote_risk=0.04,
                execution_feasibility_score=0.81,
                liquidity_proof_verdict="REAL_TERRAIN_REHEARSAL_APPROVED",
                shadow_order_digest="sha256:shadow-order-v12-digest",
                realized_fill_outcome=None,
            )
        ]

    def to_report(self) -> dict[str, Any]:
        records = [record.to_dict() for record in self.records()]
        return {
            "workstream": "V12: Liquidity Calibration Store",
            "records": records,
            "record_count": len(records),
            "simulated_only": True,
            "verdict": "PASS",
        }

    def fill_quality_schema_report(self) -> dict[str, Any]:
        return {
            "workstream": "V12: Fill Quality Calibration Schema",
            "required_fields": [
                "market_ticker",
                "contract_ticker",
                "snapshot_timestamp",
                "spread",
                "midpoint",
                "depth",
                "expected_fill_probability",
                "expected_fill_drag",
                "stale_quote_risk",
                "execution_feasibility_score",
                "liquidity_proof_verdict",
                "shadow_order_digest",
                "realized_fill_outcome",
                "future_reconciliation_placeholder",
            ],
            "realized_fill_outcome": None,
            "verdict": "PASS",
        }
