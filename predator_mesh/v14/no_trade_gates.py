"""V14 liquidity no-trade hardening reports."""

from __future__ import annotations

from typing import Any

from predator_mesh.v14.launch_readiness import LiquidityLaunchReadinessMatrix


class LiquidityNoTradeGate:
    def __init__(self, *, forensics_report: dict[str, Any] | None = None) -> None:
        self.forensics_report = forensics_report

    def to_report(self) -> dict[str, Any]:
        blockers = LiquidityLaunchReadinessMatrix(forensics_report=self.forensics_report).blockers()
        no_trade = list(dict.fromkeys(blockers + ["NO_OPERATOR_ARMED_MICRO_ORDER"]))
        return {
            "workstream": "V14: Liquidity No Trade Gate",
            "trade_allowed": False,
            "no_trade_reasons": no_trade,
            "market_orders_allowed": False,
            "live_submit_allowed": False,
            "verdict": "PASS",
        }


class FillDragNoTradeReport:
    def __init__(self, *, fill_drag_bps: float = 72.0, threshold_bps: float = 30.0) -> None:
        self.fill_drag_bps = fill_drag_bps
        self.threshold_bps = threshold_bps

    def to_report(self) -> dict[str, Any]:
        blocked = self.fill_drag_bps > self.threshold_bps
        return {
            "workstream": "V14: Fill Drag No Trade",
            "fill_drag_bps": self.fill_drag_bps,
            "threshold_bps": self.threshold_bps,
            "trade_allowed": not blocked,
            "no_trade_reasons": ["FILL_DRAG_TOO_HIGH"] if blocked else [],
            "verdict": "PASS",
        }


class StaleQuoteNoTradeReport:
    def __init__(self, *, snapshot_age_ms: int = 4_500, max_age_ms: int = 1_500) -> None:
        self.snapshot_age_ms = snapshot_age_ms
        self.max_age_ms = max_age_ms

    def to_report(self) -> dict[str, Any]:
        blocked = self.snapshot_age_ms > self.max_age_ms
        return {
            "workstream": "V14: Stale Quote No Trade",
            "snapshot_age_ms": self.snapshot_age_ms,
            "max_age_ms": self.max_age_ms,
            "trade_allowed": not blocked,
            "no_trade_reasons": ["STALE_QUOTE"] if blocked else [],
            "verdict": "PASS",
        }
