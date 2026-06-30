import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional
from core.state import STATE
from core.config_loader import load_caps
from core.ontology import AccountMode, LiveOrderRequest, FirewallVerdict, LiveOrderResult, OrderBook, Forecast, Position
from live_firewall.exposure_tracker import ExposureTracker
from compliance.governor import assess_compliance
from core.logger import logger
from repo_harvester.incorporation_engine import get_allowed_adapter_names

REJECTED_ADAPTERS: set[str] = set()


def mark_adapter_rejected(adapter_name: str):
    REJECTED_ADAPTERS.add(adapter_name)


def _check_secret_redaction(text: str) -> bool:
    # Load the inherited Blunder sentinel module directly from its file path so
    # we do not trigger the original package __init__ (which still references the
    # original `blunder` namespace).
    import importlib.util
    import pathlib
    sentinel_path = pathlib.Path(__file__).parent.parent / "core" / "inherited_blunder" / "inflow" / "secret_sentinel.py"
    spec = importlib.util.spec_from_file_location("inherited_secret_sentinel", sentinel_path)
    sentinel = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sentinel)
    return len(sentinel.scan_text_for_risk(text)) == 0


class LiveBrokerFirewall:
    def __init__(self, kalshi_client, exposure_tracker: ExposureTracker):
        self.client = kalshi_client
        self.exposure = exposure_tracker

    async def evaluate(self, req: LiveOrderRequest, orderbook: OrderBook, forecast: Forecast) -> FirewallVerdict:
        caps = load_caps()
        reasons: list[tuple[str, str]] = []

        def fail(by: str, reason: str) -> FirewallVerdict:
            logger.info("Firewall rejection", extra={"component": "firewall", "rejected_by": by, "reason": reason, "proposal_id": req.proposal_id})
            return FirewallVerdict(allow=False, reason=reason, rejected_by=by)

        if STATE.mode != AccountMode.AUTONOMOUS_LIVE_CAPPED:
            return fail("mode", "Mode is not AUTONOMOUS_LIVE_CAPPED")
        if STATE.kill_switch.active:
            return fail("kill_switch", "Kill switch active")
        if STATE.emergency_stop.active:
            return fail("emergency_stop", "Emergency stop active")
        if not os.environ.get("KALSHI_API_KEY_ID"):
            return fail("secrets", "API key missing")
        allowed = get_allowed_adapter_names()
        if req.adapter_name in REJECTED_ADAPTERS:
            return fail("repo_bypass", "Adapter rejected by repo harvester")
        if req.adapter_name not in allowed:
            return fail("unknown_adapter", f"Unknown or untested adapter {req.adapter_name}")
        if not _check_secret_redaction(str(req.model_dump())):
            return fail("secret_redaction", "Secret redaction check failed")
        if req.market_ticker not in caps.allowed_markets:
            return fail("market_allowlist", "Market not allowlisted")
        if any(req.market_ticker.startswith(c) for c in caps.blocked_categories):
            return fail("blocked_category", "Contract category blocked")
        compliance = assess_compliance(req.market_ticker, req.contract_ticker, caps=caps)
        if not compliance.passed:
            return fail("compliance", compliance.reason)
        if orderbook.timestamp < datetime.now(timezone.utc) - timedelta(seconds=30):
            return fail("stale_data", "Stale market data")
        if not orderbook.bids or not orderbook.asks:
            return fail("liquidity", "Missing orderbook data")
        spread = orderbook.asks[0].price - orderbook.bids[0].price
        if spread > caps.max_spread_cents:
            return fail("spread", "Spread too wide")
        total_liquidity = sum(l.size for l in orderbook.bids) + sum(l.size for l in orderbook.asks)
        if total_liquidity < caps.min_liquidity:
            return fail("liquidity", "Liquidity too low")
        if forecast.edge_after_fees <= 0:
            return fail("edge", "Fees remove expected edge")
        if forecast.expected_edge < Decimal(caps.min_edge_bps) / Decimal(10000):
            return fail("edge", "Expected edge below threshold")
        if not req.strategy_proof_reference or not req.forecast_proof_reference:
            return fail("proof", "Missing proof reference")
        order_value = req.price_cents * req.size
        if order_value > caps.max_single_order_cents:
            return fail("single_order_cap", "Single order cap exceeded")
        if self.exposure.market_exposure_cents(req.market_ticker) + order_value > caps.max_market_exposure_cents:
            return fail("market_exposure_cap", "Market exposure cap exceeded")
        if self.exposure.total_exposure_cents() + order_value > caps.max_total_live_exposure_cents:
            return fail("total_exposure_cap", "Total exposure cap exceeded")
        if self.exposure.correlated_exposure_cents(req.market_ticker) + order_value > caps.max_total_live_exposure_cents:
            return fail("correlated_exposure_cap", "Correlated exposure cap exceeded")
        if STATE.daily_loss_cents >= caps.max_daily_loss_cents:
            return fail("daily_loss_cap", "Daily loss cap exceeded")
        if self.exposure.open_markets() >= caps.max_open_markets:
            return fail("open_markets", "Max open markets exceeded")
        if self.exposure.orders_last_hour() >= caps.max_orders_per_hour:
            return fail("frequency_cap", "Order frequency cap exceeded")
        if self.exposure.open_order_count() >= caps.max_orders_per_hour:
            return fail("open_order_cap", "Open order count exceeded")
        if forecast.settlement_risk_score > Decimal("0.8"):
            return fail("settlement_risk", "Settlement risk too high")

        return FirewallVerdict(allow=True, reason="All gates passed")

    async def submit(self, req: LiveOrderRequest, orderbook: OrderBook, forecast: Forecast) -> LiveOrderResult:
        verdict = await self.evaluate(req, orderbook, forecast)
        if not verdict.allow:
            return LiveOrderResult(success=False, error=verdict.reason, proof_reference=req.strategy_proof_reference)
        if req.side not in ("yes", "no"):
            return LiveOrderResult(success=False, error="Invalid side", proof_reference=req.strategy_proof_reference)
        order = {
            "ticker": req.contract_ticker,
            "side": req.side,
            "action": "buy",
            "type": "limit",
            "count": req.size,
            "price": req.price_cents,
        }
        try:
            resp = await self.client.create_order(order)
            order_id = resp.get("order", {}).get("order_id") or resp.get("order_id")
            self.exposure.record_order(req.market_ticker, req.size, req.price_cents)
            self.exposure.add_open_order(order_id or "unknown", req.market_ticker, req.size, req.price_cents)
            self.exposure.update_position(Position(
                market_ticker=req.market_ticker,
                contract_ticker=req.contract_ticker,
                side=req.side,
                quantity=req.size,
                avg_price_cents=req.price_cents,
                unrealized_pnl_cents=0,
            ))
            return LiveOrderResult(success=True, order_id=order_id, proof_reference=req.strategy_proof_reference)
        except Exception as e:
            logger.error("Live order submit failed", extra={"component": "firewall", "error": str(e)})
            return LiveOrderResult(success=False, error=str(e), proof_reference=req.strategy_proof_reference)
