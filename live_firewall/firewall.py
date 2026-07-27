import hashlib
import inspect
import json
import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Optional
from core.state import STATE
from core.caps_authority import evaluate_caps_authority
from core.config_loader import load_caps
from core.env_loader import kalshi_credential_status
from core.live_execution_mode import LiveExecutionMode, classify_live_execution_mode
from core.ontology import AccountMode, LiveOrderRequest, FirewallVerdict, LiveOrderResult, OrderBook, Forecast
from core.proof_lock import proof_lock_clear as _proof_lock_clear
from live_firewall.exposure_tracker import ExposureTracker
from live_firewall.secret_sentinel import scan_text_for_risk
from compliance.governor import assess_compliance
from core.logger import logger
from core.live_submit_state import is_live_submit_armed, LIVE_SUBMIT_REQUIRED_ACK
from repo_harvester.incorporation_engine import get_allowed_adapter_names
from autonomy.target_policy import (
    is_data_only_target,
    is_equity_index_target,
    is_prediction_quarantined_target,
)
from autonomy.fees import kalshi_maker_fee_cents, kalshi_taker_fee_cents
from forecasting.model_influence_attestation import (
    verify_model_influence_attestation,
)
from forecasting.model_probability_authority import ModelProbabilityAuthorityRegistry
from live_firewall.dumbmoney_capital import CapitalEnvelopeAdapter

REJECTED_ADAPTERS: set[str] = set()

LIVE_SUBMIT_PATH = Path("configs/live_submit.json")
ADAPTER_DESCRIPTOR_PATH = Path("runtime/operator_external/livebrokerfirewall_adapter_descriptor.json")
CAPS_PATH = Path("configs/caps.json")

def mark_adapter_rejected(adapter_name: str):
    REJECTED_ADAPTERS.add(adapter_name)


def market_is_allowlisted(market_ticker: Any, caps: Any) -> bool:
    """True when *market_ticker* is positively authorized by caps.

    Two independent grants, both deny-by-default:

    * ``allowed_markets`` -- exact ticker. Authorizes a fixed pilot only.
    * ``allowed_series``  -- the contract's series. Kalshi crypto contracts
      rotate every fifteen minutes and sports contracts rotate per game, so
      exact tickers cannot express continuous authorization.

    Series matching is BOUNDARY-AWARE string matching on an opaque identifier,
    never category inference: ``KXSOL15M`` must not authorize ``KXSOL15MEGA``.
    The firewall still refuses to read a category from a ticker -- category
    compliance comes from fetched venue metadata (see
    ``_verified_live_compliance_verdict``), which additionally re-checks the
    *verified* series before any transport.
    """
    if not isinstance(market_ticker, str) or not market_ticker:
        return False
    if market_ticker in (getattr(caps, "allowed_markets", None) or []):
        return True
    allowed_series = getattr(caps, "allowed_series", None) or []
    if not allowed_series:
        return False
    series = market_ticker.split("-", 1)[0]
    return series in allowed_series


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

def _credential_resolver_ready() -> bool:
    """Resolve and parse the actual signing key without exposing it."""
    if not _kalshi_credentials_ready():
        return False
    try:
        from kalshi.signer import load_private_key

        key = load_private_key()
    except Exception:
        return False
    return bool(os.environ.get("KALSHI_API_KEY_ID")) and callable(getattr(key, "sign", None))


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
    caps_authority = evaluate_caps_authority(caps_path=CAPS_PATH)
    return (
        limit_only
        and no_market
        and kill_on
        and order_count_ok
        and caps_authority.authority_registration_valid
    )


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


def live_execution_authority_status() -> dict[str, Any]:
    """Return the local, non-network live-authority verdict.

    Paper/shadow results are deliberately absent from this contract.  They are
    retained as research history, but they can neither open nor close the live
    submission boundary.  Authority comes only from the existing explicit
    one-proof config, operator/environment acknowledgement, command seal,
    protected caps registration, staged central-firewall descriptor, local
    credential resolution, and unused proof lock.
    """
    mode, blocker, context = classify_live_execution_mode(
        live_submit_config=_load_live_submit_config(),
        env=dict(os.environ),
        seal_status=(
            "PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT"
            if _command_seal_ready()
            else "BLOCKED"
        ),
        caps_strict=_caps_strict(),
        descriptor_staged=_descriptor_staged(),
        credentials_ready=_credential_resolver_ready(),
        proof_lock_clear=_proof_lock_clear(),
    )
    return {
        "state": mode.value,
        "execution_authority": (
            mode is LiveExecutionMode.OPERATOR_ONE_PROOF_LIVE_READY
        ),
        "blocker": blocker or None,
        "default_disabled": mode is LiveExecutionMode.DEFAULT_DISABLED,
        "proof_scope": "one_controlled_proof",
        "central_firewall_required": True,
        "limit_orders_only": True,
        "market_orders_allowed": False,
        "paper_results_authority": "RETIRED_NON_AUTHORITATIVE",
        "paper_results_can_enable_live": False,
        "paper_results_can_block_live": False,
        "checks": {
            "environment_mode": bool(context.get("env_mode")),
            "environment_ack": bool(context.get("env_ack")),
            "command_seal": context.get("seal_status"),
            "caps_strict": bool(context.get("caps_strict")),
            "descriptor_staged": bool(context.get("descriptor_staged")),
            "credentials_resolved_locally": bool(
                context.get("credentials_ready")
            ),
            "proof_lock_clear": bool(context.get("proof_lock_clear")),
        },
        "broker_contacted": False,
    }


@dataclass
class RehearsalVerdict:
    would_submit: bool
    firewall_verdict: FirewallVerdict
    order: Optional[dict[str, Any]]
    blocked_reason: Optional[str]


def _check_secret_redaction(text: str) -> bool:
    return not scan_text_for_risk(text)


class LiveBrokerFirewall:
    def __init__(
        self,
        kalshi_client,
        exposure_tracker: ExposureTracker,
        *,
        autonomy_risk_state_path: Path | None = None,
        require_autonomy_risk_state: bool = False,
        require_canary_readiness: bool = False,
        model_authority_registry: ModelProbabilityAuthorityRegistry | None = None,
        capital_envelope_adapter: CapitalEnvelopeAdapter | None = None,
        core_submission_authority: Callable[[], bool] | None = None,
    ):
        self.client = kalshi_client
        self.exposure = exposure_tracker
        self.require_autonomy_risk_state = bool(require_autonomy_risk_state)
        # Compatibility-only input.  Paper/shadow canary results were retired
        # as live authority and are intentionally ignored.
        self.require_canary_readiness = False
        self.model_authority_registry = (
            model_authority_registry or ModelProbabilityAuthorityRegistry()
        )
        # Additional deny-only DumbMoney bound. Absence preserves the
        # standalone Dummy authority model; presence makes a valid signed grant
        # mandatory without replacing any existing local gate.
        self.capital_envelope_adapter = capital_envelope_adapter
        if (
            core_submission_authority is not None
            and not callable(core_submission_authority)
        ):
            raise TypeError("core_submission_authority must be callable")
        self.core_submission_authority = core_submission_authority
        self.autonomy_risk_state_path = autonomy_risk_state_path or Path(
            os.environ.get(
                "DUMMY_AUTONOMY_LIVE_RISK_STATE_PATH",
                "runtime/autonomy/risk_state_live.json",
            )
        )

    def live_authority_verdict(self) -> FirewallVerdict:
        """Evaluate operator authority from real config, seal, and resolver state."""
        status = live_execution_authority_status()
        if status["execution_authority"]:
            return FirewallVerdict(allow=True, reason="Live authority gates passed")
        if status["default_disabled"]:
            return FirewallVerdict(
                allow=False,
                reason="live_submit_disabled",
                rejected_by="live_submit",
            )
        return FirewallVerdict(
            allow=False,
            reason=status.get("blocker") or "LIVE_AUTHORITY_BLOCKED",
            rejected_by="live_authority",
        )

    def _autonomy_risk_verdict(
        self,
        req: LiveOrderRequest,
        *,
        required: bool = False,
    ) -> FirewallVerdict:
        if not (required or self.require_autonomy_risk_state):
            return FirewallVerdict(allow=True, reason="Autonomy risk attestation not required")
        path = self.autonomy_risk_state_path
        try:
            payload = path.read_bytes()
            data = json.loads(payload.decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("risk state must be an object")
        except Exception:
            return FirewallVerdict(
                allow=False,
                reason="Persisted autonomy risk state unavailable",
                rejected_by="autonomy_risk_state",
            )
        digest = hashlib.sha256(payload).hexdigest().upper()
        if not req.risk_state_sha256 or req.risk_state_sha256.upper() != digest:
            return FirewallVerdict(
                allow=False,
                reason="Autonomy risk state attestation mismatch",
                rejected_by="autonomy_risk_state",
            )
        if int(data.get("accounting_version", 0)) < 2:
            return FirewallVerdict(
                allow=False,
                reason="Autonomy risk accounting version is stale",
                rejected_by="autonomy_risk_state",
            )
        try:
            saved_at = datetime.fromisoformat(str(data["saved_at"]).replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - saved_at).total_seconds()
        except Exception:
            age = 10_000.0
        if age < -5 or age > 300:
            return FirewallVerdict(
                allow=False,
                reason="Autonomy risk state is stale",
                rejected_by="autonomy_risk_state",
            )
        if bool(data.get("hard_stopped")) or int(data.get("stage", 0)) < 1:
            return FirewallVerdict(
                allow=False,
                reason="Autonomy risk state has no live authority",
                rejected_by="autonomy_risk_state",
            )
        for key in ("stage", "bankroll_cents", "open_exposure_cents", "open_markets"):
            try:
                matches = int(req.risk_snapshot[key]) == int(data[key])
            except Exception:
                matches = False
            if not matches:
                return FirewallVerdict(
                    allow=False,
                    reason=f"Autonomy risk snapshot mismatch: {key}",
                    rejected_by="autonomy_risk_state",
                )
        return FirewallVerdict(allow=True, reason="Persisted autonomy risk state verified")

    def _canary_readiness_verdict(self, *, required: bool = False) -> FirewallVerdict:
        """Compatibility verdict for the retired paper/shadow evidence gate.

        This method deliberately does not read a backtest or paper ledger.
        Keeping the shim avoids breaking older callers while making it
        impossible for either positive or negative paper results to affect a
        live decision.
        """
        return FirewallVerdict(
            allow=True,
            reason="Paper/shadow results retired and non-authoritative",
        )

    @staticmethod
    def _side_book_ladders(
        req: LiveOrderRequest,
        orderbook: OrderBook,
    ) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
        """Return bid/ask depth in the requested YES-or-NO price frame."""
        if req.side == "yes":
            bids = [(int(level.price), int(level.size)) for level in orderbook.bids]
            asks = [(int(level.price), int(level.size)) for level in orderbook.asks]
        else:
            bids = [(100 - int(level.price), int(level.size)) for level in orderbook.asks]
            asks = [(100 - int(level.price), int(level.size)) for level in orderbook.bids]
        return (
            sorted(bids, key=lambda item: item[0], reverse=True),
            sorted(asks, key=lambda item: item[0]),
        )

    async def _trusted_sink_orderbook(
        self,
        req: LiveOrderRequest,
    ) -> tuple[OrderBook | None, FirewallVerdict]:
        """Take a final, sink-owned full-depth snapshot.

        Caller-provided books may reject a request, but can never authorize a
        real order. The central sink re-reads and binds the exact Kalshi ticker
        immediately before it reserves exposure and contacts the write API.
        """
        if self.client is None:
            return None, FirewallVerdict(
                allow=False,
                reason="Fresh broker orderbook unavailable",
                rejected_by="trusted_orderbook",
            )
        get_orderbook = getattr(self.client, "get_orderbook", None)
        if not callable(get_orderbook):
            return None, FirewallVerdict(
                allow=False,
                reason="Fresh broker orderbook unavailable",
                rejected_by="trusted_orderbook",
            )
        if req.market_ticker.strip().casefold() != req.contract_ticker.strip().casefold():
            return None, FirewallVerdict(
                allow=False,
                reason="Kalshi market and contract ticker binding mismatch",
                rejected_by="context_integrity",
            )
        try:
            book = await get_orderbook(req.contract_ticker, depth=100)
        except Exception as exc:
            logger.info(
                "Fresh broker orderbook unavailable",
                extra={
                    "component": "firewall",
                    "error_type": type(exc).__name__,
                    "proposal_id": req.proposal_id,
                },
            )
            return None, FirewallVerdict(
                allow=False,
                reason="Fresh broker orderbook unavailable",
                rejected_by="trusted_orderbook",
            )
        if not isinstance(book, OrderBook):
            return None, FirewallVerdict(
                allow=False,
                reason="Fresh broker orderbook has invalid schema",
                rejected_by="trusted_orderbook",
            )
        expected = req.contract_ticker.strip().casefold()
        if (
            book.market_ticker.strip().casefold() != expected
            or book.contract_ticker.strip().casefold() != expected
        ):
            return None, FirewallVerdict(
                allow=False,
                reason="Fresh broker orderbook identity mismatch",
                rejected_by="context_integrity",
            )
        # The central await completion is itself a local receipt witness. Never
        # overwrite a venue source timestamp; preserve both evidence clocks.
        if book.received_at is None:
            book = book.model_copy(
                update={"received_at": datetime.now(timezone.utc)}
            )
        return book, FirewallVerdict(
            allow=True,
            reason="Fresh sink-owned broker depth verified",
        )

    def _mandatory_submit_authority(
        self,
        req: LiveOrderRequest,
        *,
        reservation_held: bool = False,
        trusted_orderbook: OrderBook | None = None,
        forecast: Forecast | None = None,
    ) -> FirewallVerdict:
        """Recheck every non-optional real-submit authority gate."""
        now = datetime.now(timezone.utc)
        if (
            req.expiration_ts is not None
            and req.expiration_ts <= int(now.timestamp())
        ):
            return FirewallVerdict(
                allow=False,
                reason="Limit order expiry is not in the future",
                rejected_by="order_expiry",
            )
        if (
            self.capital_envelope_adapter is not None
            and req.liquidity_role == "maker"
            and req.expiration_ts is None
        ):
            return FirewallVerdict(
                allow=False,
                reason="Maker order lacks exchange-enforced expiration",
                rejected_by="order_expiry",
            )
        if self.capital_envelope_adapter is not None:
            if self.core_submission_authority is None:
                return FirewallVerdict(
                    allow=False,
                    reason="Current DumbMoney Core control authority is required",
                    rejected_by="core_command_authority",
                )
            try:
                core_allows = self.core_submission_authority()
            except Exception:
                core_allows = False
            if core_allows is not True:
                return FirewallVerdict(
                    allow=False,
                    reason="DumbMoney Core control authority is not current",
                    rejected_by="core_command_authority",
                )
            if not STATE.refresh_persisted_state():
                return FirewallVerdict(
                    allow=False,
                    reason="Persisted risk/safety state unavailable",
                    rejected_by="risk_state",
                )
            if STATE.kill_switch.active:
                return FirewallVerdict(
                    allow=False,
                    reason="Kill switch active",
                    rejected_by="kill_switch",
                )
            if STATE.emergency_stop.active:
                return FirewallVerdict(
                    allow=False,
                    reason="Emergency stop active",
                    rejected_by="emergency_stop",
                )
            if STATE.persistence_error or not STATE.verify_persistence():
                return FirewallVerdict(
                    allow=False,
                    reason="Persisted daily-loss state unavailable",
                    rejected_by="daily_loss_state",
                )
            if (
                not self.exposure.state_healthy
                or not self.exposure.verify_persistence()
            ):
                return FirewallVerdict(
                    allow=False,
                    reason="Persisted exposure state unavailable",
                    rejected_by="exposure_state",
                )
            caps = load_caps()
            if STATE.daily_loss_cents >= caps.max_daily_loss_cents:
                return FirewallVerdict(
                    allow=False,
                    reason="Daily loss cap exceeded",
                    rejected_by="daily_loss_cap",
                )
            if reservation_held:
                order_value = req.price_cents * req.size
                if order_value > caps.max_single_order_cents:
                    return FirewallVerdict(
                        allow=False,
                        reason="Single order cap exceeded after reservation",
                        rejected_by="single_order_cap",
                    )
                if (
                    self.exposure.market_exposure_cents(
                        req.market_ticker
                    )
                    > caps.max_market_exposure_cents
                ):
                    return FirewallVerdict(
                        allow=False,
                        reason="Market exposure cap exceeded after reservation",
                        rejected_by="market_exposure_cap",
                    )
                if (
                    self.exposure.total_exposure_cents()
                    > caps.max_total_live_exposure_cents
                ):
                    return FirewallVerdict(
                        allow=False,
                        reason="Total exposure cap exceeded after reservation",
                        rejected_by="total_exposure_cap",
                    )
                if (
                    self.exposure.correlated_exposure_cents(
                        req.market_ticker
                    )
                    > caps.max_correlated_exposure_cents
                ):
                    return FirewallVerdict(
                        allow=False,
                        reason=(
                            "Correlated exposure cap exceeded after reservation"
                        ),
                        rejected_by="correlated_exposure_cap",
                    )
                if self.exposure.open_markets() > caps.max_open_markets:
                    return FirewallVerdict(
                        allow=False,
                        reason="Max open markets exceeded after reservation",
                        rejected_by="open_markets",
                    )
                if (
                    self.exposure.orders_last_hour()
                    > caps.max_orders_per_hour
                ):
                    return FirewallVerdict(
                        allow=False,
                        reason="Order frequency cap exceeded after reservation",
                        rejected_by="frequency_cap",
                    )
                if (
                    self.exposure.open_order_count()
                    > caps.max_orders_per_hour
                ):
                    return FirewallVerdict(
                        allow=False,
                        reason=(
                            "Open order count exceeded after reservation"
                        ),
                        rejected_by="open_order_cap",
                    )
        if trusted_orderbook is not None:
            freshness_clocks = [trusted_orderbook.timestamp]
            if trusted_orderbook.received_at is not None:
                freshness_clocks.append(trusted_orderbook.received_at)
            if trusted_orderbook.source_ts is not None:
                freshness_clocks.append(trusted_orderbook.source_ts)
            if any(
                stamp.tzinfo is None
                or stamp < now - timedelta(seconds=30)
                or stamp > now + timedelta(seconds=5)
                for stamp in freshness_clocks
            ):
                return FirewallVerdict(
                    allow=False,
                    reason="Trusted broker depth expired before submission",
                    rejected_by="stale_data",
                )
            caps = load_caps()
            if not market_is_allowlisted(req.market_ticker, caps):
                return FirewallVerdict(
                    allow=False,
                    reason="Market not allowlisted at final submit",
                    rejected_by="market_allowlist",
                )
            if (
                req.side not in {"yes", "no"}
                or req.size < 1
                or not 1 <= req.price_cents <= 99
            ):
                return FirewallVerdict(
                    allow=False,
                    reason="Invalid final limit-order schema",
                    rejected_by="order_schema",
                )
            if (
                trusted_orderbook.market_ticker != req.market_ticker
                or trusted_orderbook.contract_ticker != req.contract_ticker
                or not trusted_orderbook.bids
                or not trusted_orderbook.asks
                or any(
                    level.size <= 0 or not 1 <= level.price <= 99
                    for level in (
                        trusted_orderbook.bids + trusted_orderbook.asks
                    )
                )
            ):
                return FirewallVerdict(
                    allow=False,
                    reason="Trusted broker depth failed final schema binding",
                    rejected_by="context_integrity",
                )
            side_bids, side_asks = self._side_book_ladders(
                req,
                trusted_orderbook,
            )
            if not side_bids or not side_asks:
                return FirewallVerdict(
                    allow=False,
                    reason="Trusted side-specific depth is unavailable",
                    rejected_by="liquidity",
                )
            best_bid = side_bids[0][0]
            best_ask = side_asks[0][0]
            spread = best_ask - best_bid
            total_liquidity = sum(
                level.size
                for level in (
                    trusted_orderbook.bids + trusted_orderbook.asks
                )
            )
            if spread <= 0 or spread > caps.max_spread_cents:
                return FirewallVerdict(
                    allow=False,
                    reason="Trusted spread violates current policy",
                    rejected_by="spread",
                )
            if total_liquidity < caps.min_liquidity:
                return FirewallVerdict(
                    allow=False,
                    reason="Trusted liquidity violates current policy",
                    rejected_by="liquidity",
                )
            if req.liquidity_role == "maker":
                if not best_bid <= req.price_cents < best_ask:
                    return FirewallVerdict(
                        allow=False,
                        reason="Maker order is not passive at final submit",
                        rejected_by="execution_role",
                    )
            else:
                executable_size = sum(
                    size
                    for price, size in side_asks
                    if price <= req.price_cents
                )
                if (
                    req.price_cents < best_ask
                    or executable_size < req.size
                ):
                    return FirewallVerdict(
                        allow=False,
                        reason="Final taker depth cannot execute the request",
                        rejected_by="executable_depth",
                    )
            if forecast is not None:
                if (
                    forecast.market_ticker != req.market_ticker
                    or forecast.contract_ticker != req.contract_ticker
                    or forecast.proof_reference
                    != req.forecast_proof_reference
                ):
                    return FirewallVerdict(
                        allow=False,
                        reason="Forecast identity changed before final submit",
                        rejected_by="context_integrity",
                    )
                net_ev = self._net_ev_verdict(req, forecast, caps)
                if not net_ev.allow:
                    return net_ev
                if forecast.settlement_risk_score > Decimal("0.8"):
                    return FirewallVerdict(
                        allow=False,
                        reason="Settlement risk too high at final submit",
                        rejected_by="settlement_risk",
                    )
                model_influence = self._model_influence_verdict(
                    req,
                    forecast,
                )
                if not model_influence.allow:
                    return model_influence
        risk_verdict = self._autonomy_risk_verdict(req, required=True)
        if not risk_verdict.allow:
            return risk_verdict
        capital_verdict = self._capital_envelope_verdict(
            req,
            reservation_held=reservation_held,
        )
        if not capital_verdict.allow:
            return capital_verdict
        return self.live_authority_verdict()

    def _capital_envelope_verdict(
        self,
        req: LiveOrderRequest,
        *,
        reservation_held: bool = False,
    ) -> FirewallVerdict:
        """Revalidate the optional signed external ceiling.

        The adapter can only reject or further reduce locally permitted risk.
        It is deliberately evaluated after Dummy's own caps in ``evaluate``;
        the central sink also calls it from mandatory authority checks so a
        replaced preflight cannot bypass it.
        """
        fields_present = any(
            value is not None
            for value in (
                req.capital_envelope_id,
                req.capital_strategy_hash,
                req.capital_passport_hash,
                req.capital_promotion_hash,
                req.capital_fencing_generation,
            )
        )
        if self.capital_envelope_adapter is None:
            if fields_present:
                return FirewallVerdict(
                    allow=False,
                    reason="DumbMoney capital adapter unavailable",
                    rejected_by="capital_adapter",
                )
            return FirewallVerdict(
                allow=True,
                reason="Standalone Dummy authority; no external capital adapter",
            )
        if not all(
            value is not None
            for value in (
                req.capital_envelope_id,
                req.capital_strategy_hash,
                req.capital_passport_hash,
                req.capital_promotion_hash,
                req.capital_fencing_generation,
            )
        ):
            return FirewallVerdict(
                allow=False,
                reason="Signed DumbMoney capital binding is incomplete",
                rejected_by="capital_envelope",
            )
        try:
            verdict = self.capital_envelope_adapter.evaluate_request(
                req,
                current_daily_loss_cents=max(0, int(STATE.daily_loss_cents)),
                current_local_total_exposure_cents=(
                    self.exposure.total_exposure_cents()
                ),
                current_local_correlated_exposure_cents=(
                    self.exposure.correlated_exposure_cents(
                        req.market_ticker
                    )
                ),
                current_local_open_orders=self.exposure.open_order_count(),
                current_request_locally_reserved=reservation_held,
            )
        except Exception as exc:
            return FirewallVerdict(
                allow=False,
                reason=f"DumbMoney capital state unavailable:{type(exc).__name__}",
                rejected_by="capital_envelope",
            )
        return FirewallVerdict(
            allow=verdict.allow,
            reason=verdict.reason,
            rejected_by=verdict.rejected_by,
        )

    def _model_influence_verdict(
        self,
        req: LiveOrderRequest,
        forecast: Forecast,
    ) -> FirewallVerdict:
        """Verify forecast/proposal binding and fresh exact model authority."""
        result = verify_model_influence_attestation(
            req,
            forecast,
            authority_registry=self.model_authority_registry,
        )
        if result.valid:
            return FirewallVerdict(allow=True, reason=result.reason)
        return FirewallVerdict(
            allow=False,
            reason=result.reason,
            rejected_by="model_influence_authority",
        )

    @staticmethod
    def _net_ev_verdict(
        req: LiveOrderRequest,
        forecast: Forecast,
        caps: Any,
    ) -> FirewallVerdict:
        """Recompute conservative, side-specific EV at the final limit.

        Upstream forecast fields are claims, not authority.  The central
        firewall independently binds probability uncertainty, side, limit
        price, current fee schedule, and operator minimum edge.  It may reject
        an upstream decision but can never increase its size or edge.
        """
        try:
            point = Decimal(forecast.dummy_probability)
            lower = Decimal(forecast.uncertainty_band[0])
            upper = Decimal(forecast.uncertainty_band[1])
            claimed_gross = Decimal(forecast.expected_edge)
            claimed_net = Decimal(forecast.edge_after_fees)
        except (ArithmeticError, TypeError, ValueError, IndexError):
            return FirewallVerdict(
                allow=False,
                reason="Forecast edge evidence is malformed",
                rejected_by="net_ev",
            )
        values = (point, lower, upper, claimed_gross, claimed_net)
        if (
            any(not value.is_finite() for value in values)
            or not Decimal(0) <= lower <= point <= upper <= Decimal(1)
            or claimed_gross <= 0
            or claimed_net <= 0
        ):
            return FirewallVerdict(
                allow=False,
                reason="Forecast edge evidence is invalid or non-positive",
                rejected_by="net_ev",
            )

        # Match the allocator's documented half-sigma confidence haircut:
        # halfway from the point estimate to the adverse uncertainty bound.
        probability_side = (
            (point + lower) / Decimal(2)
            if req.side == "yes"
            else Decimal(1) - (point + upper) / Decimal(2)
        )
        fee_total = (
            kalshi_maker_fee_cents(
                req.price_cents,
                req.size,
                req.market_ticker,
            )
            if req.liquidity_role == "maker"
            else kalshi_taker_fee_cents(
                req.price_cents,
                req.size,
                req.market_ticker,
            )
        )
        fee_per_contract = Decimal(fee_total) / Decimal(req.size)
        net_ev_cents = (
            probability_side * Decimal(100)
            - Decimal(req.price_cents)
            - fee_per_contract
        )
        minimum_cents = Decimal(int(caps.min_edge_bps)) / Decimal(100)
        minimum_probability_edge = (
            Decimal(int(caps.min_edge_bps)) / Decimal(10000)
        )
        if claimed_gross < minimum_probability_edge:
            return FirewallVerdict(
                allow=False,
                reason="Expected edge below threshold",
                rejected_by="net_ev",
            )
        if net_ev_cents <= 0:
            return FirewallVerdict(
                allow=False,
                reason="Conservative side-specific net EV is non-positive",
                rejected_by="net_ev",
            )
        if net_ev_cents < minimum_cents:
            return FirewallVerdict(
                allow=False,
                reason="Conservative side-specific net EV is below threshold",
                rejected_by="net_ev",
            )
        # The claim may be more conservative than the recomputation, never more
        # optimistic. One hundredth of a cent absorbs serialized rounding.
        if claimed_net * Decimal(100) > net_ev_cents + Decimal("0.01"):
            return FirewallVerdict(
                allow=False,
                reason="Claimed edge after fees exceeds firewall recomputation",
                rejected_by="net_ev_binding",
            )
        return FirewallVerdict(
            allow=True,
            reason="Conservative side-specific net EV verified",
        )

    async def evaluate(self, req: LiveOrderRequest, orderbook: OrderBook, forecast: Forecast) -> FirewallVerdict:
        caps = load_caps()
        def fail(by: str, reason: str) -> FirewallVerdict:
            logger.info("Firewall rejection", extra={"component": "firewall", "rejected_by": by, "reason": reason, "proposal_id": req.proposal_id})
            return FirewallVerdict(allow=False, reason=reason, rejected_by=by)

        if STATE.mode != AccountMode.AUTONOMOUS_LIVE_CAPPED:
            return fail("mode", "Mode is not AUTONOMOUS_LIVE_CAPPED")
        if is_data_only_target(req.market_ticker):
            return fail(
                "data_only_target",
                "Weather and commodity contracts are contextual data only",
            )
        # Use only the request ticker at this preflight boundary.  The optional
        # model-influence category is caller-authored and cannot grant or deny
        # target authority.  Structured category policy is re-evaluated later
        # from independently fetched Kalshi hierarchy metadata.
        if is_equity_index_target(req.market_ticker) or is_equity_index_target(
            req.contract_ticker
        ):
            return fail(
                "equity_index_target_quarantine",
                "Target is outside Dummy's supported prediction surface",
            )
        if not STATE.refresh_persisted_state():
            return fail("risk_state", "Persisted risk/safety state unavailable")
        if STATE.kill_switch.active:
            return fail("kill_switch", "Kill switch active")
        if STATE.emergency_stop.active:
            return fail("emergency_stop", "Emergency stop active")
        if STATE.persistence_error or not STATE.verify_persistence():
            return fail("daily_loss_state", "Persisted daily-loss state unavailable")
        if not self.exposure.state_healthy or not self.exposure.verify_persistence():
            return fail("exposure_state", "Persisted exposure state unavailable")
        if req.market_ticker != orderbook.market_ticker or req.contract_ticker != orderbook.contract_ticker:
            return fail("context_integrity", "Orderbook identity does not match request")
        if req.market_ticker != forecast.market_ticker or req.contract_ticker != forecast.contract_ticker:
            return fail("context_integrity", "Forecast identity does not match request")
        risk_verdict = self._autonomy_risk_verdict(req)
        if not risk_verdict.allow:
            return risk_verdict
        if req.side not in ("yes", "no") or not (1 <= req.price_cents <= 99) or req.size < 1:
            return fail("order_schema", "Invalid limit order side, price, or size")
        if req.expiration_ts is not None and req.expiration_ts <= int(datetime.now(timezone.utc).timestamp()):
            return fail("order_expiry", "Limit order expiry is not in the future")
        if (
            self.capital_envelope_adapter is not None
            and req.liquidity_role == "maker"
            and req.expiration_ts is None
        ):
            return fail(
                "order_expiry",
                "Maker order lacks exchange-enforced expiration",
            )
        if not os.environ.get("KALSHI_API_KEY_ID"):
            return fail("secrets", "API key missing")
        allowed = get_allowed_adapter_names()
        if req.adapter_name in REJECTED_ADAPTERS:
            return fail("repo_bypass", "Adapter rejected by repo harvester")
        if req.adapter_name not in allowed:
            return fail("unknown_adapter", f"Unknown or untested adapter {req.adapter_name}")
        if not _check_secret_redaction(str(req.model_dump())):
            return fail("secret_redaction", "Secret redaction check failed")
        if req.forecast_proof_reference != forecast.proof_reference:
            return fail("proof", "Forecast proof reference mismatch")
        if not market_is_allowlisted(req.market_ticker, caps):
            return fail("market_allowlist", "Market not allowlisted")
        # Kalshi tickers are opaque identifiers, never category metadata.
        # Category compliance is intentionally deferred to the independently
        # fetched market/event/series hierarchy in the live rehearsal/submit
        # sink; evaluate performs no semantic inference from ticker strings.
        now = datetime.now(timezone.utc)
        freshness_clocks = [orderbook.timestamp]
        if orderbook.received_at is not None:
            freshness_clocks.append(orderbook.received_at)
        if orderbook.source_ts is not None:
            freshness_clocks.append(orderbook.source_ts)
        if any(
            stamp.tzinfo is None
            or stamp < now - timedelta(seconds=30)
            or stamp > now + timedelta(seconds=5)
            for stamp in freshness_clocks
        ):
            return fail("stale_data", "Stale market data")
        if not orderbook.bids or not orderbook.asks:
            return fail("liquidity", "Missing orderbook data")
        if any(level.size <= 0 or not (1 <= level.price <= 99) for level in orderbook.bids + orderbook.asks):
            return fail("liquidity", "Invalid orderbook level")
        side_bids, side_asks = self._side_book_ladders(req, orderbook)
        if not side_bids or not side_asks:
            return fail("liquidity", "Missing side-specific orderbook data")
        best_bid = side_bids[0][0]
        best_ask = side_asks[0][0]
        spread = best_ask - best_bid
        if spread <= 0:
            return fail("spread", "Crossed or invalid orderbook")
        if spread > caps.max_spread_cents:
            return fail("spread", "Spread too wide")
        total_liquidity = sum(level.size for level in orderbook.bids) + sum(
            level.size for level in orderbook.asks
        )
        if total_liquidity < caps.min_liquidity:
            return fail("liquidity", "Liquidity too low")
        if req.liquidity_role == "maker":
            if req.price_cents >= best_ask:
                return fail(
                    "execution_role",
                    "Passive maker limit became marketable on fresh depth",
                )
            if req.price_cents < best_bid:
                return fail(
                    "execution_role",
                    "Passive maker limit is behind the current best bid",
                )
        else:
            executable_size = sum(
                size for price, size in side_asks if price <= req.price_cents
            )
            if req.price_cents < best_ask or executable_size < req.size:
                return fail(
                    "executable_depth",
                    "Fresh side-specific depth cannot execute the taker request",
                )
        net_ev_verdict = self._net_ev_verdict(req, forecast, caps)
        if not net_ev_verdict.allow:
            return fail(
                net_ev_verdict.rejected_by or "net_ev",
                net_ev_verdict.reason,
            )
        if not req.strategy_proof_reference or not req.forecast_proof_reference:
            return fail("proof", "Missing proof reference")
        order_value = req.price_cents * req.size
        if order_value > caps.max_single_order_cents:
            return fail("single_order_cap", "Single order cap exceeded")
        if self.exposure.market_exposure_cents(req.market_ticker) + order_value > caps.max_market_exposure_cents:
            return fail("market_exposure_cap", "Market exposure cap exceeded")
        if self.exposure.total_exposure_cents() + order_value > caps.max_total_live_exposure_cents:
            return fail("total_exposure_cap", "Total exposure cap exceeded")
        if self.exposure.correlated_exposure_cents(req.market_ticker) + order_value > caps.max_correlated_exposure_cents:
            return fail("correlated_exposure_cap", "Correlated exposure cap exceeded")
        if STATE.daily_loss_cents >= caps.max_daily_loss_cents:
            return fail("daily_loss_cap", "Daily loss cap exceeded")
        if self.exposure.open_markets() >= caps.max_open_markets:
            return fail("open_markets", "Max open markets exceeded")
        if self.exposure.orders_last_hour() >= caps.max_orders_per_hour:
            return fail("frequency_cap", "Order frequency cap exceeded")
        if self.exposure.open_order_count() >= caps.max_orders_per_hour:
            return fail("open_order_cap", "Open order count exceeded")
        # External capital grants are additional ceilings only. Dummy's local
        # cap, exposure, loss, frequency, and order-count checks above always
        # run first and can never be widened by the grant.
        capital_verdict = self._capital_envelope_verdict(req)
        if not capital_verdict.allow:
            return fail(
                capital_verdict.rejected_by or "capital_envelope",
                capital_verdict.reason,
            )
        if forecast.settlement_risk_score > Decimal("0.8"):
            return fail("settlement_risk", "Settlement risk too high")
        model_influence_verdict = self._model_influence_verdict(req, forecast)
        if not model_influence_verdict.allow:
            return model_influence_verdict

        return FirewallVerdict(allow=True, reason="All gates passed")

    REQUIRED_ACKNOWLEDGEMENT = LIVE_SUBMIT_REQUIRED_ACK

    def _live_submit_enabled(self) -> bool:
        """Read the operator-approved live-submit flag.

        Returns True only if configs/live_submit.json is in the valid
        operator-approved one-proof enabled state per the shared state model.
        """
        return is_live_submit_armed()

    def _build_order(self, req: LiveOrderRequest) -> dict[str, Any]:
        # Create Order V2 uses one YES-denominated book. Buying NO is an ask
        # at the complementary YES price. Fixed-point strings are constructed
        # without binary floating-point conversion.
        yes_price_cents = (
            req.price_cents if req.side == "yes" else 100 - req.price_cents
        )
        maker = req.liquidity_role == "maker"
        order: dict[str, Any] = {
            "ticker": req.contract_ticker,
            "client_order_id": req.proposal_id,
            "side": "bid" if req.side == "yes" else "ask",
            "count": f"{req.size}.00",
            "price": f"0.{yes_price_cents:02d}00",
            "time_in_force": (
                "good_till_canceled" if maker else "fill_or_kill"
            ),
            "self_trade_prevention_type": "taker_at_cross",
            "post_only": maker,
            "cancel_order_on_pause": True,
            "reduce_only": False,
            "subaccount": 0,
            "exchange_index": 0,
        }
        if maker and req.expiration_ts is not None:
            order["expiration_time"] = req.expiration_ts
        return order

    @staticmethod
    def _validate_v2_create_response(
        response: Any,
        *,
        request: LiveOrderRequest,
    ) -> str:
        """Validate the current Create Order V2 acknowledgement shape."""
        if not isinstance(response, Mapping):
            raise ValueError("Create Order V2 response is not an object")
        required = {"order_id", "fill_count", "remaining_count", "ts_ms"}
        allowed = required | {
            "client_order_id",
            "average_fill_price",
            "average_fee_paid",
        }
        if not required <= set(response) <= allowed:
            raise ValueError("Create Order V2 response fields mismatch")
        order_id = response["order_id"]
        if not isinstance(order_id, str) or not order_id.strip():
            raise ValueError("Create Order V2 order_id is invalid")
        client_order_id = response.get("client_order_id")
        if (
            client_order_id is not None
            and client_order_id != request.proposal_id
        ):
            raise ValueError(
                "Create Order V2 client_order_id differs from proposal"
            )
        try:
            fill_count = Decimal(response["fill_count"])
            remaining_count = Decimal(response["remaining_count"])
        except Exception as exc:
            raise ValueError(
                "Create Order V2 counts are not fixed-point values"
            ) from exc
        if (
            not isinstance(response["fill_count"], str)
            or not isinstance(response["remaining_count"], str)
            or not fill_count.is_finite()
            or not remaining_count.is_finite()
            or fill_count < 0
            or remaining_count < 0
            or fill_count != fill_count.to_integral_value()
            or remaining_count != remaining_count.to_integral_value()
            or fill_count + remaining_count > Decimal(request.size)
        ):
            raise ValueError("Create Order V2 counts are invalid")
        ts_ms = response["ts_ms"]
        if (
            isinstance(ts_ms, bool)
            or not isinstance(ts_ms, int)
            or ts_ms < 1
        ):
            raise ValueError("Create Order V2 ts_ms is invalid")
        # Any immediate fill or canceled remainder needs broker reconciliation
        # before local open-order state can be finalized.
        if fill_count != 0 or remaining_count != Decimal(request.size):
            raise ValueError(
                "Create Order V2 acknowledgement requires fill reconciliation"
            )
        return order_id.strip()

    async def _verified_live_compliance_verdict(
        self,
        req: LiveOrderRequest,
    ) -> FirewallVerdict:
        """Resolve trusted Kalshi hierarchy metadata at the live sink."""
        if self.client is None:
            return FirewallVerdict(
                allow=False,
                reason="Verified Kalshi compliance metadata unavailable",
                rejected_by="compliance_metadata",
            )
        try:
            from compliance.kalshi_metadata import (
                fetch_verified_kalshi_compliance_metadata,
            )

            market_raw = await self.client.get_market(req.market_ticker)
            if not isinstance(market_raw, Mapping):
                raise ValueError("market response is not an object")
            nested = market_raw.get("market")
            market = nested if nested is not None else market_raw
            if not isinstance(market, Mapping):
                raise ValueError("market envelope is not an object")
            actual_ticker = str(market.get("ticker") or "").strip()
            if (
                not actual_ticker
                or actual_ticker.casefold() != req.market_ticker.strip().casefold()
                or actual_ticker.casefold() != req.contract_ticker.strip().casefold()
            ):
                return FirewallVerdict(
                    allow=False,
                    reason="Verified Kalshi market identity mismatch",
                    rejected_by="context_integrity",
                )
            status = str(market.get("status") or "").strip().casefold()
            if status not in {"active", "open"}:
                return FirewallVerdict(
                    allow=False,
                    reason="Verified Kalshi market is not open",
                    rejected_by="market_state",
                )
            expiry_values: list[tuple[str, datetime]] = []
            for field in (
                "close_time",
                "expiration_time",
                "expected_expiration_time",
                "latest_expiration_time",
            ):
                raw_value = market.get(field)
                if raw_value in (None, ""):
                    continue
                parsed = datetime.fromisoformat(
                    str(raw_value).replace("Z", "+00:00")
                )
                if parsed.tzinfo is None:
                    raise ValueError(f"{field} is not timezone-aware")
                expiry_values.append((field, parsed.astimezone(timezone.utc)))
            if not expiry_values:
                return FirewallVerdict(
                    allow=False,
                    reason="Verified Kalshi close/expiration time unavailable",
                    rejected_by="market_state",
                )
            now = datetime.now(timezone.utc)
            if any(value <= now for _field, value in expiry_values):
                return FirewallVerdict(
                    allow=False,
                    reason="Verified Kalshi market close/expiration has passed",
                    rejected_by="market_state",
                )
            earliest_expiry = min(value for _field, value in expiry_values)
            if (
                req.expiration_ts is not None
                and datetime.fromtimestamp(req.expiration_ts, timezone.utc)
                > earliest_expiry
            ):
                return FirewallVerdict(
                    allow=False,
                    reason="Order expiration exceeds verified market close",
                    rejected_by="order_expiry",
                )
            metadata = await fetch_verified_kalshi_compliance_metadata(
                self.client,
                req.market_ticker,
                market_raw=market_raw,
            )
        except Exception as exc:
            logger.info(
                "Verified compliance metadata unavailable",
                extra={
                    "component": "firewall",
                    "error_type": type(exc).__name__,
                    "proposal_id": req.proposal_id,
                },
            )
            return FirewallVerdict(
                allow=False,
                reason="Verified Kalshi compliance metadata unavailable",
                rejected_by="compliance_metadata",
            )
        # This category is venue hierarchy evidence bound to the exact market,
        # event, and series.  Never substitute the request/model attestation's
        # self-declared category or other private metadata here.
        if is_prediction_quarantined_target(
            req.market_ticker,
            category=metadata.series_category,
            series_tags=metadata.series_tags,
        ) or is_prediction_quarantined_target(
            req.contract_ticker,
            category=metadata.event_category or metadata.series_category,
            series_tags=metadata.series_tags,
        ) or is_prediction_quarantined_target(
            metadata.series_ticker,
            category=metadata.series_category,
            series_tags=metadata.series_tags,
        ):
            return FirewallVerdict(
                allow=False,
                reason=(
                    "Verified Kalshi target category has zero prediction and "
                    "execution authority"
                ),
                rejected_by="prediction_target_quarantine",
            )
        # NO allowlist check here, deliberately. This function answers "is this
        # verified category permitted?"; the allowlist answers "is this market
        # in operator scope?". An earlier revision checked the allowlist here
        # and it fired FIRST, masking category rejections -- a Politics market
        # came back as "not allowlisted" instead of quarantined, and callers
        # testing category logic failed for authorization reasons. Scope is
        # enforced by market_is_allowlisted() in evaluate(), which submit()
        # runs twice, the second time against the trusted orderbook.
        compliance = assess_compliance(
            req.market_ticker,
            req.contract_ticker,
            caps=load_caps(),
            metadata=metadata,
            require_verified_metadata=True,
        )
        if not compliance.passed:
            return FirewallVerdict(
                allow=False,
                reason=compliance.reason,
                rejected_by="compliance",
            )
        return FirewallVerdict(
            allow=True,
            reason="Verified Kalshi hierarchy metadata compliant",
        )

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
        # Resolve the exact venue hierarchy before constructing any would-be
        # order.  A rehearsal is evidence consumed by operators and tests; it
        # must not return an order-shaped object for a quarantined or otherwise
        # unverified target, even when ``evaluate`` is replaced by a test double.
        compliance = await self._verified_live_compliance_verdict(req)
        if not compliance.allow:
            return RehearsalVerdict(
                would_submit=False,
                firewall_verdict=compliance,
                order=None,
                blocked_reason=compliance.reason,
            )
        order = self._build_order(req)
        authority = self.live_authority_verdict()
        if not authority.allow:
            return RehearsalVerdict(
                would_submit=False,
                firewall_verdict=verdict,
                order=order,
                blocked_reason=authority.reason,
            )
        return RehearsalVerdict(
            would_submit=True,
            firewall_verdict=verdict,
            order=order,
            blocked_reason=None,
        )

    async def submit(self, req: LiveOrderRequest, orderbook: OrderBook, forecast: Forecast) -> LiveOrderResult:
        # Sink-owned deny gate: retain protection even if a legacy test/dry-run
        # caller replaces ``evaluate``.  This happens before authority checks,
        # authenticated reads, exposure reservation, or broker transport.
        if is_prediction_quarantined_target(
            req.market_ticker
        ) or is_prediction_quarantined_target(req.contract_ticker):
            return LiveOrderResult(
                success=False,
                error="prediction_target_quarantine",
                proof_reference=req.strategy_proof_reference,
                broker_contacted=False,
            )
        verdict = await self.evaluate(req, orderbook, forecast)
        if not verdict.allow:
            return LiveOrderResult(success=False, error=verdict.reason, proof_reference=req.strategy_proof_reference)
        # Real submission never inherits relaxed evaluate/rehearsal defaults.
        # Check before authenticated reads, then check again after them so an
        # expiring authority/risk state cannot win a time-of-check race.
        authority = self._mandatory_submit_authority(
            req,
            forecast=forecast,
        )
        if not authority.allow:
            logger.info(
                "Live submit blocked by authority",
                extra={
                    "component": "firewall",
                    "proposal_id": req.proposal_id,
                    "rejected_by": authority.rejected_by,
                    "reason": authority.reason,
                },
            )
            return LiveOrderResult(success=False, error=authority.reason, proof_reference=req.strategy_proof_reference)
        if req.side not in ("yes", "no"):
            return LiveOrderResult(success=False, error="Invalid side", proof_reference=req.strategy_proof_reference)
        if self.client is None or not callable(getattr(self.client, "create_order", None)):
            return LiveOrderResult(success=False, error="broker_client_unavailable", proof_reference=req.strategy_proof_reference)
        compliance = await self._verified_live_compliance_verdict(req)
        if not compliance.allow:
            return LiveOrderResult(
                success=False,
                error=compliance.reason,
                proof_reference=req.strategy_proof_reference,
                broker_contacted=False,
            )
        trusted_orderbook, trusted_book_verdict = await self._trusted_sink_orderbook(req)
        if not trusted_book_verdict.allow or trusted_orderbook is None:
            return LiveOrderResult(
                success=False,
                error=trusted_book_verdict.reason,
                proof_reference=req.strategy_proof_reference,
                broker_contacted=False,
            )
        final_verdict = await self.evaluate(req, trusted_orderbook, forecast)
        if not final_verdict.allow:
            return LiveOrderResult(
                success=False,
                error=final_verdict.reason,
                proof_reference=req.strategy_proof_reference,
                broker_contacted=False,
            )
        authority = self._mandatory_submit_authority(
            req,
            forecast=forecast,
        )
        if not authority.allow:
            return LiveOrderResult(
                success=False,
                error=authority.reason,
                proof_reference=req.strategy_proof_reference,
                broker_contacted=False,
            )
        order = self._build_order(req)
        capital_reservation_id: str | None = None
        existing_submission = self.exposure.submission_record(
            req.proposal_id
        )
        if existing_submission is not None:
            return LiveOrderResult(
                success=False,
                error=(
                    "EXISTING_SUBMISSION_REQUIRES_BROKER_RECONCILIATION"
                ),
                proof_reference=req.strategy_proof_reference,
                broker_contacted=False,
            )
        # Reserve the external envelope budget before the local exposure
        # reservation. Both are durable and both must succeed. A crash between
        # them leaves a conservative external reservation that an identical
        # proposal can resume idempotently; it never creates broker authority.
        if self.capital_envelope_adapter is not None:
            try:
                capital = self.capital_envelope_adapter.reserve_request(
                    req,
                    current_daily_loss_cents=max(
                        0, int(STATE.daily_loss_cents)
                    ),
                    current_local_total_exposure_cents=(
                        self.exposure.total_exposure_cents()
                    ),
                    current_local_correlated_exposure_cents=(
                        self.exposure.correlated_exposure_cents(
                            req.market_ticker
                        )
                    ),
                    current_local_open_orders=(
                        self.exposure.open_order_count()
                    ),
                )
            except Exception as exc:
                return LiveOrderResult(
                    success=False,
                    error=f"DUMBMONEY_CAPITAL_RESERVATION_FAILED:{type(exc).__name__}",
                    proof_reference=req.strategy_proof_reference,
                    broker_contacted=False,
                )
            if not capital.allow:
                return LiveOrderResult(
                    success=False,
                    error=capital.reason,
                    proof_reference=req.strategy_proof_reference,
                    broker_contacted=False,
                )
            capital_reservation_id = capital.reservation_id
        # Reserve the full LIMIT notional durably before transport. A timeout
        # is an unknown broker outcome, not evidence that no order exists.
        if not self.exposure.reserve_order_submission(
            req.proposal_id,
            req.market_ticker,
            req.size,
            req.price_cents,
            contract_ticker=req.contract_ticker,
            side=req.side,
        ):
            # The failure may be a concurrent/existing or ambiguously durable
            # local reservation. Retain the external reservation until broker
            # reconciliation; absence cannot be proven from a false return.
            if capital_reservation_id is not None:
                logger.warning(
                    "DumbMoney reservation retained after local failure",
                    extra={
                        "component": "firewall",
                        "proposal_id": req.proposal_id,
                    },
                )
            return LiveOrderResult(
                success=False,
                error="EXPOSURE_RESERVATION_FAILED",
                proof_reference=req.strategy_proof_reference,
                broker_contacted=False,
            )
        from kalshi.client import _CENTRAL_FIREWALL_SUBMIT_CAPABILITY

        mutation_permit: object | None = None
        prepare_mutation = (
            getattr(self.client, "prepare_order_mutation")
            if inspect.getattr_static(
                self.client,
                "prepare_order_mutation",
                None,
            )
            is not None
            else None
        )
        cancel_mutation = (
            getattr(self.client, "cancel_prepared_order_mutation")
            if inspect.getattr_static(
                self.client,
                "cancel_prepared_order_mutation",
                None,
            )
            is not None
            else None
        )
        if callable(prepare_mutation):
            try:
                # Any queue/limiter wait happens before the last Core
                # resolution. The resulting permit authorizes exactly one
                # socket attempt and cannot be reused after ambiguity.
                mutation_permit = await prepare_mutation(
                    "POST",
                    "/portfolio/events/orders",
                    _capability=_CENTRAL_FIREWALL_SUBMIT_CAPABILITY,
                )
            except Exception as exc:
                return LiveOrderResult(
                    success=False,
                    error=(
                        "BROKER_MUTATION_PREPARATION_FAILED:"
                        f"{type(exc).__name__}"
                    ),
                    proof_reference=req.strategy_proof_reference,
                    broker_contacted=False,
                )

        def release_unused_mutation_permit() -> None:
            nonlocal mutation_permit
            if mutation_permit is None or not callable(cancel_mutation):
                return
            try:
                cancel_mutation(
                    mutation_permit,
                    _capability=_CENTRAL_FIREWALL_SUBMIT_CAPABILITY,
                )
            except Exception:
                logger.exception(
                    "Unused broker mutation permit release failed",
                    extra={
                        "component": "firewall",
                        "proposal_id": req.proposal_id,
                    },
                )
            finally:
                mutation_permit = None

        # Reservation work can cross a short lease or operator-authority
        # boundary. Recheck at the last synchronous point before broker I/O.
        # If authority disappeared, retain both durable reservations: no
        # broker call occurred, but automatically releasing ambiguous
        # cross-process state could grant capacity to a concurrent proposal.
        authority = self._mandatory_submit_authority(
            req,
            reservation_held=True,
            trusted_orderbook=trusted_orderbook,
            forecast=forecast,
        )
        if not authority.allow:
            release_unused_mutation_permit()
            logger.info(
                "Live submit blocked after durable reservation",
                extra={
                    "component": "firewall",
                    "proposal_id": req.proposal_id,
                    "rejected_by": authority.rejected_by,
                    "reason": authority.reason,
                },
            )
            return LiveOrderResult(
                success=False,
                error=authority.reason,
                proof_reference=req.strategy_proof_reference,
                broker_contacted=False,
            )
        if self.capital_envelope_adapter is not None:
            if capital_reservation_id is None:
                release_unused_mutation_permit()
                return LiveOrderResult(
                    success=False,
                    error="DUMBMONEY_CAPITAL_RESERVATION_MISSING",
                    proof_reference=req.strategy_proof_reference,
                    broker_contacted=False,
                )
            try:
                claimant_nonce = secrets.token_hex(32)
                if len(claimant_nonce) != 64:
                    raise ValueError("dispatch nonce length mismatch")
                self.capital_envelope_adapter.claim_broker_dispatch(
                    req,
                    reservation_id=capital_reservation_id,
                    order=order,
                    claimant_nonce=claimant_nonce,
                )
            except Exception as exc:
                release_unused_mutation_permit()
                logger.error(
                    "DumbMoney broker dispatch claim failed",
                    extra={
                        "component": "firewall",
                        "proposal_id": req.proposal_id,
                        "error_type": type(exc).__name__,
                    },
                )
                return LiveOrderResult(
                    success=False,
                    error=(
                        "DUMBMONEY_DISPATCH_CLAIM_FAILED:"
                        f"{type(exc).__name__}"
                    ),
                    proof_reference=req.strategy_proof_reference,
                    broker_contacted=False,
                )
            # The command feed and local safety journals are separate durable
            # authorities. Recheck after consuming the one-shot dispatch claim
            # and immediately before transport. A denial leaves the claim and
            # both reservations intact for broker reconciliation; it never
            # creates permission to retry the same proposal.
            authority = self._mandatory_submit_authority(
                req,
                reservation_held=True,
                trusted_orderbook=trusted_orderbook,
                forecast=forecast,
            )
            if not authority.allow:
                release_unused_mutation_permit()
                logger.info(
                    "Live submit blocked after dispatch claim",
                    extra={
                        "component": "firewall",
                        "proposal_id": req.proposal_id,
                        "rejected_by": authority.rejected_by,
                        "reason": authority.reason,
                    },
                )
                return LiveOrderResult(
                    success=False,
                    error=authority.reason,
                    proof_reference=req.strategy_proof_reference,
                    broker_contacted=False,
                )
        try:
            create_kwargs: dict[str, Any] = {
                "_capability": _CENTRAL_FIREWALL_SUBMIT_CAPABILITY,
            }
            if mutation_permit is not None:
                create_kwargs["_mutation_permit"] = mutation_permit
            resp = await self.client.create_order(order, **create_kwargs)
            mutation_permit = None
            if self.capital_envelope_adapter is not None:
                order_id = self._validate_v2_create_response(
                    resp,
                    request=req,
                )
            else:
                order_id = (
                    resp.get("order", {}).get("order_id")
                    or resp.get("order_id")
                )
            if not order_id:
                self.exposure.mark_order_outcome_unknown(req.proposal_id)
                return LiveOrderResult(
                    success=False,
                    error="AMBIGUOUS_BROKER_OUTCOME:ORDER_ID_MISSING",
                    proof_reference=req.strategy_proof_reference,
                    broker_contacted=True,
                )
            persisted = self.exposure.confirm_open_order(
                req.proposal_id, str(order_id)
            )
            return LiveOrderResult(
                success=True,
                order_id=str(order_id),
                error=(None if persisted else "accepted_exposure_state_unhealthy"),
                proof_reference=req.strategy_proof_reference,
                broker_contacted=True,
            )
        except Exception as exc:
            # The permit is consumed before the socket call. A transport
            # exception, timeout, or HTTP 429 cannot prove non-acceptance.
            mutation_permit = None
            error_type = type(exc).__name__
            self.exposure.mark_order_outcome_unknown(req.proposal_id)
            logger.error(
                "Live order submit failed",
                extra={"component": "firewall", "error_type": error_type},
            )
            return LiveOrderResult(
                success=False,
                error=f"AMBIGUOUS_BROKER_OUTCOME:{error_type}",
                proof_reference=req.strategy_proof_reference,
                broker_contacted=True,
            )

    async def submit_limit_order_adapter(
        self,
        req: Any,
    ) -> LiveOrderResult:
        """Retired alternate live-submit surface.

        Legacy proof runners may still call this compatibility shim, but it
        can never construct an adapter or contact a broker. Real orders must
        supply canonical market, forecast, risk, and execution evidence to
        :meth:`submit`, the single central chokepoint.
        """
        proof_reference = str(getattr(req, "proof_id", "") or "")
        logger.warning(
            "Retired alternate live submit path blocked",
            extra={"component": "firewall"},
        )
        return LiveOrderResult(
            success=False,
            error="LEGACY_ADAPTER_SUBMIT_RETIRED_USE_CENTRAL_FIREWALL",
            proof_reference=proof_reference,
            broker_contacted=False,
        )
