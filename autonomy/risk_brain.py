"""Self-managed dynamic risk: the system decides its own caps.

The risk brain replaces static operator caps with limits it derives itself
from (a) live bankroll, (b) realized calibration evidence, and (c) drawdown
state. "Unstoppable compounding" is a survival property: the brain's one
non-negotiable is ruin-avoidance — fractional Kelly, per-market/vertical
budgets, a drawdown ladder that de-risks before variance can end the run,
and an evidence-gated stage ladder so size is always earned, never assumed.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autonomy.fees import (
    kalshi_maker_fee_cents as kalshi_maker_fee_cents,
    kalshi_taker_fee_cents as kalshi_taker_fee_cents,
)
from autonomy.ontology import Stage

# Fraction of full Kelly actually deployed. Quarter-Kelly keeps ~95% of the
# growth rate at a fraction of the variance and is robust to edge estimation
# error — which is the dominant failure mode of a self-estimated edge.
KELLY_FRACTION = 0.25

# Stage budgets as fractions of bankroll. Per-order notional additionally
# capped in absolute cents so early stages stay tiny regardless of balance.
# group_frac / max_per_group cap correlated clusters (see autonomy/correlation):
# many adjacent buckets on one underlying are one concentrated bet, not many.
# max_days_to_close (0 = uncapped) keeps early stages on near-dated markets:
# with few position slots, capital parked in a market that settles weeks out
# is evidence-accrual frozen — slots must recycle to earn promotion.
STAGE_LIMITS: dict[Stage, dict[str, float | int]] = {
    Stage.SHADOW_ONLY: {"total_frac": 0.0, "market_frac": 0.0, "group_frac": 0.0, "order_abs_cents": 0, "max_open_markets": 0, "max_per_group": 0, "max_days_to_close": 7},
    Stage.CANARY: {"total_frac": 0.02, "market_frac": 0.005, "group_frac": 0.008, "order_abs_cents": 100, "max_open_markets": 5, "max_per_group": 1, "max_days_to_close": 7},
    Stage.RAMP: {"total_frac": 0.10, "market_frac": 0.02, "group_frac": 0.03, "order_abs_cents": 500, "max_open_markets": 12, "max_per_group": 2, "max_days_to_close": 30},
    Stage.CRUISE: {"total_frac": 0.30, "market_frac": 0.05, "group_frac": 0.08, "order_abs_cents": 2500, "max_open_markets": 25, "max_per_group": 3, "max_days_to_close": 0},
}

# Drawdown ladder (fraction below equity peak) -> sizing multiplier.
DRAWDOWN_LADDER = [
    (0.10, 0.5),  # -10%: half size
    (0.20, 0.25),  # -20%: quarter size + stage demotion
    (0.30, 0.0),  # -30%: hard self-stop
]

# Evidence required to self-promote a stage.
PROMOTION_MIN_SETTLED = 20
PROMOTION_MIN_EDGE_CENTS = 0.0  # realized P&L per contract after fees must exceed this
DEMOTION_COOLOFF_HOURS = 24
# V2 requires a witnessed positive fill before any settlement can affect P&L
# or promotion evidence. Older state files may contain optimistic shadow P&L
# from pending orders and are reset at the evidence counters only.
ACCOUNTING_VERSION = 2


def kelly_fraction_yes(probability: float, price_cents: int) -> float:
    """Full-Kelly bankroll fraction for buying YES at price_cents.

    Binary payoff: win (100 - p) per contract, lose p. f* = (q*100 - p)/(100 - p).
    Clamped to [0, 1]; negative edge -> 0.
    """
    if not (1 <= price_cents <= 99):
        return 0.0
    edge = probability * 100.0 - price_cents
    if edge <= 0:
        return 0.0
    return max(0.0, min(1.0, edge / (100.0 - price_cents)))


@dataclass
class RiskState:
    bankroll_cents: int
    equity_peak_cents: int
    stage: Stage
    open_exposure_cents: int
    open_markets: int
    daily_pnl_cents: int
    settled_count_at_stage: int
    realized_pnl_per_contract_cents: float
    last_demotion_at: str | None = None
    hard_stopped: bool = False
    stop_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.__dict__)
        data["stage"] = int(self.stage)
        return data


@dataclass(frozen=True)
class OrderBudget:
    """The brain's answer for one proposed order."""

    allowed: bool
    max_notional_cents: int
    sizing_multiplier: float
    reason: str
    risk_snapshot: dict[str, Any] = field(default_factory=dict)


class RiskBrain:
    """Derives every limit from live state; persists its own stage ledger."""

    def __init__(self, state_path: Path | str = Path("runtime/autonomy/risk_state.json")):
        self.state_path = Path(state_path)

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def load_state(self, bankroll_cents: int) -> RiskState:
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text(encoding="utf-8"))
                accounting_current = int(data.get("accounting_version", 1)) >= ACCOUNTING_VERSION
                state = RiskState(
                    bankroll_cents=bankroll_cents,
                    equity_peak_cents=max(int(data.get("equity_peak_cents", bankroll_cents)), bankroll_cents),
                    stage=Stage(int(data.get("stage", Stage.CANARY))),
                    open_exposure_cents=int(data.get("open_exposure_cents", 0)),
                    open_markets=int(data.get("open_markets", 0)),
                    daily_pnl_cents=(int(data.get("daily_pnl_cents", 0))
                                     if accounting_current else 0),
                    settled_count_at_stage=(int(data.get("settled_count_at_stage", 0))
                                            if accounting_current else 0),
                    realized_pnl_per_contract_cents=(
                        float(data.get("realized_pnl_per_contract_cents", 0.0))
                        if accounting_current else 0.0
                    ),
                    last_demotion_at=data.get("last_demotion_at"),
                    hard_stopped=bool(data.get("hard_stopped", False)),
                    stop_reason=str(data.get("stop_reason", "")),
                )
                return state
            except Exception:
                pass
        return RiskState(
            bankroll_cents=bankroll_cents,
            equity_peak_cents=bankroll_cents,
            stage=Stage.CANARY,
            open_exposure_cents=0,
            open_markets=0,
            daily_pnl_cents=0,
            settled_count_at_stage=0,
            realized_pnl_per_contract_cents=0.0,
        )

    def save_state(self, state: RiskState) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            **state.to_dict(),
            "accounting_version": ACCOUNTING_VERSION,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        self.state_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    # ------------------------------------------------------------------
    # Drawdown + stage machinery
    # ------------------------------------------------------------------

    def drawdown_fraction(self, state: RiskState) -> float:
        if state.equity_peak_cents <= 0:
            return 0.0
        return max(0.0, 1.0 - state.bankroll_cents / state.equity_peak_cents)

    def sizing_multiplier(self, state: RiskState) -> float:
        dd = self.drawdown_fraction(state)
        multiplier = 1.0
        for threshold, mult in DRAWDOWN_LADDER:
            if dd >= threshold - 1e-9:
                multiplier = mult
        return multiplier

    def apply_drawdown_policy(self, state: RiskState) -> RiskState:
        """Demote/stop on drawdown; called every cycle before any sizing."""
        dd = self.drawdown_fraction(state)
        if dd >= DRAWDOWN_LADDER[2][0] - 1e-9:
            state.hard_stopped = True
            state.stop_reason = f"drawdown {dd:.1%} breached hard-stop ladder"
            return state
        if dd >= DRAWDOWN_LADDER[1][0] - 1e-9 and state.stage > Stage.CANARY:
            state.stage = Stage(int(state.stage) - 1)
            state.settled_count_at_stage = 0
            state.last_demotion_at = datetime.now(timezone.utc).isoformat()
        return state

    def maybe_promote(self, state: RiskState) -> RiskState:
        """Self-promotion strictly on realized evidence, with cooloff."""
        if state.stage >= Stage.CRUISE or state.hard_stopped:
            return state
        if state.last_demotion_at:
            try:
                last = datetime.fromisoformat(state.last_demotion_at)
                hours = (datetime.now(timezone.utc) - last).total_seconds() / 3600.0
                if hours < DEMOTION_COOLOFF_HOURS:
                    return state
            except Exception:
                pass
        if (
            state.settled_count_at_stage >= PROMOTION_MIN_SETTLED
            and state.realized_pnl_per_contract_cents > PROMOTION_MIN_EDGE_CENTS
            and self.drawdown_fraction(state) < DRAWDOWN_LADDER[0][0]
        ):
            state.stage = Stage(int(state.stage) + 1)
            state.settled_count_at_stage = 0
        return state

    # ------------------------------------------------------------------
    # Per-order budget
    # ------------------------------------------------------------------

    def order_budget(
        self,
        state: RiskState,
        market_ticker: str,
        market_exposure_cents: int,
        kelly: float,
        group_exposure_cents: int = 0,
        group_open_count: int = 0,
    ) -> OrderBudget:
        snapshot = {
            "stage": int(state.stage),
            "bankroll_cents": state.bankroll_cents,
            "drawdown": round(self.drawdown_fraction(state), 4),
            "open_exposure_cents": state.open_exposure_cents,
            "open_markets": state.open_markets,
            "group_open_count": group_open_count,
        }
        if state.hard_stopped:
            return OrderBudget(False, 0, 0.0, f"hard_stopped: {state.stop_reason}", snapshot)
        if market_exposure_cents > 0:
            return OrderBudget(False, 0, 0.0, "existing open position in market", snapshot)
        limits = STAGE_LIMITS[state.stage]
        if limits["order_abs_cents"] == 0:
            return OrderBudget(False, 0, 0.0, "stage is shadow-only", snapshot)
        if state.open_markets >= int(limits["max_open_markets"]) and market_exposure_cents == 0:
            return OrderBudget(False, 0, 0.0, "max open markets for stage", snapshot)
        # Correlation guard: refuse to stack a new position onto a cluster that
        # already holds the stage's allowed number of correlated bets.
        if group_open_count >= int(limits["max_per_group"]) and market_exposure_cents == 0:
            return OrderBudget(False, 0, 0.0, "max correlated positions per group for stage", snapshot)

        multiplier = self.sizing_multiplier(state)
        total_budget = int(state.bankroll_cents * float(limits["total_frac"]) * multiplier)
        market_budget = int(state.bankroll_cents * float(limits["market_frac"]) * multiplier)
        group_budget = int(state.bankroll_cents * float(limits["group_frac"]) * multiplier)
        remaining_total = max(0, total_budget - state.open_exposure_cents)
        remaining_market = max(0, market_budget - market_exposure_cents)
        remaining_group = max(0, group_budget - group_exposure_cents)
        kelly_budget = int(state.bankroll_cents * kelly * KELLY_FRACTION * multiplier)

        notional = min(int(limits["order_abs_cents"]), remaining_total, remaining_market,
                       remaining_group, kelly_budget)
        if notional < 1:
            return OrderBudget(False, 0, multiplier, "no budget after caps (total/market/group/kelly)", snapshot)
        return OrderBudget(True, notional, multiplier, "within self-set budgets", snapshot)
