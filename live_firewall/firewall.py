import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional
from core.state import STATE
from core.config_loader import load_caps
from core.env_loader import kalshi_credential_status
from core.live_execution_mode import LiveExecutionMode, classify_live_execution_mode
from core.ontology import AccountMode, LiveOrderRequest, FirewallVerdict, LiveOrderResult, OrderBook, Forecast, Position
from core.proof_lock import proof_lock_clear as _proof_lock_clear
from live_firewall.exposure_tracker import ExposureTracker
from live_firewall.secret_sentinel import scan_text_for_risk
from compliance.governor import assess_compliance
from core.logger import logger
from core.live_submit_state import is_live_submit_armed, LIVE_SUBMIT_REQUIRED_ACK
from repo_harvester.incorporation_engine import get_allowed_adapter_names

REJECTED_ADAPTERS: set[str] = set()

LIVE_SUBMIT_PATH = Path("configs/live_submit.json")
ADAPTER_DESCRIPTOR_PATH = Path("runtime/operator_external/livebrokerfirewall_adapter_descriptor.json")
CAPS_PATH = Path("configs/caps.json")

# Safe broker-rejection diagnostic keys that may leave the firewall boundary.
_SAFE_BROKER_REJECTION_KEYS = ("status_code", "error_preview", "adapter_error_type", "stage")


def mark_adapter_rejected(adapter_name: str):
    REJECTED_ADAPTERS.add(adapter_name)


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _kalshi_credentials_ready() -> bool:
    """Return True if a Kalshi key id and private-key ref are present."""
    status = kalshi_credential_status()
    if not status.get("KALSHI_API_KEY_ID", {}).get("present"):
        return False
    key_refs = {
        "KALSHI_API_PRIVATE_KEY_PEM",
        "KALSHI_PRIVATE_KEY",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH",
        "KALSHI_PRIVATE_KEY_PATH",
    }
    for key in key_refs:
        entry = status.get(key, {})
        if not entry.get("present"):
            continue
        if "file_exists" in entry:
            if entry["file_exists"]:
                return True
        else:
            return True
    return False


def _load_live_submit_config() -> dict[str, Any]:
    if not LIVE_SUBMIT_PATH.exists():
        return {"enabled": False}
    try:
        data = json.loads(LIVE_SUBMIT_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"enabled": False}
    except Exception:
        return {"enabled": False}


def _caps_strict() -> bool:
    if not CAPS_PATH.exists():
        return False
    try:
        data = json.loads(CAPS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return False
    limit_only = data.get("order_type_policy") == "LIMIT_ONLY" or data.get("limit_orders_only") is True
    no_market = data.get("market_orders_allowed") is False or data.get("allow_market_orders") is False
    kill_on = data.get("kill_switch_enabled") is True or data.get("kill_switch_required") is True
    order_count_ok = data.get("max_order_count", 1) == 1
    return limit_only and no_market and kill_on and order_count_ok


def _descriptor_staged() -> bool:
    if not ADAPTER_DESCRIPTOR_PATH.exists():
        return False
    try:
        data = json.loads(ADAPTER_DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    except Exception:
        return False
    return (
        data.get("broker") == "KALSHI"
        and data.get("adapter_type") == "LiveBrokerFirewall"
        and data.get("order_type_policy") == "LIMIT_ONLY"
        and data.get("market_orders_allowed") is False
    )


def _command_seal_ready() -> bool:
    v297 = Path("artifacts/dummy/final_report_v297.json")
    if not v297.exists():
        return False
    try:
        data = json.loads(v297.read_text(encoding="utf-8"))
    except Exception:
        return False
    return str(data.get("execute_once_command_seal_controller_status", "")) == "PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT"


@dataclass
class RehearsalVerdict:
    would_submit: bool
    firewall_verdict: FirewallVerdict
    order: Optional[dict[str, Any]]
    blocked_reason: Optional[str]


def _check_secret_redaction(text: str) -> bool:
    return not scan_text_for_risk(text)


class LiveBrokerFirewall:
    def __init__(self, kalshi_client, exposure_tracker: ExposureTracker):
        self.client = kalshi_client
        self.exposure = exposure_tracker

    async def evaluate(self, req: LiveOrderRequest, orderbook: OrderBook, forecast: Forecast) -> FirewallVerdict:
        caps = load_caps()
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
        total_liquidity = sum(level.size for level in orderbook.bids) + sum(
            level.size for level in orderbook.asks
        )
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

    REQUIRED_ACKNOWLEDGEMENT = LIVE_SUBMIT_REQUIRED_ACK

    def _live_submit_enabled(self) -> bool:
        """Read the operator-approved live-submit flag.

        Returns True only if configs/live_submit.json is in the valid
        operator-approved one-proof enabled state per the shared state model.
        """
        return is_live_submit_armed()

    def _build_order(self, req: LiveOrderRequest) -> dict[str, Any]:
        # trade-api/v2 CreateOrder body: the limit price is side-specific
        # (yes_price/no_price) and client_order_id is required.
        order: dict[str, Any] = {
            "ticker": req.contract_ticker,
            "side": req.side,
            "action": "buy",
            "type": "limit",
            "count": req.size,
            "client_order_id": req.proposal_id,
        }
        if req.side == "no":
            order["no_price"] = req.price_cents
        else:
            order["yes_price"] = req.price_cents
        return order

    async def submit_rehearsal(
        self,
        req: LiveOrderRequest,
        orderbook: OrderBook,
        forecast: Forecast,
    ) -> RehearsalVerdict:
        """Run the full firewall evaluation but do not call the broker.

        If the firewall allows the request but live-submit is disabled, record
        the would-be order and the blocked reason.
        """
        verdict = await self.evaluate(req, orderbook, forecast)
        if not verdict.allow:
            return RehearsalVerdict(
                would_submit=False,
                firewall_verdict=verdict,
                order=None,
                blocked_reason=verdict.reason,
            )
        order = self._build_order(req)
        if not self._live_submit_enabled():
            return RehearsalVerdict(
                would_submit=False,
                firewall_verdict=verdict,
                order=order,
                blocked_reason="live_submit_disabled",
            )
        return RehearsalVerdict(
            would_submit=True,
            firewall_verdict=verdict,
            order=order,
            blocked_reason=None,
        )

    async def submit(self, req: LiveOrderRequest, orderbook: OrderBook, forecast: Forecast) -> LiveOrderResult:
        verdict = await self.evaluate(req, orderbook, forecast)
        if not verdict.allow:
            return LiveOrderResult(success=False, error=verdict.reason, proof_reference=req.strategy_proof_reference)
        if not self._live_submit_enabled():
            logger.info("Live submit blocked: live_submit flag disabled", extra={"component": "firewall", "proposal_id": req.proposal_id})
            return LiveOrderResult(success=False, error="live_submit_disabled", proof_reference=req.strategy_proof_reference)
        if req.side not in ("yes", "no"):
            return LiveOrderResult(success=False, error="Invalid side", proof_reference=req.strategy_proof_reference)
        order = self._build_order(req)
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

    async def submit_limit_order_adapter(
        self,
        req: Any,
    ) -> LiveOrderResult:
        """One-proof live submit through KalshiLiveBrokerFirewallAdapter.

        Fail-closed: any missing gate returns LiveOrderResult(success=False).
        This path is independent of the trading-focused evaluate() method so that
        the one-proof controlled pilot can submit without requiring a market
        allowlist or synthetic forecast.
        """
        # Local imports avoid a circular import through predator_mesh/__init__.
        from predator_mesh.brokers.kalshi_livebrokerfirewall_adapter import (
            KalshiLiveBrokerFirewallAdapter,
        )

        mode, blocker, ctx = classify_live_execution_mode(
            live_submit_config=_load_live_submit_config(),
            env=dict(os.environ),
            seal_status=("PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT" if _command_seal_ready() else "BLOCKED"),
            caps_strict=_caps_strict(),
            descriptor_staged=_descriptor_staged(),
            credentials_ready=_kalshi_credentials_ready(),
            proof_lock_clear=_proof_lock_clear(),
        )

        proof_reference = req.proof_id or ""

        if mode is LiveExecutionMode.DEFAULT_DISABLED:
            return LiveOrderResult(success=False, error="live_submit_disabled", proof_reference=proof_reference)

        if mode is not LiveExecutionMode.OPERATOR_ONE_PROOF_LIVE_READY:
            logger.info("Live adapter submit blocked", extra={"component": "firewall", "blocker": blocker})
            return LiveOrderResult(success=False, error=blocker, proof_reference=proof_reference)

        # Request-level policy validation (defense in depth).
        if req.order_type.upper() != "LIMIT":
            return LiveOrderResult(success=False, error="MARKET_ORDER_REJECTED", proof_reference=proof_reference)
        if req.market_orders_allowed:
            return LiveOrderResult(success=False, error="MARKET_ORDERS_NOT_ALLOWED", proof_reference=proof_reference)
        if req.max_order_count != 1:
            return LiveOrderResult(success=False, error="MAX_ORDER_COUNT_EXCEEDED", proof_reference=proof_reference)
        if not req.idempotency_key:
            return LiveOrderResult(success=False, error="IDEMPOTENCY_KEY_MISSING", proof_reference=proof_reference)
        if not req.proof_id or not req.proof_target:
            return LiveOrderResult(success=False, error="PROOF_LOCK_INCOMPLETE", proof_reference=proof_reference)
        if req.price * req.quantity > req.max_order_size_cents:
            return LiveOrderResult(success=False, error="ORDER_SIZE_CAP_EXCEEDED", proof_reference=proof_reference)

        adapter = KalshiLiveBrokerFirewallAdapter(
            live_submit_enabled=True,
            caps_confirmed=True,
            kill_switch_active=STATE.kill_switch.active,
            command_seal_ready=True,
            resolver_armable=True,
            require_proof_lock=False,  # lock handled by _proof_lock_clear and adapter's _attempted
        )

        try:
            submit_result = await adapter.submit_limit_order(req)
        except Exception as exc:
            logger.error("Adapter submit raised", extra={"component": "firewall", "error": str(exc)})
            return LiveOrderResult(success=False, error=f"ADAPTER_EXCEPTION:{type(exc).__name__}", proof_reference=proof_reference)
        finally:
            await adapter.close()

        if submit_result.submitted and submit_result.order_id:
            self.exposure.record_order(req.market_ticker, req.quantity, req.price)
            self.exposure.add_open_order(submit_result.order_id, req.market_ticker, req.quantity, req.price)
            self.exposure.update_position(Position(
                market_ticker=req.market_ticker,
                contract_ticker=req.market_ticker,
                side=req.side,
                quantity=req.quantity,
                avg_price_cents=req.price,
                unrealized_pnl_cents=0,
            ))
            return LiveOrderResult(success=True, order_id=submit_result.order_id, proof_reference=proof_reference)

        # Preserve the adapter's structured error code (no secret values).
        broker_error = submit_result.errors[0] if submit_result.errors else "BROKER_REJECTED"
        safe_raw = {k: submit_result.raw[k] for k in _SAFE_BROKER_REJECTION_KEYS if k in submit_result.raw}
        return LiveOrderResult(
            success=False,
            order_id=submit_result.order_id,
            error=broker_error,
            proof_reference=proof_reference,
            broker_rejection_code=broker_error,
            broker_rejection_safe_message=safe_raw.get("error_preview"),
            broker_rejection_http_status=safe_raw.get("status_code"),
            broker_rejection_adapter_error_type=safe_raw.get("adapter_error_type"),
            broker_rejection_stage=safe_raw.get("stage"),
            broker_rejection_raw_redacted=safe_raw or None,
        )
