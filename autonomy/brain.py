"""The predator loop: one cycle = scan -> signal -> forecast -> decide ->
execute -> reconcile -> learn. Honest status enums out of every cycle."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from autonomy.allocator import Allocator
from autonomy.executor import Executor, kill_switch_active
from autonomy.forecaster import EnsembleForecaster
from autonomy.learner import Learner
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import DecisionAction, MarketView, OutcomeKind, SessionMode, TradeOutcome
from autonomy.reconciler import Reconciler, settlement_pnl_cents
from autonomy.risk_brain import RiskBrain, RiskState
from autonomy.scanner import MarketScanner
from autonomy.signals.base import SourceRegistry

SHADOW_BANKROLL_CENTS = 10_000
MAX_DECISIONS_PER_CYCLE = 10
# Only the top-K markets by |edge| get the expensive LLM panel each cycle.
DEBATE_TOP_K = 5


@dataclass
class CycleReport:
    status: str
    mode: str
    stage: int
    bankroll_cents: int
    markets_scanned: int = 0
    signals_generated: int = 0
    decisions_made: int = 0
    orders_placed: int = 0
    abstained: int = 0
    settlements: int = 0
    phantom_settlements: int = 0
    weight_updates: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


class PredatorBrain:
    def __init__(
        self,
        mode: SessionMode,
        ledger: AutonomyLedger,
        registry: SourceRegistry,
        scanner: MarketScanner,
        risk_brain: RiskBrain,
        executor: Executor,
        reconciler: Reconciler,
        learner: Learner,
        balance_fn: Any | None = None,
        router: Any | None = None,
    ) -> None:
        self.mode = mode
        self.ledger = ledger
        self.registry = registry
        self.scanner = scanner
        self.risk_brain = risk_brain
        self.executor = executor
        self.reconciler = reconciler
        self.learner = learner
        self.balance_fn = balance_fn
        # Optional LLM panel; when present, adjudicates the top-K edge markets.
        self.router = router

    # ------------------------------------------------------------------

    def _bankroll_cents(self) -> int:
        if self.mode is SessionMode.LIVE and self.balance_fn is not None:
            try:
                return int(self.balance_fn())
            except Exception:
                pass
        return SHADOW_BANKROLL_CENTS

    def _market_exposure(self, state: RiskState, ticker: str) -> int:
        exposure = 0
        for open_decision in self.ledger.open_decisions():
            if open_decision["market_ticker"] == ticker:
                exposure += int(open_decision["price_cents"]) * int(open_decision["count"])
        return exposure

    def _group_exposure(self, ticker: str) -> tuple[int, int]:
        """(exposure_cents, open_position_count) for the ticker's correlation group."""
        from autonomy.correlation import group_key

        target = group_key(ticker)
        exposure = 0
        count = 0
        for open_decision in self.ledger.open_decisions():
            if group_key(open_decision["market_ticker"]) == target:
                exposure += int(open_decision["price_cents"]) * int(open_decision["count"])
                count += 1
        return exposure, count

    def _apply_settlements(self, state: RiskState, report: CycleReport) -> None:
        for ticker, result_yes in self.reconciler.reconcile_settlements():
            report.settlements += 1
            report.weight_updates.update(self.learner.apply_settlement(ticker, result_yes))
            # Realized P&L for our filled/accepted positions in that market.
            for open_decision in self.ledger.open_decisions():
                if open_decision["market_ticker"] != ticker:
                    continue
                pnl = settlement_pnl_cents(
                    str(open_decision["side"]), int(open_decision["price_cents"]),
                    int(open_decision["count"]), result_yes,
                )
                won = pnl > 0
                self.ledger.record_outcome(
                    TradeOutcome(
                        decision_id=str(open_decision["decision_id"]),
                        market_ticker=ticker,
                        kind=OutcomeKind.SETTLED_WIN if won else OutcomeKind.SETTLED_LOSS,
                        order_id=open_decision.get("order_id"),
                        fill_count=int(open_decision["count"]),
                        fill_price_cents=int(open_decision["price_cents"]),
                        pnl_cents=pnl,
                        broker_contacted=self.mode is SessionMode.LIVE,
                        detail={"result_yes": result_yes},
                    )
                )
                state.daily_pnl_cents += pnl
                state.settled_count_at_stage += 1
                count = max(1, int(open_decision["count"]))
                # Exponential moving realized edge per contract.
                state.realized_pnl_per_contract_cents = (
                    0.8 * state.realized_pnl_per_contract_cents + 0.2 * (pnl / count)
                )

    def _apply_phantom_settlements(self, report: CycleReport) -> None:
        """Grade every forecasted market that settled — trades or not.

        This is the calibration firehose: trust weights learn from the whole
        forecast surface, not just the stage-capped handful of positions.
        Never touches risk state (there is no position to P&L).
        """
        try:
            phantom = self.reconciler.reconcile_forecast_settlements(list(self.scanner.watchlist))
        except Exception:
            return
        for ticker, result_yes in phantom:
            report.phantom_settlements += 1
            report.weight_updates.update(self.learner.apply_settlement(ticker, result_yes))

    # ------------------------------------------------------------------

    async def _adjudicate_top_k(self, forecaster, scored: list, report: CycleReport) -> None:
        """Run the LLM debate on the top-K edge markets and re-fuse in place."""
        from autonomy.debate import run_debate

        for idx in range(min(DEBATE_TOP_K, len(scored))):
            market, forecast, signals = scored[idx]
            try:
                result = await run_debate(self.router, market, base_prob=forecast.probability_yes)
            except Exception:
                result = None
            if result is None:
                continue
            debate_signal = result.to_signal(market.ticker)
            self.ledger.record_signal(debate_signal)
            report.signals_generated += 1
            refused = forecaster.fuse(market, list(signals) + [debate_signal])
            if refused is not None:
                scored[idx] = (market, refused, list(signals) + [debate_signal])
                report.notes.append(f"debate:{market.ticker}:{result.probability_yes:.2f}")

    async def run_cycle(self) -> CycleReport:
        bankroll = self._bankroll_cents()
        state = self.risk_brain.load_state(bankroll)
        report = CycleReport(status="CYCLE_OK", mode=self.mode.value, stage=int(state.stage),
                             bankroll_cents=bankroll)

        if kill_switch_active(self.executor.kill_path):
            report.status = "HALTED_KILL_SWITCH"
            return report

        state = self.risk_brain.apply_drawdown_policy(state)
        if state.hard_stopped:
            self.risk_brain.save_state(state)
            report.status = f"HALTED_SELF_STOP: {state.stop_reason}"
            return report

        self._apply_settlements(state, report)
        self._apply_phantom_settlements(report)
        self.reconciler.reconcile_open_orders()
        state = self.risk_brain.maybe_promote(state)
        report.stage = int(state.stage)

        # Per-cycle source hooks (ESPN cache reset + incremental Elo retrain).
        self.registry.on_cycle_start()

        try:
            markets = self.scanner.scan()
        except Exception as exc:
            report.status = f"CYCLE_DEGRADED_SCAN_FAILED:{type(exc).__name__}"
            self.risk_brain.save_state(state)
            return report
        report.markets_scanned = len(markets)

        forecaster = EnsembleForecaster(self.ledger)
        scored: list[tuple[MarketView, Any, list[Any]]] = []
        for market in markets:
            signals = list(self.registry.signals_for(market))
            if not signals:
                continue
            for signal in signals:
                self.ledger.record_signal(signal)
            report.signals_generated += len(signals)
            forecast = forecaster.fuse(market, signals)
            if forecast is None:
                continue
            scored.append((market, forecast, signals))

        # Chase the largest absolute disagreement first; bounded per cycle so
        # one sweep can never spray orders across the whole exchange.
        scored.sort(key=lambda triple: abs(triple[1].edge_yes), reverse=True)

        # LLM panel adjudicates only the top-K edge markets, then re-fuse.
        if self.router is not None and scored:
            await self._adjudicate_top_k(forecaster, scored, report)
            scored.sort(key=lambda triple: abs(triple[1].edge_yes), reverse=True)

        from autonomy.correlation import group_key

        allocator = Allocator(self.risk_brain)
        # In-cycle group accumulation so successive orders on one correlated
        # cluster see each other, not just prior-cycle open positions.
        cycle_group_cents: dict[str, int] = {}
        cycle_group_count: dict[str, int] = {}
        for market, forecast, _signals in scored[:MAX_DECISIONS_PER_CYCLE]:
            gkey = group_key(market.ticker)
            base_cents, base_count = self._group_exposure(market.ticker)
            group_cents = base_cents + cycle_group_cents.get(gkey, 0)
            group_count = base_count + cycle_group_count.get(gkey, 0)
            decision = allocator.decide(
                market, forecast, state,
                self._market_exposure(state, market.ticker),
                group_exposure_cents=group_cents,
                group_open_count=group_count,
            )
            self.ledger.record_decision(decision)
            report.decisions_made += 1
            if decision.action is DecisionAction.ABSTAIN:
                report.abstained += 1
                continue
            outcome = await self.executor.execute(decision)
            self.ledger.record_outcome(outcome)
            if outcome.kind in (OutcomeKind.ACCEPTED, OutcomeKind.SHADOW) and outcome.order_id:
                report.orders_placed += 1
                state.open_exposure_cents += decision.notional_cents
                state.open_markets += 1
                cycle_group_cents[gkey] = cycle_group_cents.get(gkey, 0) + decision.notional_cents
                cycle_group_count[gkey] = cycle_group_count.get(gkey, 0) + 1

        state.equity_peak_cents = max(state.equity_peak_cents, bankroll)
        self.risk_brain.save_state(state)
        self.ledger.record_bankroll(bankroll, state.open_exposure_cents, int(state.stage))
        return report


async def run_loop(brain: PredatorBrain, interval_seconds: float, should_continue) -> list[CycleReport]:
    reports: list[CycleReport] = []
    while should_continue():
        report = await brain.run_cycle()
        reports.append(report)
        if report.status.startswith("HALTED"):
            break
        await asyncio.sleep(interval_seconds)
    return reports
