"""Executor: routes decisions to the shadow book or the hardened live adapter.

Live mode requires a valid autonomy session authority (exact typed ack,
unexpired) and a clear kill file. Every live order flows through
KalshiLiveBrokerFirewallAdapter — LIMIT only, per-order validation, structured
rejections — with the per-order notional ceiling supplied by the risk brain.
Truthful outcomes: broker contact is claimed only on transport witness.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from autonomy.execution_policy import ExecutionPolicy
from autonomy.ontology import Decision, DecisionAction, OutcomeKind, SessionMode, TradeOutcome
from autonomy.staleness import StalenessPolicy, evaluate_snapshot_freshness

SESSION_PATH = Path("runtime/autonomy/session.json")
KILL_PATH = Path("runtime/autonomy/KILL")

AUTONOMY_ACK = (
    "I authorize an autonomous Dummy trading session with self-managed risk "
    "under the LiveBrokerFirewall, LIMIT orders only, until I stop it"
)
SESSION_ACCOUNTING_VERSION = 2
MAX_QUEUE_AHEAD_CONTRACTS = 50.0


def order_ttl_seconds(market_ticker: str) -> int:
    """Resting-order lifetime: fast crypto books get a one-minute lease.

    Hourly crypto fair values can reverse within one scheduler interval. The
    observed fill record remains entirely losing even at five minutes; the
    historical one-minute censor retains research fills while cutting settled
    loss exposure materially. Quotes therefore expire before stale maker edge
    can linger into the next ten-minute forecast cycle.
    """
    from autonomy.ontology import Vertical
    from autonomy.scanner import classify_vertical

    return 60 if classify_vertical(market_ticker) is Vertical.CRYPTO else 45 * 60


def load_session(path: Path | None = None) -> dict[str, Any]:
    path = path or SESSION_PATH
    if not path.exists():
        return {"mode": SessionMode.SHADOW.value, "valid": False, "reason": "no session file"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"mode": SessionMode.SHADOW.value, "valid": False, "reason": "unreadable session file"}
    if data.get("mode") == SessionMode.LIVE.value:
        if int(data.get("accounting_version", 1)) < SESSION_ACCOUNTING_VERSION:
            return {
                "mode": SessionMode.SHADOW.value,
                "valid": False,
                "reason": "live session predates fill-truth accounting upgrade; restart required",
            }
        if data.get("ack") != AUTONOMY_ACK:
            return {"mode": SessionMode.SHADOW.value, "valid": False, "reason": "ack mismatch"}
        expiry = str(data.get("expires_at", ""))
        try:
            if datetime.fromisoformat(expiry.replace("Z", "+00:00")) < datetime.now(timezone.utc):
                return {"mode": SessionMode.SHADOW.value, "valid": False, "reason": "session expired"}
        except Exception:
            return {"mode": SessionMode.SHADOW.value, "valid": False, "reason": "bad expiry"}
    data["valid"] = True
    return data


def kill_switch_active(path: Path | None = None) -> bool:
    return (path or KILL_PATH).exists()


class Executor:
    def __init__(
        self,
        mode: SessionMode,
        session_path: Path | None = None,
        kill_path: Path | None = None,
        adapter_factory: Any | None = None,
        quote_fn: Any | None = None,
        shadow_book_fn: Any | None = None,
        staleness_policy: StalenessPolicy | None = None,
        exchange_status_fn: Callable[[], dict[str, Any]] | None = None,
        now_fn: Callable[[], float] | None = None,
        execution_policy: ExecutionPolicy | None = None,
    ) -> None:
        self.mode = mode
        # Typed execution policy (Wave-2 A2/F2; Wave-5 taker path). The default
        # is the incumbent maker-only control (C0): when the policy is the
        # control, execute() takes the exact pre-existing code path with zero
        # new branches, so C0 reproduces current behavior byte for byte. A
        # non-control adverse-guard maker (C3) consults the divergence guard;
        # a taker policy (C1, tournament-backed 2026-07-17) reprices orders to
        # cross the freshest book in BOTH shadow and live paths via
        # _apply_taker_policy — fail-closed, EV re-checked net of taker fee.
        self.execution_policy = execution_policy or ExecutionPolicy.maker_only_control()
        self.session_path = session_path or SESSION_PATH
        self.kill_path = kill_path or KILL_PATH
        self.adapter_factory = adapter_factory
        # Optional pre-submit fresh-book read; when supplied, a maker quote that
        # has crossed since the scan is skipped instead of filled as a taker.
        self.quote_fn = quote_fn
        self.shadow_book_fn = shadow_book_fn
        # Stale-data submit gate. Active only when a policy is supplied; when
        # active it is fail-closed (missing snapshot timestamp => refuse). Left
        # None by most callers/tests so existing behavior is unchanged.
        self.staleness_policy = staleness_policy
        # Optional venue re-check at the moment of a LIVE submit (halt state can
        # change between cycle start and submit). Fail-open on fetch error.
        self.exchange_status_fn = exchange_status_fn
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc).timestamp())
        # Counter so a refusal is never a silent skip: surfaced on the executor
        # for the daemon/dashboard, and each refusal is also recorded as a
        # BLOCKED_LOCAL outcome in the ledger with its reason.
        self.stale_block_count = 0

    def _idempotency_key(self, decision: Decision) -> str:
        return hashlib.sha256(f"autonomy|{decision.decision_id}".encode("utf-8")).hexdigest()[:32]

    async def execute(
        self,
        decision: Decision,
        *,
        snapshot_ts: Any | None = None,
        is_live_market: bool = False,
        market_prior_yes: float | None = None,
    ) -> TradeOutcome:
        if decision.action is DecisionAction.ABSTAIN or decision.count < 1:
            return TradeOutcome(
                decision_id=decision.decision_id,
                market_ticker=decision.market_ticker,
                kind=OutcomeKind.SHADOW,
                order_id=None,
                fill_count=0,
                fill_price_cents=None,
                pnl_cents=None,
                broker_contacted=False,
                detail={"note": "abstain"},
            )

        # Stale-data submit gate (fail-closed). The driving book snapshot /
        # price-feed candle that produced this edge must not have gone stale
        # while the cycle churned. Applies to both shadow and live so paper
        # evidence stays honest; disabled entirely when no policy is wired.
        stale = self._stale_gate_block(decision, snapshot_ts, is_live_market)
        if stale is not None:
            return stale

        # Execution-policy guard (Wave-2 A2/F2). No-op for the control policy;
        # a non-control adverse-guard maker (C3) may refuse a quote whose model
        # diverges from the market prior beyond the cap. Applied to both books
        # so paper evidence honors the same guard the live policy would.
        guarded = self._execution_policy_block(decision, market_prior_yes)
        if guarded is not None:
            return guarded

        # Taker policy (Wave-5, tournament-backed): when the operator-selected
        # policy takes liquidity (C1), reprice the order to cross the freshest
        # book instead of resting a maker quote. Applied BEFORE the shadow/live
        # fork so paper evidence accrues under the same policy the live path
        # would use. Fail-closed on any missing/unpriceable book or an EV (net
        # of the taker fee) below the policy minimum.
        repriced = self._apply_taker_policy(decision)
        if isinstance(repriced, TradeOutcome):
            return repriced
        decision = repriced

        if self.mode is SessionMode.SHADOW:
            submitted_at = datetime.now(timezone.utc)
            expiration_ts = int(submitted_at.timestamp()) + order_ttl_seconds(
                decision.market_ticker
            )
            detail: dict[str, Any] = {
                "note": (
                    "shadow taker order (crossed book) pending witnessed fill"
                    if self.execution_policy.mode == "taker"
                    else "shadow maker order pending witnessed fill"
                ),
                "state": "resting",
                "side": decision.side,
                "count": decision.count,
                "expiration_ts": expiration_ts,
                "queue_snapshot_available": False,
            }
            if self.shadow_book_fn is not None:
                try:
                    from autonomy.live_book import normalize_orderbook_levels

                    book = self.shadow_book_fn(decision.market_ticker)
                    recognized = isinstance(book, dict) and any(
                        key in book for key in ("yes", "no", "yes_dollars", "no_dollars")
                    )
                    if recognized:
                        levels = normalize_orderbook_levels(book, decision.side)
                        detail.update({
                            "queue_snapshot_available": True,
                            "queue_ahead_contracts": round(sum(
                                count for price, count in levels
                                if price == decision.price_cents
                            ), 4),
                            "book_snapshot_at": submitted_at.isoformat(),
                        })
                    else:
                        detail["queue_snapshot_error"] = "unrecognized_orderbook_schema"
                except Exception as exc:
                    detail["queue_snapshot_error"] = type(exc).__name__
            if (
                detail.get("queue_snapshot_available")
                and float(detail.get("queue_ahead_contracts") or 0)
                    > MAX_QUEUE_AHEAD_CONTRACTS
            ):
                return TradeOutcome(
                    decision_id=decision.decision_id,
                    market_ticker=decision.market_ticker,
                    kind=OutcomeKind.BLOCKED_LOCAL,
                    order_id=None,
                    fill_count=0,
                    fill_price_cents=None,
                    pnl_cents=None,
                    broker_contacted=False,
                    detail={
                        "reason": "queue_ahead_exceeds_execution_cap",
                        "queue_ahead_contracts": detail["queue_ahead_contracts"],
                        "maximum_queue_ahead_contracts": MAX_QUEUE_AHEAD_CONTRACTS,
                    },
                )
            return TradeOutcome(
                decision_id=decision.decision_id,
                market_ticker=decision.market_ticker,
                kind=OutcomeKind.SHADOW,
                order_id=f"shadow-{decision.decision_id}",
                fill_count=0,
                fill_price_cents=decision.price_cents,
                pnl_cents=None,
                broker_contacted=False,
                detail=detail,
            )

        # LIVE: re-validate authority + kill switch at the moment of submit.
        session = load_session(self.session_path)
        if not session.get("valid") or session.get("mode") != SessionMode.LIVE.value:
            return self._blocked(decision, f"live session invalid: {session.get('reason', 'unknown')}")
        if kill_switch_active(self.kill_path):
            return self._blocked(decision, "kill switch active")

        # Re-check venue halt state at the moment of submit, not just at cycle
        # start: a maintenance window or trading pause can open mid-cycle.
        # Fail-open on a fetch error (unknown is not down) to match the
        # cycle-start doctrine and never become its own stall point.
        if self.exchange_status_fn is not None:
            try:
                venue = self.exchange_status_fn() or {}
            except Exception:
                venue = {}
            if venue.get("exchange_active") is False:
                return self._blocked(decision, "exchange_maintenance_at_submit")
            if venue.get("trading_active") is False:
                return self._blocked(decision, "trading_halted_at_submit")

        # Real-time re-quote guard: if the freshest book shows our resting
        # maker price would now cross (take liquidity), skip — the edge was
        # computed as a maker and adverse selection has arrived. (Maker path
        # only: a taker policy crossing the book is the intent, not adverse
        # selection — its EV was just re-checked against the same fresh book.)
        if self.quote_fn is not None and self.execution_policy.mode != "taker":
            try:
                fresh = self.quote_fn(decision.market_ticker)
            except Exception:
                fresh = None
            if fresh:
                if decision.side == "yes" and fresh.get("yes_ask") is not None and decision.price_cents >= fresh["yes_ask"]:
                    return self._blocked(decision, "quote_crossed_repriced_out_yes")
                if decision.side == "no" and fresh.get("no_ask") is not None and decision.price_cents >= fresh["no_ask"]:
                    return self._blocked(decision, "quote_crossed_repriced_out_no")
                bid = fresh.get(f"{decision.side}_bid")
                bid_size = fresh.get(f"{decision.side}_bid_size")
                if bid is not None and decision.price_cents < int(bid):
                    return self._blocked(decision, "quote_behind_current_best_bid")
                if (
                    bid is not None and decision.price_cents == int(bid)
                    and bid_size is not None
                    and float(bid_size) > MAX_QUEUE_AHEAD_CONTRACTS
                ):
                    return self._blocked(decision, "queue_ahead_exceeds_execution_cap")

        from predator_mesh.brokers.livebrokerfirewall_adapter import LimitOrderRequest

        # Exchange-enforced TTL replaces cancel loops (the repo's
        # no-direct-cancel-bypass gates forbid direct cancels): a resting
        # maker quote the market has moved away from dies on its own.
        # Fast verticals get short quotes: an hourly crypto bucket moves its
        # fair value in minutes, and a stale maker quote there is standing
        # adverse selection.
        ttl_seconds = order_ttl_seconds(decision.market_ticker)
        expiration_ts = int(datetime.now(timezone.utc).timestamp()) + ttl_seconds
        request = LimitOrderRequest(
            venue="KALSHI",
            order_type="LIMIT",
            market_orders_allowed=False,
            side=decision.side,
            action="buy",
            price=decision.price_cents,
            quantity=decision.count,
            idempotency_key=self._idempotency_key(decision),
            market_ticker=decision.market_ticker,
            proof_id=f"autonomy-{decision.decision_id}",
            proof_target="AUTONOMOUS_SESSION",
            client_order_id=self._idempotency_key(decision),
            max_order_count=1,
            max_order_size_cents=max(100, decision.notional_cents),
            expiration_ts=expiration_ts,
        )
        adapter = self._make_adapter(decision)
        try:
            result = await adapter.submit_limit_order(request)
        finally:
            try:
                await adapter.close()
            except Exception:
                pass

        if result.submitted and result.order_id:
            return TradeOutcome(
                decision_id=decision.decision_id,
                market_ticker=decision.market_ticker,
                kind=OutcomeKind.ACCEPTED,
                order_id=result.order_id,
                fill_count=0,
                fill_price_cents=decision.price_cents,
                pnl_cents=None,
                broker_contacted=True,
                detail={"state": result.state},
            )
        raw = dict(result.raw or {})
        transport_witnessed = raw.get("stage") == "broker_transport" or raw.get("status_code") is not None
        return TradeOutcome(
            decision_id=decision.decision_id,
            market_ticker=decision.market_ticker,
            kind=OutcomeKind.REJECTED if transport_witnessed else OutcomeKind.BLOCKED_LOCAL,
            order_id=None,
            fill_count=0,
            fill_price_cents=None,
            pnl_cents=None,
            broker_contacted=bool(transport_witnessed),
            detail={"errors": list(result.errors), "raw": raw},
        )

    def _make_adapter(self, decision: Decision):
        if self.adapter_factory is not None:
            return self.adapter_factory(decision)
        from predator_mesh.brokers.kalshi_livebrokerfirewall_adapter import (
            KalshiLiveBrokerFirewallAdapter,
        )

        return KalshiLiveBrokerFirewallAdapter(
            live_submit_enabled=True,
            caps_confirmed=True,
            kill_switch_active=kill_switch_active(self.kill_path),
            command_seal_ready=True,
            resolver_armable=True,
            require_proof_lock=False,
            max_order_notional_cents=max(100, decision.notional_cents),
        )

    def _stale_gate_block(
        self, decision: Decision, snapshot_ts: Any | None, is_live_market: bool
    ) -> TradeOutcome | None:
        """Return a BLOCKED_LOCAL outcome if the driving snapshot is stale.

        No-op (returns None) when no staleness policy is configured. When a
        policy is configured the gate is fail-closed: a missing/unparseable/
        future snapshot timestamp refuses the order just as a too-old one does.
        """
        if self.staleness_policy is None:
            return None
        verdict = evaluate_snapshot_freshness(
            decision.market_ticker,
            snapshot_ts,
            self._now_fn(),
            is_live_market=is_live_market,
            policy=self.staleness_policy,
        )
        if verdict["fresh"]:
            return None
        self.stale_block_count += 1
        return TradeOutcome(
            decision_id=decision.decision_id,
            market_ticker=decision.market_ticker,
            kind=OutcomeKind.BLOCKED_LOCAL,
            order_id=None,
            fill_count=0,
            fill_price_cents=None,
            pnl_cents=None,
            broker_contacted=False,
            detail={
                "reason": verdict["reason"],
                "snapshot_age_seconds": verdict["age_seconds"],
                "max_age_seconds": verdict["max_age_seconds"],
                "stale_block_count": self.stale_block_count,
            },
        )

    def _execution_policy_block(
        self, decision: Decision, market_prior_yes: float | None
    ) -> TradeOutcome | None:
        """Refuse a quote the active execution policy's guards reject.

        Returns None (no-op) for the control policy, so C0 reproduces current
        behavior exactly. For a non-control adverse-guard maker (C3), a model
        that diverges from the market prior beyond ``divergence_cap_cents`` is
        refused: the wider the divergence, the more the fill is adverse
        information rather than value. The guard fails open when no market prior
        is available (it cannot evaluate divergence) rather than refusing blind.
        """
        policy = self.execution_policy
        if policy.is_control():
            return None
        cap = policy.divergence_cap_cents
        if cap is not None and market_prior_yes is not None:
            model_yes = float(decision.forecast.probability_yes)
            divergence_cents = abs(model_yes - float(market_prior_yes)) * 100.0
            if divergence_cents > cap:
                return TradeOutcome(
                    decision_id=decision.decision_id,
                    market_ticker=decision.market_ticker,
                    kind=OutcomeKind.BLOCKED_LOCAL,
                    order_id=None,
                    fill_count=0,
                    fill_price_cents=None,
                    pnl_cents=None,
                    broker_contacted=False,
                    detail={
                        "reason": "execution_policy_divergence_cap",
                        "cohort": policy.cohort,
                        "divergence_cents": round(divergence_cents, 4),
                        "divergence_cap_cents": cap,
                    },
                )
        return None

    def _apply_taker_policy(self, decision: Decision) -> "Decision | TradeOutcome":
        """Reprice a decision to cross the freshest book under a taker policy.

        No-op (returns the decision unchanged) unless the active policy's mode
        is taker. Otherwise: fetch the freshest book, require a priceable ask
        for the decision's side, re-check EV net of the Kalshi taker fee
        against ``taker_min_ev_cents``, and return a copy of the decision
        priced at the ask. Every failure blocks fail-closed — a taker policy
        never silently degrades back into a resting maker quote.
        """
        if self.execution_policy.mode != "taker":
            return decision
        fresh = None
        if self.quote_fn is not None:
            try:
                fresh = self.quote_fn(decision.market_ticker)
            except Exception:
                fresh = None
        ask = (fresh or {}).get(f"{decision.side}_ask")
        if ask is None:
            return self._blocked(decision, "taker_no_fresh_book")
        try:
            ask = int(ask)
        except (TypeError, ValueError):
            return self._blocked(decision, "taker_ask_unpriceable")
        if not (1 <= ask <= 99):
            return self._blocked(decision, "taker_ask_unpriceable")
        from dataclasses import replace as dataclass_replace

        from autonomy.fees import kalshi_taker_fee_cents

        p_yes = float(decision.forecast.probability_yes)
        p_side = p_yes if decision.side == "yes" else 1.0 - p_yes
        fee = kalshi_taker_fee_cents(ask, decision.count, decision.market_ticker)
        ev_per_contract = p_side * 100.0 - ask - (fee / max(1, decision.count))
        min_ev = float(self.execution_policy.taker_min_ev_cents or 0.0)
        if ev_per_contract < min_ev:
            return self._blocked(decision, "taker_ev_below_min")
        return dataclass_replace(decision, price_cents=ask)

    def _blocked(self, decision: Decision, reason: str) -> TradeOutcome:
        return TradeOutcome(
            decision_id=decision.decision_id,
            market_ticker=decision.market_ticker,
            kind=OutcomeKind.BLOCKED_LOCAL,
            order_id=None,
            fill_count=0,
            fill_price_cents=None,
            pnl_cents=None,
            broker_contacted=False,
            detail={"reason": reason},
        )
