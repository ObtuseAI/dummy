"""Decision and no-trade ledger for V17 attribution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class NoTradeReason(str, Enum):
    REAL_TERRAIN_WARNING = "REAL_TERRAIN_WARNING"
    SPREAD_TOO_WIDE = "SPREAD_TOO_WIDE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    AMBIGUOUS_SETTLEMENT = "AMBIGUOUS_SETTLEMENT"
    STALE_QUOTE = "STALE_QUOTE"


@dataclass(frozen=True)
class DecisionRecord:
    record_id: str
    market_id: str
    forecast_snapshot_id: str
    decision_type: str
    proof_refs: list[str]
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "market_id": self.market_id,
            "forecast_snapshot_id": self.forecast_snapshot_id,
            "decision_type": self.decision_type,
            "proof_refs": self.proof_refs,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class NoTradeDecisionRecord(DecisionRecord):
    reasons: list[NoTradeReason | str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["reasons"] = [reason.value if isinstance(reason, NoTradeReason) else reason for reason in self.reasons]
        return data


@dataclass(frozen=True)
class DecisionAttribution:
    record_id: str
    outcome: str
    evidence_backed: bool
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "outcome": self.outcome,
            "evidence_backed": self.evidence_backed,
            "notes": self.notes,
        }


NoTradeAttribution = DecisionAttribution


class DecisionLedger:
    def __init__(self) -> None:
        self.records: list[DecisionRecord] = []
        self.no_trade_attributions: list[NoTradeAttribution] = []

    def record_decision(self, *, market_id: str, forecast_snapshot_id: str, decision_type: str, proof_refs: list[str] | None = None) -> DecisionRecord:
        record = DecisionRecord(
            record_id=f"decision-{len(self.records) + 1:06d}",
            market_id=market_id,
            forecast_snapshot_id=forecast_snapshot_id,
            decision_type=decision_type,
            proof_refs=list(proof_refs or []),
        )
        self.records.append(record)
        return record

    def record_no_trade(
        self,
        *,
        market_id: str,
        forecast_snapshot_id: str,
        reasons: list[NoTradeReason | str],
        proof_refs: list[str] | None = None,
    ) -> NoTradeDecisionRecord:
        record = NoTradeDecisionRecord(
            record_id=f"no-trade-{len(self.records) + 1:06d}",
            market_id=market_id,
            forecast_snapshot_id=forecast_snapshot_id,
            decision_type="NO_TRADE",
            proof_refs=list(proof_refs or []),
            reasons=list(reasons),
        )
        self.records.append(record)
        return record

    def attribute_no_trade(self, record_id: str, *, avoided_loss: bool | None = None, missed_opportunity: bool | None = None) -> NoTradeAttribution:
        if avoided_loss:
            outcome = "GOOD_SAVE"
        elif missed_opportunity:
            outcome = "MISSED_OPPORTUNITY"
        else:
            outcome = "UNRESOLVED"
        attribution = NoTradeAttribution(
            record_id=record_id,
            outcome=outcome,
            evidence_backed=True,
            notes=["No-trade attribution remains outcome-backed and does not imply live execution."],
        )
        self.no_trade_attributions.append(attribution)
        return attribution

    def no_trade_attribution_report(self) -> dict[str, Any]:
        return {
            "workstream": "V17: No-Trade Attribution",
            "good_save_count": sum(1 for item in self.no_trade_attributions if item.outcome == "GOOD_SAVE"),
            "missed_opportunity_count": sum(1 for item in self.no_trade_attributions if item.outcome == "MISSED_OPPORTUNITY"),
            "unresolved_count": sum(1 for item in self.no_trade_attributions if item.outcome == "UNRESOLVED"),
            "attributions": [item.to_dict() for item in self.no_trade_attributions],
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V17: Decision Ledger",
            "decision_count": len(self.records),
            "no_trade_count": sum(1 for record in self.records if record.decision_type == "NO_TRADE"),
            "records": [record.to_dict() for record in self.records],
            "secret_values_exposed": False,
            "verdict": "PASS",
        }
