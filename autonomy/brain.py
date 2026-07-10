"""The predator loop: one cycle = scan -> signal -> forecast -> decide ->
execute -> reconcile -> learn. Honest status enums out of every cycle."""
from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
MAX_CANDIDATES_EVALUATED = 100
MAX_ORDERS_PER_CYCLE = 10
# Only the top-K markets by |edge| get the expensive LLM panel each cycle.
DEBATE_TOP_K = 5


def edge_velocity(market: MarketView, forecast: Any) -> float:
    """Edge per sqrt-hour to settlement: the compounding-rate ranking metric."""
    hours = 24.0
    try:
        close = datetime.fromisoformat(market.close_time.replace("Z", "+00:00"))
        hours = max(0.5, (close - datetime.now(timezone.utc)).total_seconds() / 3600.0)
    except Exception:
        pass
    return abs(forecast.edge_yes) / math.sqrt(hours)


@dataclass
class CycleReport:
    status: str
    mode: str
    stage: int
    bankroll_cents: int
    markets_scanned: int = 0
    signals_generated: int = 0
    signals_rejected: int = 0
    decisions_made: int = 0
    orders_placed: int = 0
    abstained: int = 0
    settlements: int = 0
    phantom_settlements: int = 0
    shadow_fills: int = 0
    shadow_expirations: int = 0
    trading_halted: bool = False
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
        exchange_status_fn: Any | None = None,
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
        # Optional venue-state probe (autonomy/exchange_status.py); None skips
        # the check entirely (hermetic tests, offline replays).
        self.exchange_status_fn = exchange_status_fn
        # Position-book scope: a live brain counts only broker positions
        # against its slots/exposure; a shadow brain only the shadow book.
        self.book_scope = "live" if mode is SessionMode.LIVE else "shadow"

    # ------------------------------------------------------------------

    def _bankroll_cents(self) -> int:
        if self.mode is SessionMode.LIVE and self.balance_fn is not None:
            try:
                return int(self.balance_fn())
            except Exception:
                # Never size live risk off a made-up number. Fall back to the
                # last persisted live bankroll; failing that, zero — a zero
                # budget places no orders and the cycle still learns.
                try:
                    import json as _json

                    data = _json.loads(self.risk_brain.state_path.read_text(encoding="utf-8"))
                    last = int(data.get("bankroll_cents", 0))
                except Exception:
                    last = 0
                return max(0, last)
        # Shadow drawdown must be driven by the same verified settled-fill P&L
        # used by readiness. A fixed paper bankroll hid losses and prevented
        # the drawdown ladder from doing its job.
        realized = getattr(self.ledger, "realized_pnl_cents", None)
        pnl = int(realized("shadow")) if callable(realized) else 0
        return max(0, SHADOW_BANKROLL_CENTS + pnl)

    def _open_positions(self) -> list[dict[str, Any]]:
        """This brain's own book only (duck-typed for minimal ledger fakes)."""
        try:
            return self.ledger.open_decisions(self.book_scope)
        except TypeError:
            return self.ledger.open_decisions()

    def _market_exposure(self, state: RiskState, ticker: str) -> int:
        exposure = 0
        for open_decision in self._open_positions():
            if open_decision["market_ticker"] == ticker:
                exposure += int(open_decision["price_cents"]) * int(
                    open_decision.get("reserved_count", open_decision["count"])
                )
        return exposure

    def _group_exposure(self, ticker: str) -> tuple[int, int]:
        """(exposure_cents, open_position_count) for the ticker's correlation group."""
        from autonomy.correlation import group_key

        target = group_key(ticker)
        exposure = 0
        count = 0
        for open_decision in self._open_positions():
            if group_key(open_decision["market_ticker"]) == target:
                exposure += int(open_decision["price_cents"]) * int(
                    open_decision.get("reserved_count", open_decision["count"])
                )
                count += 1
        return exposure, count

    def _close_position(self, state: RiskState, open_decision: dict[str, Any],
                        result_yes: bool) -> None:
        """Write the settlement outcome for one open position + risk evidence."""
        filled_count = int(open_decision.get("filled_count", open_decision["count"]) or 0)
        if filled_count <= 0:
            # The order reserved risk but never produced a witnessed fill.
            # Settlement releases it without inventing a position or P&L.
            self.ledger.record_outcome(TradeOutcome(
                decision_id=str(open_decision["decision_id"]),
                market_ticker=str(open_decision["market_ticker"]),
                kind=OutcomeKind.EXPIRED,
                order_id=open_decision.get("order_id"),
                fill_count=0,
                fill_price_cents=None,
                pnl_cents=None,
                broker_contacted=False,
                detail={"reason": "market_settled_before_any_witnessed_fill"},
            ))
            return
        pnl = settlement_pnl_cents(
            str(open_decision["side"]), int(open_decision["price_cents"]),
            filled_count, result_yes,
            market_ticker=str(open_decision["market_ticker"]), liquidity_role="maker",
        )
        won = pnl > 0
        self.ledger.record_outcome(
            TradeOutcome(
                decision_id=str(open_decision["decision_id"]),
                market_ticker=str(open_decision["market_ticker"]),
                kind=OutcomeKind.SETTLED_WIN if won else OutcomeKind.SETTLED_LOSS,
                order_id=open_decision.get("order_id"),
                fill_count=filled_count,
                fill_price_cents=int(open_decision["price_cents"]),
                pnl_cents=pnl,
                broker_contacted=self.mode is SessionMode.LIVE,
                detail={"result_yes": result_yes},
            )
        )
        state.daily_pnl_cents += pnl
        state.settled_count_at_stage += 1
        count = max(1, filled_count)
        # Exponential moving realized edge per contract.
        state.realized_pnl_per_contract_cents = (
            0.8 * state.realized_pnl_per_contract_cents + 0.2 * (pnl / count)
        )

    def _apply_settlements(self, state: RiskState, report: CycleReport) -> None:
        for ticker, result_yes in self.reconciler.reconcile_settlements():
            report.settlements += 1
            report.weight_updates.update(self.learner.apply_settlement(ticker, result_yes))
        self._close_settled_positions(state)

    def _close_settled_positions(self, state: RiskState) -> None:
        # Close EVERY open position whose market has a settlement on record —
        # including positions from earlier sessions whose settlement landed
        # through another path (phantom sweep, retro). A settled market must
        # always release its slot. Duck-typed for minimal ledger stand-ins.
        settlement_result = getattr(self.ledger, "settlement_result", None)
        if not callable(settlement_result):
            return
        for open_decision in self._open_positions():
            result = settlement_result(str(open_decision["market_ticker"]))
            if result is None:
                continue
            self._close_position(state, open_decision, result)

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
            # Read the tape for the panel: recent momentum/volume/spread from
            # 1-minute candlesticks. Absent tape never blocks the debate.
            tape_line = None
            try:
                from autonomy.tape import describe_tape, tape_features

                series = market.ticker.split("-")[0]
                tape_line = describe_tape(tape_features(series, market.ticker)) or None
            except Exception:
                tape_line = None
            try:
                result = await run_debate(self.router, market, base_prob=forecast.probability_yes,
                                          context=tape_line)
            except Exception:
                result = None
            if result is None:
                continue
            debate_signal = result.to_signal(market.ticker)
            if not self.ledger.record_signal(debate_signal):
                report.signals_rejected += 1
                continue
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

        # Venue awareness: a maintenance window is a fact, not an error.
        # Unknown status (probe failed) proceeds — the check must never
        # become its own stall point.
        trading_active = True
        if self.exchange_status_fn is not None:
            try:
                venue = self.exchange_status_fn() or {}
            except Exception:
                venue = {}
            if venue.get("exchange_active") is False:
                self.risk_brain.save_state(state)
                report.status = "CYCLE_SKIPPED_EXCHANGE_MAINTENANCE"
                if venue.get("maintenance_windows"):
                    report.notes.append(f"maintenance_windows={venue['maintenance_windows']}")
                return report
            trading_active = venue.get("trading_active", True) is not False
            if not trading_active:
                # Reads still work: keep learning, place nothing.
                report.trading_halted = True
                report.notes.append("trading_halted_orders_skipped")

        # Refresh order fills before settlement accounting; a last-cycle fill
        # must be seen before deciding whether the order ever became a position.
        self.reconciler.reconcile_open_orders()
        self._apply_settlements(state, report)
        self._apply_phantom_settlements(report)
        # Phantom settlement discovery can also close a traded ticker.
        self._close_settled_positions(state)

        # Per-cycle source hooks (ESPN cache reset + incremental Elo retrain).
        self.registry.on_cycle_start()

        try:
            markets = self.scanner.scan()
        except Exception as exc:
            report.status = f"CYCLE_DEGRADED_SCAN_FAILED:{type(exc).__name__}"
            self.risk_brain.save_state(state)
            return report
        report.markets_scanned = len(markets)

        if self.mode is SessionMode.SHADOW:
            shadow_updates = self.reconciler.reconcile_shadow_orders(markets)
            report.shadow_fills = sum(1 for o in shadow_updates if o.kind is OutcomeKind.FILLED)
            report.shadow_expirations = sum(
                1 for o in shadow_updates if o.kind is OutcomeKind.EXPIRED
            )

        # Open exposure is a ledger fact, including active-order reservations
        # but only witnessed fill quantities after an order becomes terminal.
        open_positions = self._open_positions()
        state.open_markets = len({p["market_ticker"] for p in open_positions})
        state.open_exposure_cents = sum(
            int(p["price_cents"]) * int(p.get("reserved_count", p["count"]))
            for p in open_positions
        )
        state = self.risk_brain.maybe_promote(state)
        report.stage = int(state.stage)

        forecaster = EnsembleForecaster(self.ledger)
        scored: list[tuple[MarketView, Any, list[Any]]] = []
        for market in markets:
            signals = list(self.registry.signals_for(market))
            if not signals:
                continue
            accepted_mask = self.ledger.record_signals(signals)
            accepted_signals = [
                signal for signal, accepted in zip(signals, accepted_mask) if accepted
            ]
            report.signals_generated += len(accepted_signals)
            report.signals_rejected += len(signals) - len(accepted_signals)
            if not accepted_signals:
                continue
            forecast = forecaster.fuse(market, accepted_signals)
            if forecast is None:
                continue
            scored.append((market, forecast, accepted_signals))

        # Capital velocity: rank by edge per unit of settlement time, not raw
        # edge. A 3c edge that settles in an hour compounds faster than a 5c
        # edge parked for five days; sqrt damping keeps big slow edges alive.
        scored.sort(key=lambda t: edge_velocity(t[0], t[1]), reverse=True)

        # LLM panel adjudicates only the top-K edge markets, then re-fuse.
        if self.router is not None and scored:
            await self._adjudicate_top_k(forecaster, scored, report)
            scored.sort(key=lambda t: edge_velocity(t[0], t[1]), reverse=True)

        from autonomy.correlation import group_key

        allocator = Allocator(self.risk_brain)
        # In-cycle group accumulation so successive orders on one correlated
        # cluster see each other, not just prior-cycle open positions.
        cycle_group_cents: dict[str, int] = {}
        cycle_group_count: dict[str, int] = {}
        decision_slice = scored[:MAX_CANDIDATES_EVALUATED] if trading_active else []
        for market, forecast, _signals in decision_slice:
            if report.orders_placed >= MAX_ORDERS_PER_CYCLE:
                break
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
                if decision.abstain_reason == "risk brain: max open markets for stage":
                    report.notes.append("candidate_search_stopped_at_stage_position_cap")
                    break
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
