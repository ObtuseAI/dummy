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
from typing import Any

from autonomy.ontology import Decision, DecisionAction, OutcomeKind, SessionMode, TradeOutcome

SESSION_PATH = Path("runtime/autonomy/session.json")
KILL_PATH = Path("runtime/autonomy/KILL")

AUTONOMY_ACK = (
    "I authorize an autonomous Dummy trading session with self-managed risk "
    "under the LiveBrokerFirewall, LIMIT orders only, until I stop it"
)


def load_session(path: Path | None = None) -> dict[str, Any]:
    path = path or SESSION_PATH
    if not path.exists():
        return {"mode": SessionMode.SHADOW.value, "valid": False, "reason": "no session file"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"mode": SessionMode.SHADOW.value, "valid": False, "reason": "unreadable session file"}
    if data.get("mode") == SessionMode.LIVE.value:
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
    ) -> None:
        self.mode = mode
        self.session_path = session_path or SESSION_PATH
        self.kill_path = kill_path or KILL_PATH
        self.adapter_factory = adapter_factory
        # Optional pre-submit fresh-book read; when supplied, a maker quote that
        # has crossed since the scan is skipped instead of filled as a taker.
        self.quote_fn = quote_fn

    def _idempotency_key(self, decision: Decision) -> str:
        return hashlib.sha256(f"autonomy|{decision.decision_id}".encode("utf-8")).hexdigest()[:32]

    async def execute(self, decision: Decision) -> TradeOutcome:
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

        if self.mode is SessionMode.SHADOW:
            return TradeOutcome(
                decision_id=decision.decision_id,
                market_ticker=decision.market_ticker,
                kind=OutcomeKind.SHADOW,
                order_id=f"shadow-{decision.decision_id}",
                fill_count=0,
                fill_price_cents=decision.price_cents,
                pnl_cents=None,
                broker_contacted=False,
                detail={"note": "shadow book order", "side": decision.side, "count": decision.count},
            )

        # LIVE: re-validate authority + kill switch at the moment of submit.
        session = load_session(self.session_path)
        if not session.get("valid") or session.get("mode") != SessionMode.LIVE.value:
            return self._blocked(decision, f"live session invalid: {session.get('reason', 'unknown')}")
        if kill_switch_active(self.kill_path):
            return self._blocked(decision, "kill switch active")

        # Real-time re-quote guard: if the freshest book shows our resting
        # maker price would now cross (take liquidity), skip — the edge was
        # computed as a maker and adverse selection has arrived.
        if self.quote_fn is not None:
            try:
                fresh = self.quote_fn(decision.market_ticker)
            except Exception:
                fresh = None
            if fresh:
                if decision.side == "yes" and fresh.get("yes_ask") is not None and decision.price_cents >= fresh["yes_ask"]:
                    return self._blocked(decision, "quote_crossed_repriced_out_yes")
                if decision.side == "no" and fresh.get("no_ask") is not None and decision.price_cents >= fresh["no_ask"]:
                    return self._blocked(decision, "quote_crossed_repriced_out_no")

        from predator_mesh.brokers.livebrokerfirewall_adapter import LimitOrderRequest

        # Exchange-enforced TTL replaces cancel loops (the repo's
        # no-direct-cancel-bypass gates forbid direct cancels): a resting
        # maker quote the market has moved away from dies on its own.
        # Fast verticals get short quotes: an hourly crypto bucket moves its
        # fair value in minutes, and a stale maker quote there is standing
        # adverse selection.
        from autonomy.ontology import Vertical
        from autonomy.scanner import classify_vertical

        ttl_seconds = 20 * 60 if classify_vertical(decision.market_ticker) is Vertical.CRYPTO else 45 * 60
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
