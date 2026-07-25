"""The predator loop: one cycle = scan -> signal -> forecast -> decide ->
execute -> reconcile -> learn. Honest status enums out of every cycle."""
from __future__ import annotations

import asyncio
import json
import math
import os
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Callable

from autonomy.allocator import Allocator
from autonomy.executor import Executor, kill_switch_active
from autonomy.forecaster import EnsembleForecaster
from autonomy.learner import Learner
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import DecisionAction, MarketView, OutcomeKind, SessionMode, TradeOutcome
from autonomy.reconciler import Reconciler, settlement_pnl_cents
from autonomy.risk_brain import RiskBrain, RiskState, RiskStatePersistenceError
from autonomy.scanner import MarketScanner
from autonomy.signals.base import SourceRegistry
from autonomy.target_policy import has_prediction_target_authority
from core.logger import logger

SHADOW_BANKROLL_CENTS = 10_000
MAX_CANDIDATES_EVALUATED = 100
MAX_ORDERS_PER_CYCLE = 10
# Above this many settlements in one cycle, batch the calibration fetch instead
# of one query per market (a full-scan batch only pays off past ~150 markets).
_PHANTOM_BATCH_THRESHOLD = 200


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, ""))
        return value if value >= 0 else default
    except (TypeError, ValueError):
        return default


# A debate is four independent calls plus four revisions.  The environment can
# narrow the slice, but a persistent user variable cannot widen it beyond this
# code-level ceiling without a reviewed code change.
DEBATE_LOGICAL_CALLS_PER_MARKET = 8
DEBATE_HARD_MAX_MARKETS_PER_CYCLE = 2
DEBATE_HARD_MAX_CONCURRENCY = 2
DEFAULT_DEBATE_MAX_LOGICAL_CALLS_PER_CYCLE = 8
DEFAULT_DEBATE_MAX_USD_PER_CYCLE = 0.10


def _fail_closed_budget_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0
    return max(0, value)


def _fail_closed_budget_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    return value if math.isfinite(value) and value >= 0 else 0.0


def _debate_top_k() -> int:
    return min(
        DEBATE_HARD_MAX_MARKETS_PER_CYCLE,
        _env_int("DUMMY_DEBATE_TOP_K", 1),
    )


# The local-CLI voices (claude/codex) bill personal subscriptions, so they join
# only the top-K_cli markets' panels -- a quota cap independent of DEBATE_TOP_K.
def _debate_cli_top_k() -> int:
    return _env_int("DUMMY_DEBATE_CLI_TOP_K", 1)


# The debate is the dominant per-cycle cost (10 markets x 2 rounds, formerly
# sequential). This many markets' panels run concurrently -- bounded so parallel
# HTTP panels don't blow the provider rate limits. Cuts the debate ~N-fold.
def _debate_concurrency() -> int:
    return min(
        DEBATE_HARD_MAX_CONCURRENCY,
        max(1, _env_int("DUMMY_DEBATE_CONCURRENCY", 1)),
    )


def _debate_max_logical_calls_per_cycle() -> int:
    return _fail_closed_budget_int(
        "DUMMY_DEBATE_MAX_LOGICAL_CALLS_PER_CYCLE",
        DEFAULT_DEBATE_MAX_LOGICAL_CALLS_PER_CYCLE,
    )


def _debate_max_usd_per_cycle() -> float:
    return _fail_closed_budget_float(
        "DUMMY_DEBATE_MAX_USD_PER_CYCLE",
        DEFAULT_DEBATE_MAX_USD_PER_CYCLE,
    )


def _conservative_debate_panel_cost_usd(router: Any) -> float:
    """Worst-case configured cost for one complete two-round exact panel.

    Production routers must expose exact provider pricing. Unknown/malformed
    prices fail closed with infinity. Test doubles without a config remain
    zero-cost so pure unit tests do not need billing fixtures.
    """
    config = getattr(router, "config", None)
    if config is None:
        return 0.0
    names = list(getattr(config, "hybrid_providers", []) or [])
    provider_configs = getattr(config, "provider_configs", {})
    if len(names) != 4 or len(set(names)) != 4:
        return math.inf
    prompt_tokens = math.ceil(max(0, int(config.max_prompt_length)) / 4)
    completion_tokens = 512
    total = 0.0
    for name in names:
        provider = provider_configs.get(name)
        if provider is None:
            return math.inf
        prompt_price = provider.prompt_cost_per_million
        completion_price = provider.completion_cost_per_million
        if (
            prompt_price is None
            or completion_price is None
            or not math.isfinite(float(prompt_price))
            or not math.isfinite(float(completion_price))
            or prompt_price < 0
            or completion_price < 0
        ):
            return math.inf
        one_round = (
            prompt_tokens * float(prompt_price)
            + completion_tokens * float(completion_price)
        ) / 1_000_000
        total += 2 * one_round
    return total


DEBATE_TOP_K = 1   # module default retained for back-compat/imports


def edge_velocity(market: MarketView, forecast: Any) -> float:
    """Edge per sqrt-hour to settlement: the compounding-rate ranking metric."""
    hours = 24.0
    try:
        close = datetime.fromisoformat(market.close_time.replace("Z", "+00:00"))
        hours = max(0.5, (close - datetime.now(timezone.utc)).total_seconds() / 3600.0)
    except Exception:
        # Unparseable close time silently ranked as 24h — leave the default
        # but log once-per-cycle-ish so a malformed feed is visible, not a
        # quiet mis-ranking (2026-07-24 audit).
        logger.warning(
            "edge_velocity close_time unparseable; defaulting to 24h",
            extra={"component": "brain", "ticker": market.ticker,
                   "close_time": str(market.close_time)},
        )
    return abs(forecast.edge_yes) / math.sqrt(hours)


def _reserved_exposure_cents(position: dict[str, Any]) -> int:
    """Worst-case capital still reserved for an open order or position."""
    explicit = position.get("reserved_notional_cents")
    if explicit is not None:
        try:
            return max(0, int(explicit))
        except (TypeError, ValueError):
            pass
    return max(0, int(position["price_cents"])) * max(
        0, int(position.get("reserved_count", position["count"]))
    )


def _market_has_prediction_authority(market: MarketView) -> bool:
    """Authorize a scanner row from its structured point-in-time context."""
    raw = market.raw or {}
    return has_prediction_target_authority(
        market.ticker,
        category=raw.get("category"),
        vertical=market.vertical,
        series_tags=raw.get("series_tags") or raw.get("tags"),
    )


def _authoritative_live_candidate_allowlist() -> Callable[[str], bool] | None:
    """Load the live-candidacy test from the protected caps config.

    ``None`` means the authority source is unavailable or invalid.  Callers
    treat ``None`` and an all-rejecting predicate alike as zero candidates; this
    helper never turns a caps/config failure into a broad live scan.

    Candidacy is decided by the firewall's own matcher, so the set the brain
    proposes and the set the firewall accepts cannot drift apart: exact
    ``allowed_markets`` plus whole-series ``allowed_series``.  Reading
    ``allowed_markets`` alone -- as this did before -- left a series grant
    unreachable.  Kalshi contracts rotate, so the shipped caps authorize a
    series and hold ``allowed_markets`` empty; against that config a LIVE cycle
    filtered out every market and an armed session silently placed nothing.
    """
    try:
        from core.caps_authority import evaluate_caps_authority
        from core.config_loader import load_caps
        from live_firewall.firewall import market_is_allowlisted

        authority = evaluate_caps_authority()
        if authority.config_integrity_valid is not True:
            return None
        caps = load_caps()
        # ``allowed_series`` postdates some caps payloads; absent means "no
        # series grant", exactly as the firewall's matcher reads it.
        grants = (
            caps.allowed_markets,
            getattr(caps, "allowed_series", None) or [],
        )
    except Exception:
        return None
    for raw in grants:
        if not isinstance(raw, list):
            return None
        values: list[str] = []
        for value in raw:
            if not isinstance(value, str) or not value or value != value.strip():
                return None
            values.append(value)
        if len(values) != len(set(values)):
            return None
    return lambda ticker: market_is_allowlisted(ticker, caps)


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
    # Wall-time (seconds) spent in each major cycle phase, so the live cycle
    # self-reports where its time goes -- the observability that turns "cycles
    # are slow" into "phase X is slow" without a profiler on the box.
    phase_seconds: dict[str, float] = field(default_factory=dict)
    # Phantom-grading coverage receipt for this cycle (see
    # autonomy.reconciler.Reconciler._forecast_coverage_receipt): what share of
    # the markets we priced this sweep was actually asked to grade, and whether
    # any series' settled listing overflowed its page cap. Lands in
    # runtime/autonomy/cycles.jsonl so "grades every priced market" is a
    # measured claim rather than an assertion.
    phantom_coverage: dict[str, Any] = field(default_factory=dict)

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
        performance_guard: Any | None = None,
        board_path: Any | None = None,
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
        self.performance_guard = performance_guard
        self.board_path = board_path
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
                exposure += _reserved_exposure_cents(open_decision)
        return exposure

    def _group_exposure(self, ticker: str) -> tuple[int, int]:
        """(exposure_cents, open_position_count) for the ticker's correlation group."""
        from autonomy.correlation import group_key

        target = group_key(ticker)
        exposure = 0
        count = 0
        for open_decision in self._open_positions():
            if group_key(open_decision["market_ticker"]) == target:
                exposure += _reserved_exposure_cents(open_decision)
                count += 1
        return exposure, count

    def _allocation_scope(self, market, forecast) -> str:
        """The grading scope this candidate's allocation weight is looked up under.

        Falls back to the ticker so an unmappable market still allocates (at
        the weight floor) rather than crashing the cycle.
        """
        try:
            from autonomy.taxonomy import grading_scope

            return grading_scope(
                "fused", market.ticker, getattr(forecast, "features", None)
            )
        except Exception:
            try:
                return str(market.ticker)
            except Exception:
                return "unknown"

    def _scope_advantages(self) -> dict[str, float]:
        """Per-scope contested-Brier advantage (lower 95% bound).

        Reads the latest dashboard snapshot rather than the ledger: this runs
        every cycle and must never take a ledger lock.  An absent or unreadable
        snapshot yields an empty map, which resolves every scope to the weight
        floor -- the honest "no evidence yet" answer.
        """
        from pathlib import Path

        try:
            snapshot = json.loads(
                Path("runtime/autonomy/latest_dashboard_snapshot.json")
                .read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            return {}
        if not isinstance(snapshot, dict):
            return {}
        surface = snapshot.get("trust_surface_by_specialist")
        if not isinstance(surface, dict):
            return {}
        out: dict[str, float] = {}
        for bucket in surface.values():
            if not isinstance(bucket, dict):
                continue
            scopes = bucket.get("scopes")
            if not isinstance(scopes, dict):
                continue
            for scope, row in scopes.items():
                if not isinstance(row, dict):
                    continue
                value = row.get("contested_brier_advantage_lower95")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    out[str(scope)] = float(value)
        return out

    def _sync_live_exposure(self, outcomes: list[TradeOutcome]) -> None:
        """Project only broker-witnessed fills into central live exposure."""
        if self.mode is not SessionMode.LIVE or not outcomes:
            return
        from live_firewall.exposure_tracker import get_persistent_exposure_tracker

        tracker = get_persistent_exposure_tracker()
        terminal_states = {
            OutcomeKind.FILLED: "filled",
            OutcomeKind.CANCELED: "canceled",
            OutcomeKind.EXPIRED: "expired",
        }
        for outcome in outcomes:
            order_id = str(outcome.order_id or "").strip()
            if not order_id:
                continue
            terminal_state = terminal_states.get(outcome.kind)
            if outcome.kind is OutcomeKind.PARTIALLY_FILLED or terminal_state:
                tracker.record_cumulative_fill(
                    order_id,
                    int(outcome.fill_count),
                    (
                        int(outcome.fill_price_cents)
                        if outcome.fill_price_cents is not None else None
                    ),
                    terminal_state=terminal_state,
                )

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
        witnessed_price = open_decision.get("fill_price_cents")
        fill_price_cents = int(
            witnessed_price
            if witnessed_price is not None
            else open_decision["price_cents"]
        )
        liquidity_role = str(open_decision.get("liquidity_role") or "maker").lower()
        if liquidity_role not in {"maker", "taker", "mixed"}:
            # Unknown execution provenance must never receive the cheaper fee.
            liquidity_role = "taker"
        execution_fee = open_decision.get("execution_fee_cents")
        fill_cost = open_decision.get("fill_cost_cents")
        pnl = settlement_pnl_cents(
            str(open_decision["side"]).lower(), fill_price_cents,
            filled_count, result_yes,
            market_ticker=str(open_decision["market_ticker"]),
            liquidity_role=liquidity_role,
            fee_cents=(int(execution_fee) if execution_fee is not None else None),
            fill_cost_cents=(int(fill_cost) if fill_cost is not None else None),
        )
        won = pnl > 0
        self.ledger.record_outcome(
            TradeOutcome(
                decision_id=str(open_decision["decision_id"]),
                market_ticker=str(open_decision["market_ticker"]),
                kind=OutcomeKind.SETTLED_WIN if won else OutcomeKind.SETTLED_LOSS,
                order_id=open_decision.get("order_id"),
                fill_count=filled_count,
                fill_price_cents=fill_price_cents,
                pnl_cents=pnl,
                broker_contacted=self.mode is SessionMode.LIVE,
                detail={
                    "result_yes": result_yes,
                    # A zero-PnL settlement is a push/scratch, not a loss; the
                    # terminal kind stays binary (10+ consumers key on
                    # WIN/LOSS as "settled"), so win-rate consumers must
                    # exclude push_scratch rows rather than trust the kind.
                    "push_scratch": pnl == 0,
                    "liquidity_role": liquidity_role,
                    "fill_price_source": (
                        "witnessed_outcome"
                        if witnessed_price is not None
                        else "submitted_limit_fallback"
                    ),
                    "execution_fee_cents": (
                        int(execution_fee) if execution_fee is not None else None
                    ),
                    "fill_cost_cents": (
                        int(fill_cost) if fill_cost is not None else None
                    ),
                },
            )
        )
        if self.mode is SessionMode.LIVE:
            from core import state as state_module
            from live_firewall.exposure_tracker import get_persistent_exposure_tracker

            decision_id = str(open_decision["decision_id"])
            state_module.STATE.record_realized_pnl(pnl, settlement_id=decision_id)
            tracker = get_persistent_exposure_tracker()
            order_id = open_decision.get("order_id")
            if order_id:
                tracker.remove_open_order(str(order_id))
            tracker.remove_position(
                str(open_decision["market_ticker"]),
                str(open_decision["side"]),
            )
        state.daily_pnl_cents += pnl
        state.settled_count_at_stage += 1
        count = max(1, filled_count)
        # Exponential moving realized edge per contract.
        state.realized_pnl_per_contract_cents = (
            0.8 * state.realized_pnl_per_contract_cents + 0.2 * (pnl / count)
        )

    def _apply_settlements(self, state: RiskState, report: CycleReport) -> None:
        settlements = list(self.reconciler.reconcile_settlements())
        decay_dormant = getattr(self.learner, "decay_dormant_weights", None)
        if callable(decay_dormant):
            decay_dormant()
        from autonomy.correlation import group_key
        cluster_counts: dict[str, int] = {}
        for ticker, _result_yes in settlements:
            key = group_key(ticker)
            cluster_counts[key] = cluster_counts.get(key, 0) + 1
        for ticker, result_yes in settlements:
            report.settlements += 1
            cluster_weight = 1.0 / cluster_counts[group_key(ticker)]
            report.weight_updates.update(
                self.learner.apply_settlement(ticker, result_yes, cluster_weight=cluster_weight)
            )
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

    def _persist_risk_state(self, state: RiskState, report: CycleReport) -> bool:
        """Persist risk state or turn the cycle into a fail-closed halt."""
        try:
            self.risk_brain.save_state(state)
        except RiskStatePersistenceError as exc:
            report.status = "HALTED_RISK_STATE_PERSISTENCE"
            report.notes.append(str(exc))
            return False
        return True

    def _apply_phantom_settlements(self, report: CycleReport) -> None:
        """Grade every forecasted market that settled — trades or not.

        This is the calibration firehose: trust weights learn from the whole
        forecast surface, not just the stage-capped handful of positions.
        Never touches risk state (there is no position to P&L).

        The sweep's coverage receipt (how much of the priced surface this pass
        was actually asked to grade, plus any pagination overflow) is copied
        onto the cycle report -- including when the sweep raises, so a failed
        sweep reads as zero coverage instead of silence.
        """
        try:
            phantom = self.reconciler.reconcile_forecast_settlements(list(self.scanner.watchlist))
        except Exception as exc:
            report.phantom_coverage = {
                "status": "SWEEP_FAILED",
                "error": type(exc).__name__,
                "attempt_coverage_ratio": None,
                "graded_coverage_ratio": None,
                "graded_this_pass": 0,
                "pagination_truncated": False,
                "complete": False,
            }
            report.notes.append(f"phantom_sweep_failed:{type(exc).__name__}")
            return
        coverage = getattr(self.reconciler, "last_forecast_coverage", None)
        if isinstance(coverage, dict):
            report.phantom_coverage = dict(coverage)
            if coverage.get("pagination_truncated"):
                report.notes.append(
                    "phantom_coverage_pagination_truncated:"
                    + ",".join(coverage.get("series_truncated") or [])
                )
        # Backlog resilience: after an outage many markets settle at once, and
        # grading them one calibration query at a time (apply_settlement ->
        # calibration_signals_for_market) is another N+1. Above a threshold,
        # share ONE batched fetch (the same validated per-source selection).
        prefetch: dict[str, list] = {}
        if len(phantom) >= _PHANTOM_BATCH_THRESHOLD:
            batch = getattr(self.ledger, "calibration_signals_for_settled", None)
            if callable(batch):
                try:
                    prefetch = batch([t for t, _ in phantom])
                except Exception:
                    prefetch = {}
        from autonomy.correlation import group_key
        cluster_counts: dict[str, int] = {}
        for ticker, _result_yes in phantom:
            key = group_key(ticker)
            cluster_counts[key] = cluster_counts.get(key, 0) + 1
        for ticker, result_yes in phantom:
            report.phantom_settlements += 1
            report.weight_updates.update(
                self.learner.apply_settlement(
                    ticker,
                    result_yes,
                    signals=prefetch.get(ticker),
                    cluster_weight=1.0 / cluster_counts[group_key(ticker)],
                )
            )

    # ------------------------------------------------------------------

    async def _adjudicate_top_k(self, forecaster, scored: list, report: CycleReport) -> None:
        """Run the LLM debate on the top-K edge markets and re-fuse in place.

        The local-CLI voices (claude/codex) join only the top-K_cli markets'
        panels, so plugging Claude in costs a few personal-subscription calls a
        cycle, not one per market."""
        from autonomy.debate import run_debate

        cli_top_k = _debate_cli_top_k()
        requested_k = min(_debate_top_k(), len(scored))
        call_budget = _debate_max_logical_calls_per_cycle()
        max_by_calls = call_budget // DEBATE_LOGICAL_CALLS_PER_MARKET
        panel_cost = _conservative_debate_panel_cost_usd(self.router)
        dollar_budget = _debate_max_usd_per_cycle()
        max_by_dollars = (
            requested_k
            if panel_cost == 0.0
            else int(dollar_budget // panel_cost)
            if math.isfinite(panel_cost) and panel_cost > 0
            else 0
        )
        k = min(requested_k, max_by_calls, max_by_dollars)
        if k <= 0:
            report.notes.append(
                "debate:skipped:paid_call_budget_closed"
            )
            return
        report.notes.append(
            "debate:budget:"
            f"markets={k}:logical_calls={k * DEBATE_LOGICAL_CALLS_PER_MARKET}:"
            f"worst_case_usd={k * panel_cost:.6f}"
        )
        sem = asyncio.Semaphore(_debate_concurrency())

        async def _debate_one(idx: int):
            market, forecast, _signals = scored[idx]
            allow_cli = idx < cli_top_k
            # Read the tape for the panel: recent momentum/volume/spread from
            # 1-minute candlesticks. Absent tape never blocks the debate.
            tape_line = None
            try:
                from autonomy.tape import describe_tape, tape_features

                series = market.ticker.split("-")[0]
                tape_line = describe_tape(tape_features(series, market.ticker)) or None
            except Exception:
                tape_line = None
            async with sem:  # bound concurrent panels so we don't blow rate limits
                try:
                    return await run_debate(
                        self.router, market, base_prob=forecast.probability_yes,
                        context=tape_line, allow_cli=allow_cli)
                except Exception:
                    return None

        # Run the panels concurrently (I/O-bound LLM calls); the CLI cap keeps
        # local-subscription voices on the top-K_cli markets only.
        results = await asyncio.gather(*[_debate_one(idx) for idx in range(k)])
        # Record + re-fuse sequentially: these mutate shared ledger/scored state.
        for idx, result in enumerate(results):
            if result is None:
                continue
            market, forecast, signals = scored[idx]
            scope_features: dict[str, Any] = {
                "vertical": market.vertical.value,
                "market_status": market.status,
                "live": bool(
                    (market.raw or {}).get("live")
                    or (market.raw or {}).get("is_live")
                    or str(market.status).lower() in {"live", "in_play", "in-play"}
                ),
            }
            # Reuse point-in-time specialist stamps when available. This keeps
            # LLM evidence isolated by the same market type/horizon as its
            # quantitative base instead of pooling every bet into one bucket.
            for original in signals:
                for key in ("market_type", "hours_to_close"):
                    value = (original.features or {}).get(key)
                    if key not in scope_features and value is not None:
                        scope_features[key] = value
            if "market_type" not in scope_features:
                try:
                    from autonomy.sports_markets import classify

                    contract = classify(market)
                    if contract is not None:
                        scope_features["market_type"] = contract.market_type
                except Exception:
                    pass
            if "hours_to_close" not in scope_features:
                try:
                    close = datetime.fromisoformat(
                        str(market.close_time).replace("Z", "+00:00")
                    )
                    if close.tzinfo is None:
                        close = close.replace(tzinfo=timezone)
                    scope_features["hours_to_close"] = max(
                        0.0,
                        (close - datetime.now(timezone.utc)).total_seconds() / 3600.0,
                    )
                except (TypeError, ValueError):
                    pass
            # Persist raw per-model opinions for settlement grading, but never
            # feed them into fusion. The versioned aggregate is also a
            # challenger: the promotion registry is its only path to authority.
            observations = result.observation_signals(
                market.ticker, scope_features=scope_features,
            )
            if observations:
                accepted = self.ledger.record_signals(observations)
                report.signals_generated += sum(1 for ok in accepted if ok)
                report.signals_rejected += sum(1 for ok in accepted if not ok)
            debate_signal = result.to_signal(
                market.ticker, scope_features=scope_features,
            )
            if not self.ledger.record_signal(debate_signal):
                report.signals_rejected += 1
                continue
            report.signals_generated += 1
            refused = forecaster.fuse(market, list(signals) + [debate_signal])
            if refused is not None:
                scored[idx] = (market, refused, list(signals) + [debate_signal])
                report.notes.append(
                    f"debate:observed:{debate_signal.source}:"
                    f"{market.ticker}:{result.probability_yes:.2f}"
                )

    async def run_cycle(self) -> CycleReport:
        cycle_t0 = time.perf_counter()
        bankroll = self._bankroll_cents()
        state = self.risk_brain.load_state(bankroll)
        report = CycleReport(status="CYCLE_OK", mode=self.mode.value, stage=int(state.stage),
                             bankroll_cents=bankroll)

        load_error = getattr(self.risk_brain, "persistence_error", None)
        if load_error:
            report.status = "HALTED_RISK_STATE_UNAVAILABLE"
            report.notes.append(f"risk_state_load_error={load_error}")
            return report

        if kill_switch_active(self.executor.kill_path):
            report.status = "HALTED_KILL_SWITCH"
            return report

        # Operator MAIN switch: off idles the whole cycle (no scan/forecast/
        # execute), read fresh so a toggle takes effect on the next fire.
        from autonomy.switches import Switches

        switches = Switches.load()
        if not switches.main_enabled():
            report.status = "IDLE_MAIN_SWITCH_OFF"
            return report

        state = self.risk_brain.apply_drawdown_policy(state)
        if state.hard_stopped:
            if not self._persist_risk_state(state, report):
                return report
            report.status = f"HALTED_SELF_STOP: {state.stop_reason}"
            return report

        # Preflight the durable risk sink before reconciliation, forecasting,
        # or any executor call. A process that cannot preserve its caps,
        # drawdown, and stage state has no authority to place another order.
        if not self._persist_risk_state(state, report):
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
                if not self._persist_risk_state(state, report):
                    return report
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
        live_order_updates = self.reconciler.reconcile_open_orders()
        self._sync_live_exposure(live_order_updates)
        # Snapshot trust before settlements so a pathological recalibration
        # (e.g. every crypto source pinned at the ceiling) can be reverted.
        try:
            pre_settlement_weights = self.ledger.all_weights()
        except Exception:
            pre_settlement_weights = {}
        self._apply_settlements(state, report)
        self._apply_phantom_settlements(report)
        guard_weights = getattr(self.learner, "guard_cycle_weights", None)
        if callable(guard_weights) and report.weight_updates:
            guard_weights(report, pre_settlement_weights)
        # Phantom settlement discovery can also close a traded ticker.
        self._close_settled_positions(state)

        # Per-cycle source hooks (ESPN cache reset + incremental Elo retrain).
        _t = time.perf_counter()
        self.registry.on_cycle_start()
        report.phase_seconds["on_cycle_start"] = round(time.perf_counter() - _t, 2)
        if self.performance_guard is not None:
            reload_guard = getattr(self.performance_guard, "reload", None)
            if callable(reload_guard):
                reload_guard()

        _t = time.perf_counter()
        try:
            markets = self.scanner.scan()
        except Exception as exc:
            report.status = f"CYCLE_DEGRADED_SCAN_FAILED:{type(exc).__name__}"
            if not self._persist_risk_state(state, report):
                return report
            return report
        report.phase_seconds["scan"] = round(time.perf_counter() - _t, 2)
        # Vertical / per-league switches: crypto off, sports off, or a league
        # off drops those markets from the cycle (the rest keeps trading).
        if self.mode is SessionMode.LIVE:
            live_allowlist = _authoritative_live_candidate_allowlist()
            before_live_filter = len(markets)
            markets = [
                market
                for market in markets
                if live_allowlist is not None and live_allowlist(market.ticker)
            ]
            report.notes.append(
                "live_allowlist_candidates="
                f"{len(markets)};filtered={before_live_filter - len(markets)};"
                f"authority={'valid' if live_allowlist is not None else 'invalid'}"
            )
        before_switches = len(markets)
        markets = [m for m in markets if switches.market_allowed(m)]
        if len(markets) != before_switches:
            report.notes.append(
                f"switches_filtered={before_switches - len(markets)}"
            )
        switched = len(markets)
        markets = [m for m in markets if _market_has_prediction_authority(m)]
        if len(markets) != switched:
            report.notes.append(
                f"target_authority_filtered={switched - len(markets)}"
            )
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
            _reserved_exposure_cents(p)
            for p in open_positions
        )
        state = self.risk_brain.maybe_promote(state)
        report.stage = int(state.stage)

        forecaster = EnsembleForecaster(self.ledger)
        scored: list[tuple[MarketView, Any, list[Any]]] = []
        _t = time.perf_counter()
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
        report.phase_seconds["signal_gen"] = round(time.perf_counter() - _t, 2)

        # Capital velocity: rank by edge per unit of settlement time, not raw
        # edge. A 3c edge that settles in an hour compounds faster than a 5c
        # edge parked for five days; sqrt damping keeps big slow edges alive.
        scored.sort(key=lambda t: edge_velocity(t[0], t[1]), reverse=True)

        # LLM panel adjudicates only the top-K edge markets, then re-fuse.
        _t = time.perf_counter()
        if self.router is not None and scored:
            await self._adjudicate_top_k(forecaster, scored, report)
            scored.sort(key=lambda t: edge_velocity(t[0], t[1]), reverse=True)
            # Real spend/health telemetry per voice (observational): the
            # tracker aggregates provider-reported cost and counts fallback
            # failures without ever changing the roster contract.
            try:
                tracker = getattr(self.router, "cost_tracker", None)
                if tracker is not None and tracker.calls:
                    report.notes.append(
                        "llm_router=" + json.dumps(tracker.summary(), sort_keys=True)
                    )
            except Exception:
                pass
        report.phase_seconds["debate"] = round(time.perf_counter() - _t, 2)

        # One immutable v2 classification is shared by signals, board rows,
        # and decisions.  This prevents the UI and performance ledger from
        # assigning different tiers to the same point-in-time forecast.
        from autonomy.tier_policy import assign_cycle_tiers

        cycle_tiers = assign_cycle_tiers([(m, f) for m, f, _s in scored])

        # Wave-14 (picks-first directive): persist the FINAL post-debate fused
        # probability for every scored market as its own ledger row, so pick
        # accuracy and calibration are measured on everything the machine
        # opines on -- not just the handful it trades. Never feeds back into
        # fusion (fusion consumes registry signals, not ledger rows) and never
        # blocks the cycle.
        from autonomy.picks import (
            build_calibrated_fused_signal,
            build_fused_signal,
            load_fused_maps,
        )

        # Wave-17: nightly reliability maps for the fused output (empty until
        # enough Wave-14 rows settle -- the shadow calibration self-activates
        # as evidence accrues, no switch to flip).
        try:
            fused_maps = load_fused_maps()
        except Exception:
            fused_maps = {}
        _t = time.perf_counter()
        for market, forecast, _signals in scored:
            try:
                # Ledger mode is an evidence-provenance axis accepting only
                # live/retro -- the brain records everything (incl. its own
                # per-source signals above) under the default, session mode
                # notwithstanding. Passing mode=self.mode.value ("shadow")
                # silently rejected 24k fused rows as invalid_mode.
                tier_assessment = cycle_tiers.get(market.ticker)
                self.ledger.record_signal(
                    build_fused_signal(market.ticker, forecast, tier_assessment)
                )
                calibrated = build_calibrated_fused_signal(
                    market.ticker, forecast, fused_maps, tier_assessment)
                if calibrated is not None:
                    self.ledger.record_signal(calibrated)
            except Exception:
                pass
        report.phase_seconds["picks_record"] = round(time.perf_counter() - _t, 2)
        # Wave-15: publish the bet board straight from this cycle's in-memory
        # scores (titles included, ledger untouched -- the dashboard reads the
        # artifact, never contends with this process's write lock).
        try:
            from autonomy.bet_board import write_board_artifact

            write_board_artifact(
                [(m, f) for m, f, _s in scored],
                path=self.board_path,
                tier_assignments=cycle_tiers,
            )
        except Exception:
            pass

        # Wave-75 coordinator reports (fail-soft, report-only): the defensive
        # top-threat decomposition of the open book, and the offensive matchup
        # lens over the fresh board's letter-tier rows.
        try:
            from autonomy.top_threat import write_top_threat

            write_top_threat(self.ledger)
        except Exception:
            pass
        try:
            from autonomy.matchup_lens import write_matchup_report

            write_matchup_report()
        except Exception:
            pass

        # Exit logic remains an observational challenger until it has enough
        # forward evidence and complete live sell/reconciliation proof. It may
        # recommend EXIT, but this cycle never turns that advice into an order.
        try:
            from autonomy.exit_advisor import write_exit_advisory_artifact

            exit_advice = write_exit_advisory_artifact(
                open_positions, [(m, f) for m, f, _s in scored],
            )
            exit_signals = [row.to_signal() for row in exit_advice]
            if exit_signals:
                accepted = self.ledger.record_signals(exit_signals)
                report.signals_generated += sum(1 for ok in accepted if ok)
                report.signals_rejected += sum(1 for ok in accepted if not ok)
            exit_candidates = sum(1 for row in exit_advice if row.action == "EXIT")
            if exit_candidates:
                report.notes.append(f"shadow_exit_candidates={exit_candidates}")
        except Exception:
            pass

        from autonomy.correlation import group_key

        allocator = Allocator(
            self.risk_brain,
            performance_guard=self.performance_guard,
            execution_policy=getattr(self.executor, "execution_policy", None),
        )
        # In-cycle group accumulation so successive orders on one correlated
        # cluster see each other, not just prior-cycle open positions.
        cycle_group_cents: dict[str, int] = {}
        cycle_group_count: dict[str, int] = {}
        decision_slice = scored[:MAX_CANDIDATES_EVALUATED] if trading_active else []

        # Cross-candidate allocation: divide ONE pot across the candidates that
        # can actually be held this cycle, weighted by each scope's
        # demonstrated contested-Brier advantage.  Without this the loop below
        # is greedy -- whoever ranks first takes as much as its own caps allow
        # and everything after it competes for the remainder.
        from autonomy.allocation_config import AllocationConfig
        from autonomy.allocation_weights import weights_for_scopes
        from autonomy.candidate_allocation import Ask, allocate
        from autonomy.risk_brain import STAGE_LIMITS

        alloc_config = AllocationConfig.load()
        stage_limits = STAGE_LIMITS[state.stage]
        # Only as many candidates as the stage can still hold open.  Dividing
        # the pot across all 100 evaluated markets when the stage permits 5
        # positions would push every grant below the price of one contract and
        # silently stop trading altogether.
        alloc_slots = max(
            0, int(stage_limits["max_open_markets"]) - int(state.open_markets)
        )
        alloc_pool = decision_slice[:alloc_slots]
        pot_cents = int(
            max(
                0,
                int(state.bankroll_cents * float(stage_limits["total_frac"]))
                - int(state.open_exposure_cents),
            )
            * alloc_config.throttle
        )
        alloc_asks = [
            Ask(
                candidate_id=market.ticker,
                scope=self._allocation_scope(market, forecast),
                ask_cents=int(stage_limits["order_abs_cents"]),
                price_cents=1,
            )
            for market, forecast, _signals in alloc_pool
        ]
        alloc_weights = weights_for_scopes(
            {a.scope for a in alloc_asks},
            self._scope_advantages(),
            config=alloc_config,
        )
        alloc_grants = {
            g.candidate_id: g.granted_cents
            for g in allocate(
                alloc_asks, pot_cents, alloc_weights,
                alloc_config.policy, top_k=alloc_config.top_k,
            )
        }
        report.notes.append(
            "allocation=" + json.dumps(
                {
                    "policy": alloc_config.policy,
                    "throttle": alloc_config.throttle,
                    "pot_cents": pot_cents,
                    "slots": alloc_slots,
                    "candidates": len(alloc_asks),
                    "granted_cents": sum(alloc_grants.values()),
                },
                sort_keys=True,
            )
        )

        _t = time.perf_counter()
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
                # Default 0, never None: a candidate outside the allocation
                # pool must be capped OUT, not left uncapped.
                allocation_cap_cents=alloc_grants.get(market.ticker, 0),
            )
            tier_assessment = cycle_tiers.get(market.ticker)
            if tier_assessment is not None:
                from autonomy.tier_policy import tier_snapshot_is_valid

                frozen_tier = tier_assessment.feature_fields()
                side_matches = decision.side == tier_assessment.side
                if not tier_snapshot_is_valid(
                    frozen_tier, ticker=market.ticker
                ):
                    decision = replace(
                        decision,
                        tier_label=None,
                        tier_policy_version=None,
                        tier_score=None,
                        tier_reason=(
                            "unattributed_invalid_tier_snapshot:"
                            f"{tier_assessment.reason}"
                        ),
                        tier_snapshot={},
                    )
                elif decision.action is not DecisionAction.ABSTAIN and not side_matches:
                    # A value-side label can never follow an actionable order
                    # on the opposite side.  Leave it unattributed rather than
                    # laundering an allocator disagreement into tier results.
                    decision = replace(
                        decision,
                        tier_label=None,
                        tier_policy_version=None,
                        tier_score=None,
                        tier_reason="unattributed_decision_side_mismatch",
                        tier_snapshot={},
                    )
                else:
                    decision = replace(
                        decision,
                        tier_label=tier_assessment.tier,
                        tier_policy_version=tier_assessment.policy_version,
                        # The immutable tier snapshot stores score at six
                        # decimals. Persist that same canonical precision so
                        # harmless binary-float tails cannot de-attribute a
                        # genuine decision during forward performance grading.
                        # A scoreless assessment stays None (matches the
                        # snapshot's null) instead of raising mid-cycle.
                        tier_score=(
                            round(float(tier_assessment.score), 6)
                            if tier_assessment.score is not None
                            else None
                        ),
                        tier_reason=tier_assessment.reason,
                        tier_snapshot=frozen_tier,
                    )
            self.ledger.record_decision(decision)
            report.decisions_made += 1
            if decision.action is DecisionAction.ABSTAIN:
                report.abstained += 1
                if decision.abstain_reason == "risk brain: max open markets for stage":
                    report.notes.append("candidate_search_stopped_at_stage_position_cap")
                    break
                continue
            # Bind the actionable decision to a just-written risk snapshot.
            # The central firewall verifies its digest again immediately
            # before submit; a failed write halts without touching the broker.
            if self.mode is SessionMode.LIVE and not self._persist_risk_state(state, report):
                return report
            execute_kwargs: dict[str, Any] = {
                "snapshot_ts": getattr(market, "fetched_at", None),
                # The exact MarketView that produced the forecast is required
                # in SHADOW as well as LIVE.  Executor independently verifies
                # identity and structured target authority before either book.
                "market": market,
            }
            outcome = await self.executor.execute(decision, **execute_kwargs)
            self.ledger.record_outcome(outcome)
            if outcome.kind in (OutcomeKind.ACCEPTED, OutcomeKind.SHADOW) and outcome.order_id:
                report.orders_placed += 1
                submitted_notional = int(
                    outcome.detail.get("submitted_notional_cents")
                    or decision.notional_cents
                )
                state.open_exposure_cents += submitted_notional
                state.open_markets += 1
                cycle_group_cents[gkey] = cycle_group_cents.get(gkey, 0) + submitted_notional
                cycle_group_count[gkey] = cycle_group_count.get(gkey, 0) + 1

        # Isolated challenger forward-evidence lane (paper-only, fail-closed):
        # books one tiny sources_used={candidate:1.0} probe per registered
        # candidate so the auto-promotion forward gate is reachable. Never
        # touches risk state, order counts, or the executor; runs in SHADOW
        # and LIVE cycles alike (execution-mode gate lives inside the module).
        try:
            from autonomy.challenger_lane import emit_isolated_challenger_decisions

            emit_isolated_challenger_decisions(
                self.ledger, scored, mode=self.mode.value, notes=report.notes,
                trading_active=trading_active,
            )
        except Exception as exc:
            report.notes.append(f"challenger_lane_error:lane:{type(exc).__name__}")

        report.phase_seconds["decide"] = round(time.perf_counter() - _t, 2)
        state.equity_peak_cents = max(state.equity_peak_cents, bankroll)
        if not self._persist_risk_state(state, report):
            return report
        self.ledger.record_bankroll(bankroll, state.open_exposure_cents, int(state.stage))
        report.phase_seconds["total"] = round(time.perf_counter() - cycle_t0, 2)
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
