"""Session assembly and lifecycle: the only operator surface is start/stop."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from autonomy.executor import (
    AUTONOMY_ACK,
    KILL_PATH,
    SESSION_ACCOUNTING_VERSION,
    SESSION_PATH,
    Executor,
    load_session,
)
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
        "accounting_version": SESSION_ACCOUNTING_VERSION,
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
    def normalized_risk(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            bankroll = int(raw.get("bankroll_cents", 0))
            state = RiskBrain(path).load_state(bankroll)
            result = state.to_dict()
            result["accounting_version"] = 2
            if int(raw.get("accounting_version", 1)) < 2:
                result["evidence_reset_pending_save"] = True
            return result
        except Exception:
            return {"error": "unreadable"}

    shadow_risk = normalized_risk(Path("runtime/autonomy/risk_state.json"))
    live_risk = normalized_risk(Path("runtime/autonomy/risk_state_live.json"))
    status["risk_states"] = {"shadow": shadow_risk, "live": live_risk}
    active_scope = "live" if session.get("mode") == SessionMode.LIVE.value else "shadow"
    status["risk_state"] = status["risk_states"].get(active_scope)
    return status


def _ensure_creds_loaded() -> None:
    """Load whitelisted .env credentials (idempotent, never overwrites)."""
    try:
        from core.env_loader import load_whitelisted_env

        load_whitelisted_env()
    except Exception:
        pass  # absent .env just means the signed call will fail loudly


def _run_coro_sync(coro):
    """Run a coroutine to completion from synchronous code — safely from
    inside OR outside a running event loop.

    The live brain calls these sync helpers from within its own async cycle;
    a bare asyncio.run() there raises ("cannot be called from a running
    event loop") and the silent-fallback callers would quietly substitute
    shadow values — a live session sizing risk off a fake bankroll. A
    single-use worker thread with its own loop is dull and correct.
    """
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _live_balance_cents() -> int:
    """Authenticated balance read through the existing signed client."""
    from kalshi.client import KalshiClient

    _ensure_creds_loaded()

    async def fetch() -> int:
        client = KalshiClient()
        try:
            data = await client.get_account()
        finally:
            await client.close()
        return int(data.get("balance", 0))

    return _run_coro_sync(fetch())


def _order_status_fn(order_id: str) -> dict[str, Any]:
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

    return _run_coro_sync(fetch())


def build_brain(mode: SessionMode):
    """Assemble the full predator stack for the given mode."""
    from autonomy.brain import PredatorBrain

    from autonomy.signals.crypto_indicators import (
        CryptoDataHub,
        CryptoDvolSignal,
        CryptoEmpiricalRegimeSignal,
        CryptoTechnicalCompositeSignal,
    )
    from autonomy.signals.crypto_macro import CryptoMacroRegimeSignal
    from autonomy.signals.crypto_spot import CryptoEwmaTailSignal
    from autonomy.signals.sportsbook import SportsbookConsensusSignal
    from autonomy.signals.sports_intelligence import (
        BaseballIntelligenceSignal,
        TeamSportsIntelligenceSignal,
    )

    ledger = AutonomyLedger()
    registry = SourceRegistry(health_path=Path("runtime/autonomy/source_health.json"))
    registry.register(MarketPriorSignal())
    registry.register(OpenMeteoWeatherSignal.from_calibration())
    crypto_hub = CryptoDataHub()
    registry.register(CryptoSpotVolSignal(fetch_spot_and_vol=crypto_hub.flat_spot_and_vol))
    # Challenger crypto model (EWMA vol + fat tails) runs beside the champion
    # under its own name; the contested record decides which earns weight.
    registry.register(CryptoEwmaTailSignal(fetch_spot_and_vol=crypto_hub.ewma_spot_and_vol))
    # Empirical regimes, a bounded technical composite, and Deribit implied vol
    # are logged as challenger-only evidence. The forecaster excludes them until
    # an explicit point-in-time promotion review; breadth cannot silently alter risk.
    registry.register(CryptoEmpiricalRegimeSignal(fetch_state=crypto_hub.state))
    registry.register(CryptoTechnicalCompositeSignal(fetch_state=crypto_hub.state))
    registry.register(CryptoDvolSignal(fetch_state=crypto_hub.state))
    # Multi-timeframe structure (S/R + trend channels + confirming
    # technicals): opines ONLY at actionable swing setups, challenger-only.
    from autonomy.signals.crypto_structure import CryptoStructureSignal

    registry.register(CryptoStructureSignal(fetch_state=crypto_hub.state))
    # Macro risk-regime (S&P/DXY/VIX/10y/gold/oil) reused from the retired
    # commodities/econ pipeline as a crypto feature. Challenger-only: logged as
    # point-in-time evidence, excluded from the execution ensemble until a
    # settlement-backed promotion review, and abstains when no macro feed exists.
    registry.register(CryptoMacroRegimeSignal(fetch_state=crypto_hub.state))
    # Crypto-equities flow (BTC/ETH ETFs, crypto stocks, treasury companies
    # via the keyless Yahoo pipeline): institutional-appetite drift,
    # challenger-only, abstains without equity data.
    from autonomy.signals.crypto_equities import CryptoEquitiesSignal

    registry.register(CryptoEquitiesSignal(fetch_state=crypto_hub.state))
    # Volatility triangulation (blended flat/EWMA/implied sigma + settlement-
    # proximity guard) and the VRP mean-reversion regime, both challenger-only
    # over the shared hub state. The blend + guard reach execution only via a
    # WS-14 promotion; the champion is never silently altered.
    from autonomy.signals.crypto_vol import (
        CryptoBlendSigmaSignal,
        CryptoVrpRegimeSignal,
    )

    registry.register(CryptoBlendSigmaSignal(fetch_state=crypto_hub.state))
    registry.register(CryptoVrpRegimeSignal(fetch_state=crypto_hub.state))
    # CommoditiesSpotVolSignal is retained only as challenger evidence: with
    # COMMODITIES dropped from the scanner's trading verticals it no longer
    # receives tradable markets, but keeping it registered is harmless and
    # preserves its settled-market record.
    registry.register(CommoditiesSpotVolSignal())
    # One shared season monitor gates every sports warmup: dormant leagues
    # skip their per-cycle fetches and auto-wake when preseason games appear
    # on the scoreboard. Sharing one instance keeps one verdict cache and
    # one writer for the persisted season state.
    from autonomy.specialists.seasons import SeasonMonitor

    seasons = SeasonMonitor()
    registry.register(SportsEloSignal(seasons=seasons))
    # De-vigged sportsbook moneyline + open->close steam: the sharpest public
    # game forecast, and the trap detector when Elo fights the book.
    registry.register(SportsbookConsensusSignal())
    # New totals/first-inning models are recorded as challenger-only
    # point-in-time evidence. Their own feature gate keeps them out of the
    # execution ensemble until a settlement-backed promotion review.
    # UFC and Formula One intelligence retired 2026-07-12 (operator directive):
    # their markets route to no sports model and are simply never forecast.
    registry.register(BaseballIntelligenceSignal(seasons=seasons))
    registry.register(TeamSportsIntelligenceSignal(seasons=seasons))
    registry.register(CrossVenueSignal())
    # Empirical price->outcome curve mined from settled-market history; no
    # curve artifact on disk means the source simply never opines.
    registry.register(MarketDebiasSignal())
    # Reliability calibration wrappers (WS-18): re-emit curated sources'
    # forecasts isotonically recalibrated, challenger-only, at scopes with a
    # learned map. They wrap already-registered parent instances; a wrapper
    # abstains wherever no map exists, so parents are untouched. The corrected
    # view reaches execution only via a WS-14 promotion.
    from autonomy.reliability import CALIBRATED_SOURCES, CalibratedSignal, ReliabilityMaps

    reliability_maps = ReliabilityMaps()
    _by_name = {getattr(s, "name", ""): s for s in registry.sources()}
    for _parent_name in ("crypto_spot_vol", "crypto_ewma_t", "mlb_intelligence"):
        _parent = _by_name.get(_parent_name)
        if _parent is not None:
            registry.register(CalibratedSignal(
                _parent, maps=reliability_maps, sources=CALIBRATED_SOURCES))
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

    shadow_candle_fetcher = None
    shadow_trade_fetcher = None
    shadow_book_fetcher = None
    if not live:
        from autonomy.retro import default_fetch_candles
        from autonomy.reconciler import default_fetch_trades
        from kalshi.presubmit import default_fetch_orderbook

        shadow_candle_fetcher = default_fetch_candles
        shadow_trade_fetcher = default_fetch_trades
        shadow_book_fetcher = default_fetch_orderbook
    reconciler = Reconciler(
        ledger,
        order_status_fn=_order_status_fn if live else None,
        fetch_settled_page=default_fetch_settled_page,
        fetch_shadow_candles=shadow_candle_fetcher,
        fetch_shadow_trades=shadow_trade_fetcher,
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

    from autonomy.exchange_status import fetch_exchange_status

    # Live and shadow run concurrently (scheduled shadow task + operator live
    # session) — each gets its OWN risk state. Sharing one file would let the
    # shadow book's equity peak read as a catastrophic live drawdown.
    risk_state_path = Path("runtime/autonomy/risk_state_live.json") if live \
        else Path("runtime/autonomy/risk_state.json")

    return PredatorBrain(
        mode=mode,
        ledger=ledger,
        registry=registry,
        scanner=MarketScanner(),
        risk_brain=RiskBrain(state_path=risk_state_path),
        executor=Executor(mode, quote_fn=quote_fn, shadow_book_fn=shadow_book_fetcher),
        reconciler=reconciler,
        learner=Learner(ledger, router=router),
        balance_fn=_live_balance_cents if live else None,
        router=router,
        exchange_status_fn=fetch_exchange_status,
    )
