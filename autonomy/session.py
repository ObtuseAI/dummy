"""Session assembly and lifecycle: the only operator surface is start/stop."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from autonomy.executor import AUTONOMY_ACK, KILL_PATH, SESSION_PATH, Executor, load_session
from autonomy.learner import Learner
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import SessionMode
from autonomy.reconciler import Reconciler
from autonomy.risk_brain import RiskBrain
from autonomy.scanner import MarketScanner
from autonomy.signals.base import SourceRegistry
from autonomy.signals.commodities_spot import CommoditiesSpotVolSignal
from autonomy.signals.cross_venue import CrossVenueSignal
from autonomy.signals.crypto_spot import CryptoSpotVolSignal
from autonomy.signals.market_debias import MarketDebiasSignal
from autonomy.signals.market_prior import MarketPriorSignal
from autonomy.signals.sports_elo import SportsEloSignal
from autonomy.signals.weather_openmeteo import OpenMeteoWeatherSignal


def canary_readiness(check_balance: bool = False) -> dict[str, Any]:
    """Dry evidence check for a first live canary (read-only)."""
    from autonomy.canary import evaluate_canary_readiness

    ledger = AutonomyLedger()
    balance = None
    if check_balance:
        try:
            balance = _live_balance_cents()
        except Exception:
            balance = None
    try:
        return evaluate_canary_readiness(ledger, balance_cents=balance).to_dict()
    finally:
        ledger.close()


def start_session(mode: SessionMode, ack: str = "", hours: float = 24.0,
                  operator: str = "", session_path: Path | None = None,
                  override_evidence_gate: bool = False) -> dict[str, Any]:
    """Write the session authority. LIVE requires the exact typed ack AND a
    passing evidence gate (settlements + a market-beating source + weights)."""
    path = session_path or SESSION_PATH
    if mode is SessionMode.LIVE and ack != AUTONOMY_ACK:
        return {"started": False, "reason": "LIVE requires exact ack", "required_ack": AUTONOMY_ACK}
    if mode is SessionMode.LIVE and not override_evidence_gate:
        from autonomy.canary import evaluate_canary_readiness

        gate_ledger = AutonomyLedger()
        try:
            readiness = evaluate_canary_readiness(gate_ledger)
        finally:
            gate_ledger.close()
        if not readiness.ready:
            return {
                "started": False,
                "reason": "LIVE blocked by evidence gate",
                "blockers": readiness.blockers,
                "evidence": readiness.evidence,
                "override_hint": "pass override_evidence_gate=True only with deliberate operator intent",
            }
    now = datetime.now(timezone.utc)
    payload = {
        "mode": mode.value,
        "operator": operator or "operator",
        "started_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=hours)).isoformat(),
        "ack": ack if mode is SessionMode.LIVE else "",
        "limit_orders_only": True,
        "market_orders_allowed": False,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    # Starting a session clears a stale kill file only on explicit start.
    if KILL_PATH.exists():
        KILL_PATH.unlink()
    return {"started": True, "mode": mode.value, "expires_at": payload["expires_at"]}


def stop_session(session_path: Path | None = None) -> dict[str, Any]:
    """Kill switch + disarm: instant, unconditional."""
    KILL_PATH.parent.mkdir(parents=True, exist_ok=True)
    KILL_PATH.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    path = session_path or SESSION_PATH
    if path.exists():
        path.unlink()
    return {"stopped": True, "kill_switch": str(KILL_PATH)}


def session_status(ledger: AutonomyLedger | None = None) -> dict[str, Any]:
    session = load_session()
    status: dict[str, Any] = {
        "session": session,
        "kill_switch_active": KILL_PATH.exists(),
    }
    own_ledger = ledger is None
    ledger = ledger or AutonomyLedger()
    try:
        status["performance"] = ledger.performance_summary()
    finally:
        if own_ledger:
            ledger.close()
    risk_path = Path("runtime/autonomy/risk_state.json")
    if risk_path.exists():
        try:
            status["risk_state"] = json.loads(risk_path.read_text(encoding="utf-8"))
        except Exception:
            status["risk_state"] = {"error": "unreadable"}
    return status


def _ensure_creds_loaded() -> None:
    """Load whitelisted .env credentials (idempotent, never overwrites)."""
    try:
        from core.env_loader import load_whitelisted_env

        load_whitelisted_env()
    except Exception:
        pass  # absent .env just means the signed call will fail loudly


def _live_balance_cents() -> int:
    """Authenticated balance read through the existing signed client."""
    import asyncio

    from kalshi.client import KalshiClient

    _ensure_creds_loaded()

    async def fetch() -> int:
        client = KalshiClient()
        try:
            data = await client.get_account()
        finally:
            await client.close()
        return int(data.get("balance", 0))

    return asyncio.run(fetch())


def _order_status_fn(order_id: str) -> dict[str, Any]:
    import asyncio

    from kalshi.client import KalshiClient

    _ensure_creds_loaded()

    async def fetch() -> dict[str, Any]:
        client = KalshiClient()
        try:
            data = await client._request("GET", f"/portfolio/orders/{order_id}")
        finally:
            await client.close()
        order = data.get("order", data)
        return order if isinstance(order, dict) else {}

    return asyncio.run(fetch())


def build_brain(mode: SessionMode):
    """Assemble the full predator stack for the given mode."""
    from autonomy.brain import PredatorBrain

    from autonomy.signals.crypto_spot import CryptoEwmaTailSignal
    from autonomy.signals.sportsbook import SportsbookConsensusSignal

    ledger = AutonomyLedger()
    registry = SourceRegistry(health_path=Path("runtime/autonomy/source_health.json"))
    registry.register(MarketPriorSignal())
    registry.register(OpenMeteoWeatherSignal.from_calibration())
    registry.register(CryptoSpotVolSignal())
    # Challenger crypto model (EWMA vol + fat tails) runs beside the champion
    # under its own name; the contested record decides which earns weight.
    registry.register(CryptoEwmaTailSignal())
    registry.register(CommoditiesSpotVolSignal())
    registry.register(SportsEloSignal())
    # De-vigged sportsbook moneyline + open->close steam: the sharpest public
    # game forecast, and the trap detector when Elo fights the book.
    registry.register(SportsbookConsensusSignal())
    registry.register(CrossVenueSignal())
    # Empirical price->outcome curve mined from settled-market history; no
    # curve artifact on disk means the source simply never opines.
    registry.register(MarketDebiasSignal())
    # The LLM panel (debate.py) supersedes the single-model analyst and runs as
    # a post-forecast adjudicator on top-K markets inside the brain, not as a
    # per-market source (it must await the router from the async loop).

    live = mode is SessionMode.LIVE
    if live:
        # The signed client and the firewall adapter read credentials from the
        # process environment; a live brain must have them loaded up front.
        _ensure_creds_loaded()
    # No cancel_fn: the repo's no-direct-cancel-bypass gates forbid direct
    # cancel calls; stale maker quotes die via order-level expiration_ts.
    from autonomy.reconciler import default_fetch_settled_page

    reconciler = Reconciler(
        ledger,
        order_status_fn=_order_status_fn if live else None,
        fetch_settled_page=default_fetch_settled_page,
    )
    quote_fn = None
    if live:
        from autonomy.live_book import fresh_best_quote

        quote_fn = fresh_best_quote
    router = None
    try:
        from model_router.router import ModelRouter

        router = ModelRouter()
        # Enable the live LLM panel for THIS process only when the operator
        # opts in via env. The global config file stays false so the test
        # suite never makes paid network calls.
        if os.environ.get("DUMMY_DEBATE_LIVE") == "1":
            router.config.live_model_calls_enabled = True
    except Exception:
        router = None

    return PredatorBrain(
        mode=mode,
        ledger=ledger,
        registry=registry,
        scanner=MarketScanner(),
        risk_brain=RiskBrain(),
        executor=Executor(mode, quote_fn=quote_fn),
        reconciler=reconciler,
        learner=Learner(ledger, router=router),
        balance_fn=_live_balance_cents if live else None,
        router=router,
    )
