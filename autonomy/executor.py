"""Executor: routes decisions to shadow or the central live firewall.

Live mode requires a valid autonomy session authority (exact typed ack,
unexpired) and a clear kill file. Every live order flows through
LiveBrokerFirewall.evaluate/submit — LIMIT only, with persisted risk/exposure,
current evidence, authority, compliance, and liquidity gates.
Truthful outcomes: broker contact is claimed only on transport witness.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from autonomy.execution_policy import ExecutionPolicy
from autonomy.ontology import Decision, DecisionAction, MarketView, OutcomeKind, SessionMode, TradeOutcome
from autonomy.staleness import StalenessPolicy, evaluate_snapshot_freshness
from autonomy.target_policy import (
    has_prediction_target_authority,
    is_prediction_quarantined_target,
)
from forecasting.model_influence_attestation import build_model_influence_attestation

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
        risk_state_path: Path | None = None,
        quote_fn: Any | None = None,
        shadow_book_fn: Any | None = None,
        staleness_policy: StalenessPolicy | None = None,
        exchange_status_fn: Callable[[], dict[str, Any]] | None = None,
        now_fn: Callable[[], float] | None = None,
        execution_policy: ExecutionPolicy | None = None,
        capital_envelope_adapter: Any | None = None,
        core_submission_authority: Callable[[], bool] | None = None,
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
        self.risk_state_path = risk_state_path or Path(
            os.environ.get(
                "DUMMY_AUTONOMY_LIVE_RISK_STATE_PATH",
                "runtime/autonomy/risk_state_live.json",
            )
        )
        # Fresh pre-submit book read consumed by the taker execution policy
        # (_apply_taker_policy). The session builder wires it for BOTH shadow
        # and live books from the public read-only orderbook fetch, so paper
        # evidence can accrue under the same taker policy the live path uses.
        # When absent, failing, or stale, a taker (C1) order fails closed with
        # the existing block reasons (taker_no_fresh_book / taker_quote_stale).
        self.quote_fn = quote_fn
        self.shadow_book_fn = shadow_book_fn
        # Stale-data submit gate. Active only when a policy is supplied; when
        # active it is fail-closed (missing snapshot timestamp => refuse). Left
        # None by most callers/tests so existing behavior is unchanged.
        self.staleness_policy = staleness_policy
        # Optional venue re-check at the moment of a LIVE submit (halt state can
        # change between cycle start and submit). Fails CLOSED: a missing,
        # failed, or malformed status blocks the submit
        # (exchange_status_unavailable_at_submit), as does maintenance/halt.
        self.exchange_status_fn = exchange_status_fn
        # Optional DumbMoney deny-only capital ceiling. This adapter cannot
        # replace the session acknowledgement, local risk state, kill switch,
        # central firewall, or live-submit authority.
        self.capital_envelope_adapter = capital_envelope_adapter
        self.core_submission_authority = core_submission_authority
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc).timestamp())
        # Counter so a refusal is never a silent skip: surfaced on the executor
        # for the daemon/dashboard, and each refusal is also recorded as a
        # BLOCKED_LOCAL outcome in the ledger with its reason.
        self.stale_block_count = 0

    def _idempotency_key(self, decision: Decision) -> str:
        return hashlib.sha256(f"autonomy|{decision.decision_id}".encode("utf-8")).hexdigest()[:32]

    def _target_context_block(
        self,
        decision: Decision,
        market: MarketView | None,
    ) -> TradeOutcome | None:
        """Verify the exact structured target before either execution book."""
        if market is None:
            return self._blocked(decision, "prediction_target_context_unverified")
        if market.ticker != decision.market_ticker:
            return self._blocked(decision, "prediction_target_context_mismatch")
        raw = market.raw or {}
        context = {
            "category": raw.get("category"),
            "vertical": market.vertical,
            "series_tags": raw.get("series_tags") or raw.get("tags"),
        }
        if is_prediction_quarantined_target(decision.market_ticker, **context):
            return self._blocked(
                decision,
                "prediction_target_quarantine",
                {
                    "target_category": context["category"],
                    "target_vertical": market.vertical.value,
                },
            )
        if not has_prediction_target_authority(decision.market_ticker, **context):
            return self._blocked(
                decision,
                "prediction_target_eligibility_unverified",
                {
                    "target_category": context["category"],
                    "target_vertical": market.vertical.value,
                },
            )
        return None

    async def execute(
        self,
        decision: Decision,
        *,
        snapshot_ts: Any | None = None,
        is_live_market: bool = False,
        market_prior_yes: float | None = None,
        market: MarketView | None = None,
    ) -> TradeOutcome:
        target_block = self._target_context_block(decision, market)
        if target_block is not None:
            return target_block
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
            detail.update(self._execution_detail(decision))
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
                detail["liquidity_role"] == "maker"
                and detail.get("queue_snapshot_available")
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

        # A real submit requires a positive, current venue-health witness.
        # Missing/failed/partial status is unknown authority, not permission.
        if self.exchange_status_fn is None:
            return self._blocked(decision, "exchange_status_unavailable_at_submit")
        try:
            venue = self.exchange_status_fn()
        except Exception:
            return self._blocked(decision, "exchange_status_unavailable_at_submit")
        if not isinstance(venue, dict):
            return self._blocked(decision, "exchange_status_unavailable_at_submit")
        if venue.get("exchange_active") is not True:
            return self._blocked(decision, "exchange_maintenance_at_submit")
        if venue.get("trading_active") is not True:
            return self._blocked(decision, "trading_halted_at_submit")

        return await self._execute_live_via_firewall(decision, market)

    def _make_firewall(self):
        """Build the sole production live-submit boundary from real state."""
        from kalshi.client import KalshiClient
        from live_firewall.exposure_tracker import get_persistent_exposure_tracker
        from live_firewall.firewall import LiveBrokerFirewall

        if self.capital_envelope_adapter is None:
            raise RuntimeError(
                "DumbMoney capital adapter is mandatory for LIVE execution"
            )
        return LiveBrokerFirewall(
            KalshiClient(),
            get_persistent_exposure_tracker(),
            autonomy_risk_state_path=self.risk_state_path,
            require_autonomy_risk_state=True,
            capital_envelope_adapter=self.capital_envelope_adapter,
            core_submission_authority=self.core_submission_authority,
        )

    def _risk_state_digest(self) -> str | None:
        try:
            payload = self.risk_state_path.read_bytes()
            data = json.loads(payload.decode("utf-8"))
        except Exception:
            return None
        if not isinstance(data, dict):
            return None
        return hashlib.sha256(payload).hexdigest().upper()

    @staticmethod
    def _side_book_levels(orderbook: Any, side: str) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
        """Return bid/ask ladders in the requested contract's price frame."""
        if side == "yes":
            bids = [(int(level.price), int(level.size)) for level in orderbook.bids]
            asks = [(int(level.price), int(level.size)) for level in orderbook.asks]
        else:
            bids = [(100 - int(level.price), int(level.size)) for level in orderbook.asks]
            asks = [(100 - int(level.price), int(level.size)) for level in orderbook.bids]
        return (
            sorted(bids, key=lambda item: item[0], reverse=True),
            sorted(asks, key=lambda item: item[0]),
        )

    def _live_book_execution_verdict(
        self,
        decision: Decision,
        orderbook: Any,
    ) -> tuple[TradeOutcome | None, dict[str, Any]]:
        bids, asks = self._side_book_levels(orderbook, decision.side)
        evidence: dict[str, Any] = {
            "firewall_book_timestamp": orderbook.timestamp.isoformat(),
            "firewall_book_bid_levels": len(bids),
            "firewall_book_ask_levels": len(asks),
        }
        if not bids or not asks:
            return self._blocked(decision, "firewall_book_missing_two_sided_depth"), evidence
        best_bid = bids[0][0]
        best_ask = asks[0][0]
        evidence.update({
            "firewall_best_bid_cents": best_bid,
            "firewall_best_ask_cents": best_ask,
        })
        if self.execution_policy.mode != "taker":
            if decision.price_cents >= best_ask:
                return self._blocked(decision, "quote_crossed_repriced_out"), evidence
            if decision.price_cents < best_bid:
                return self._blocked(decision, "quote_behind_current_best_bid"), evidence
            queue_ahead = sum(size for price, size in bids if price == decision.price_cents)
            evidence["firewall_queue_ahead_contracts"] = queue_ahead
            if queue_ahead > MAX_QUEUE_AHEAD_CONTRACTS:
                return self._blocked(decision, "queue_ahead_exceeds_execution_cap"), evidence
            return None, evidence

        from autonomy.executable_liquidity import LIQUIDITY_EVIDENCE_VERSION

        reprice = decision.risk_snapshot.get("execution_reprice")
        plan = (
            reprice.get("executable_liquidity")
            if isinstance(reprice, dict) else None
        )
        if not isinstance(plan, dict):
            return self._blocked(decision, "taker_liquidity_plan_missing"), evidence
        try:
            planned_version = str(plan["liquidity_evidence_version"])
            planned_count = int(plan["executable_count"])
            planned_limit = int(plan["submitted_limit_price_cents"])
            planned_vwap = float(plan["modeled_vwap_cents"])
            planned_fee = int(plan["modeled_fee_cents"])
            planned_net_ev = float(plan["net_ev_cents_per_contract"])
            planned_notional = int(plan["worst_case_notional_cents"])
            fill_status = str(plan["fill_status"])
        except (KeyError, TypeError, ValueError):
            return self._blocked(decision, "taker_liquidity_plan_malformed"), evidence
        if (
            planned_version != LIQUIDITY_EVIDENCE_VERSION
            or fill_status != "unfilled_plan_only"
            or planned_count != int(decision.count)
            or planned_limit != int(decision.price_cents)
            or planned_notional != int(decision.notional_cents)
            or planned_fee < 0
            or not (0.0 < planned_vwap <= float(planned_limit))
            or abs(planned_net_ev - float(decision.ev_cents_per_contract)) > 0.011
        ):
            return self._blocked(decision, "taker_liquidity_plan_mismatch"), evidence
        minimum_ev = float(
            getattr(self.execution_policy, "taker_min_ev_cents", 0.0) or 0.0
        )
        if planned_net_ev < minimum_ev:
            return self._blocked(decision, "taker_ev_below_min"), evidence

        remaining = planned_count
        cost_cents = 0
        used_levels: list[dict[str, int]] = []
        for price, size in asks:
            if price > planned_limit or remaining <= 0:
                break
            take = min(remaining, size)
            if take > 0:
                used_levels.append({"price_cents": price, "count": take})
                cost_cents += price * take
                remaining -= take
        if remaining > 0:
            evidence["firewall_executable_contracts"] = planned_count - remaining
            return self._blocked(decision, "taker_depth_changed_before_firewall"), evidence
        vwap = cost_cents / planned_count
        evidence.update({
            "firewall_executable_contracts": planned_count,
            "firewall_execution_vwap_cents": round(vwap, 6),
            "firewall_execution_levels": used_levels,
            "planned_execution_vwap_cents": round(planned_vwap, 6),
            "planned_execution_fee_cents": planned_fee,
            "planned_net_ev_cents_per_contract": round(planned_net_ev, 6),
            "liquidity_evidence_version": planned_version,
        })
        if vwap > planned_vwap + 1e-6:
            return self._blocked(
                decision, "taker_depth_changed_before_firewall"
            ), evidence
        return None, evidence

    def _to_firewall_forecast(self, decision: Decision, market: MarketView, orderbook: Any):
        from core.ontology import Forecast as FirewallForecast
        from autonomy.risk_brain import kalshi_maker_fee_cents, kalshi_taker_fee_cents

        now = datetime.now(timezone.utc)
        try:
            expiration = datetime.fromisoformat(market.close_time.replace("Z", "+00:00"))
            if expiration.tzinfo is None:
                expiration = expiration.replace(tzinfo=timezone.utc)
        except Exception as exc:
            raise ValueError("market close time unavailable") from exc
        if expiration <= now:
            raise ValueError("market already closed")
        best_bid = max(int(level.price) for level in orderbook.bids)
        best_ask = min(int(level.price) for level in orderbook.asks)
        spread = best_ask - best_bid
        total_depth = sum(int(level.size) for level in orderbook.bids + orderbook.asks)
        depth_score = min(Decimal("1"), Decimal(total_depth) / Decimal("1000"))
        spread_score = max(Decimal("0"), Decimal("1") - Decimal(spread) / Decimal("10"))
        liquidity_score = depth_score * spread_score
        book_age = max(0.0, (now - orderbook.timestamp).total_seconds())
        freshness_score = Decimal(str(round(max(0.0, 1.0 - book_age / 300.0), 4)))
        implied_yes = Decimal(best_bid + best_ask) / Decimal("200")
        probability_yes = Decimal(str(float(decision.forecast.probability_yes)))
        uncertainty = max(0.0, min(0.5, float(decision.forecast.uncertainty)))
        lower = Decimal(str(max(0.0, float(probability_yes) - uncertainty)))
        upper = Decimal(str(min(1.0, float(probability_yes) + uncertainty)))
        confidence = Decimal(str(max(0.0, min(1.0, 1.0 - uncertainty * 2.0))))
        raw_settlement_risk = market.raw.get("settlement_risk_score")
        try:
            settlement_risk = Decimal(str(raw_settlement_risk))
        except Exception:
            settlement_risk = Decimal("1")
        settlement_risk = min(Decimal("1"), max(Decimal("0"), settlement_risk))
        if self.execution_policy.mode == "taker":
            fee_cents = kalshi_taker_fee_cents(
                decision.price_cents, decision.count, decision.market_ticker
            )
        else:
            fee_cents = kalshi_maker_fee_cents(
                decision.price_cents, decision.count, decision.market_ticker
            )
        per_contract_fee = fee_cents / max(1, decision.count)
        gross_edge = Decimal(str((decision.ev_cents_per_contract + per_contract_fee) / 100.0))
        net_edge = Decimal(str(decision.ev_cents_per_contract / 100.0))
        forecast_proof = f"autonomy_forecast:{decision.decision_id}"
        strategy_proof = f"autonomy_strategy_v2:{decision.decision_id}"
        try:
            forecast_timestamp = datetime.fromisoformat(decision.created_at.replace("Z", "+00:00"))
            if forecast_timestamp.tzinfo is None:
                raise ValueError("decision timestamp must be timezone-aware")
        except Exception as exc:
            raise ValueError("decision timestamp unavailable") from exc
        return FirewallForecast(
            market_ticker=decision.market_ticker,
            contract_ticker=decision.market_ticker,
            event_title=market.title,
            contract_title=str(market.raw.get("subtitle") or market.title),
            market_implied_probability=implied_yes,
            dummy_probability=probability_yes,
            probability_delta=probability_yes - implied_yes,
            confidence_score=confidence,
            uncertainty_band=(lower, upper),
            expected_edge=gross_edge,
            edge_after_fees=net_edge,
            freshness_score=freshness_score,
            liquidity_score=liquidity_score,
            spread_score=spread_score,
            orderbook_depth_score=depth_score,
            settlement_risk_score=settlement_risk,
            source_summary=",".join(sorted(decision.forecast.sources_used)) or "no_sources",
            model_summary=decision.forecast.rationale[:500],
            calibration_notes=f"uncertainty={uncertainty:.6f};central_firewall_v2",
            timestamp=forecast_timestamp,
            expiration=expiration,
            strategy_references=[strategy_proof],
            proof_reference=forecast_proof,
        )

    async def _execute_live_via_firewall(
        self,
        decision: Decision,
        market: MarketView | None,
    ) -> TradeOutcome:
        if market is None or market.ticker != decision.market_ticker:
            return self._blocked(decision, "live_market_context_missing_or_mismatched")
        if self.capital_envelope_adapter is None:
            return self._blocked(
                decision,
                "dumbmoney_capital_adapter_required_for_live_execution",
            )
        try:
            firewall = self._make_firewall()
        except Exception as exc:
            return self._blocked(decision, f"central_firewall_unavailable:{type(exc).__name__}")
        try:
            authority = firewall.live_authority_verdict()
            if not authority.allow:
                return self._blocked(
                    decision,
                    authority.reason,
                    {"rejected_by": authority.rejected_by or "live_authority"},
                )
            risk_digest = self._risk_state_digest()
            if risk_digest is None:
                return self._blocked(decision, "persisted_autonomy_risk_state_unavailable")
            capital_binding: dict[str, Any] = {}
            if self.capital_envelope_adapter is not None:
                from live_firewall.dumbmoney_capital import strategy_binding_hash

                try:
                    capital_binding = self.capital_envelope_adapter.binding_for(
                        strategy_hash=strategy_binding_hash(
                            f"autonomy_strategy_v2:{decision.decision_id}"
                        ),
                        passport_hash=strategy_binding_hash(
                            f"autonomy_forecast:{decision.decision_id}"
                        ),
                        authorized_instrument=(
                            f"event_contract:{decision.market_ticker}"
                        ),
                    )
                except Exception as exc:
                    return self._blocked(
                        decision,
                        f"signed_capital_envelope_unavailable:{type(exc).__name__}",
                    )
            client = getattr(firewall, "client", None)
            get_orderbook = getattr(client, "get_orderbook", None)
            if not callable(get_orderbook):
                return self._blocked(decision, "central_firewall_orderbook_reader_unavailable")
            try:
                orderbook = await get_orderbook(decision.market_ticker, depth=10)
            except Exception as exc:
                return self._blocked(decision, f"fresh_orderbook_unavailable:{type(exc).__name__}")
            book_block, book_evidence = self._live_book_execution_verdict(decision, orderbook)
            if book_block is not None:
                return TradeOutcome(
                    **{**book_block.__dict__, "detail": {**book_block.detail, **book_evidence}}
                )
            try:
                firewall_forecast = self._to_firewall_forecast(decision, market, orderbook)
            except Exception as exc:
                return self._blocked(decision, f"firewall_forecast_unavailable:{type(exc).__name__}")
            from core.ontology import LiveOrderRequest

            strategy_proof = f"autonomy_strategy_v2:{decision.decision_id}"
            expiration_ts = int(datetime.now(timezone.utc).timestamp()) + order_ttl_seconds(
                decision.market_ticker
            )
            request_fields = {
                "proposal_id": self._idempotency_key(decision),
                "market_ticker": decision.market_ticker,
                "contract_ticker": decision.market_ticker,
                "side": decision.side,
                "price_cents": decision.price_cents,
                "size": decision.count,
                "strategy_proof_reference": strategy_proof,
                "forecast_proof_reference": firewall_forecast.proof_reference,
                "adapter_name": "kalshi_live_firewall_adapter",
                "liquidity_role": self.execution_policy.mode,
                "risk_state_sha256": risk_digest,
                "risk_snapshot": dict(decision.risk_snapshot),
                "expiration_ts": expiration_ts,
                **capital_binding,
            }
            request = LiveOrderRequest(
                **request_fields,
                model_influence_attestation=build_model_influence_attestation(
                    firewall_forecast,
                    request_fields,
                ),
            )
            try:
                result = await firewall.submit(request, orderbook, firewall_forecast)
            except Exception as exc:
                return self._blocked(
                    decision,
                    f"central_firewall_submit_failed:{type(exc).__name__}",
                    book_evidence,
                )
        finally:
            try:
                await firewall.client.close()
            except Exception:
                pass
        detail = {
            **self._execution_detail(decision),
            **book_evidence,
            "firewall_error": result.error,
        }
        if result.success and result.order_id:
            return TradeOutcome(
                decision_id=decision.decision_id,
                market_ticker=decision.market_ticker,
                kind=OutcomeKind.ACCEPTED,
                order_id=result.order_id,
                fill_count=0,
                fill_price_cents=None,
                pnl_cents=None,
                broker_contacted=bool(result.broker_contacted),
                detail={"state": "submitted", **detail},
            )
        return TradeOutcome(
            decision_id=decision.decision_id,
            market_ticker=decision.market_ticker,
            kind=(OutcomeKind.REJECTED if result.broker_contacted else OutcomeKind.BLOCKED_LOCAL),
            order_id=None,
            fill_count=0,
            fill_price_cents=None,
            pnl_cents=None,
            broker_contacted=bool(result.broker_contacted),
            detail=detail,
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

    def _execution_detail(self, decision: Decision) -> dict[str, Any]:
        """Canonical submitted-order metadata carried by every open outcome.

        ``fill_count`` remains the fill-truth discriminator.  The price here is
        explicitly the submitted limit until a later simulator/broker witness
        records a positive fill count and its execution price.
        """
        liquidity_role = "taker" if self.execution_policy.mode == "taker" else "maker"
        detail = {
            "execution_policy_cohort": self.execution_policy.cohort,
            "submitted_liquidity_role": liquidity_role,
            "liquidity_role": liquidity_role,
            "submitted_price_cents": int(decision.price_cents),
            "submitted_count": int(decision.count),
            "submitted_notional_cents": int(decision.notional_cents),
            "submitted_ev_cents_per_contract": float(decision.ev_cents_per_contract),
            "submitted_kelly_fraction": float(decision.kelly_fraction),
            "price_evidence": "submitted_limit",
        }
        reprice = decision.risk_snapshot.get("execution_reprice")
        liquidity = (
            reprice.get("executable_liquidity")
            if isinstance(reprice, dict) else None
        )
        if isinstance(liquidity, dict):
            detail["executable_liquidity"] = dict(liquidity)
        for key in (
            "maker_adverse_selection_haircut_cents",
            "maker_adverse_selection_report_sha256",
            "maker_adverse_selection_generated_at",
        ):
            if key in decision.risk_snapshot:
                detail[key] = decision.risk_snapshot[key]
        return detail

    def _apply_taker_policy(self, decision: Decision) -> "Decision | TradeOutcome":
        """Build a fresh, depth-capped, fee-aware executable taker plan.

        A top ask alone does not prove that ``decision.count`` is executable.
        Taker submission therefore requires a timestamped side-specific ask
        ladder, discounts displayed depth, caps spread/slippage and the
        original risk-brain notional, and recomputes EV from modeled VWAP.
        The plan remains unfilled evidence until reconciliation witnesses the
        actual broker/simulator quantity, price, role, and fee.
        """
        if self.execution_policy.mode != "taker":
            return decision

        from dataclasses import replace as dataclass_replace

        from autonomy.executable_liquidity import (
            LIQUIDITY_EVIDENCE_VERSION,
            MAX_FRESH_QUOTE_AGE_SECONDS,
            assess_taker_liquidity,
            evaluate_quote_freshness,
        )
        from autonomy.fees import kalshi_taker_fee_cents
        from autonomy.risk_brain import kelly_fraction_yes

        fresh = None
        if self.quote_fn is not None:
            try:
                fresh = self.quote_fn(decision.market_ticker)
            except Exception:
                fresh = None
        freshness = evaluate_quote_freshness(fresh, now_ts=self._now_fn())
        if not freshness.valid:
            return self._blocked(
                decision,
                freshness.reason,
                {
                    "quote_age_seconds": freshness.age_seconds,
                    "quote_received_at": freshness.received_at,
                    "maximum_quote_age_seconds": MAX_FRESH_QUOTE_AGE_SECONDS,
                    "liquidity_evidence_version": LIQUIDITY_EVIDENCE_VERSION,
                },
            )

        p_yes = float(decision.forecast.probability_yes)
        forecast_p_side = p_yes if decision.side == "yes" else 1.0 - p_yes
        # Preserve the allocator's conservative probability rather than
        # upgrading back to the raw forecast during a book move. The encoded
        # probability is reconstructed from the decision's fee-adjusted EV and
        # then capped by the raw side probability.
        original_fee = kalshi_taker_fee_cents(
            int(decision.price_cents), 1, decision.market_ticker
        )
        encoded_p_side = (
            float(decision.ev_cents_per_contract)
            + int(decision.price_cents)
            + original_fee
        ) / 100.0
        p_side = min(forecast_p_side, max(0.0, min(1.0, encoded_p_side)))
        min_ev = float(self.execution_policy.taker_min_ev_cents or 0.0)
        edge_floor = float(self.execution_policy.taker_min_edge_cents or 0.0)
        assessment = assess_taker_liquidity(
            fresh,
            side=decision.side,
            requested_count=max(0, int(decision.count)),
            notional_cap_cents=max(0, int(decision.notional_cents)),
            probability_side=p_side,
            market_ticker=decision.market_ticker,
            min_ev_cents=min_ev,
            min_edge_cents=edge_floor,
        )
        if not assessment.allowed or assessment.plan is None:
            return self._blocked(
                decision,
                assessment.reason,
                {
                    **assessment.detail,
                    "quote_age_seconds": freshness.age_seconds,
                    "quote_received_at": freshness.received_at,
                    "liquidity_evidence_version": LIQUIDITY_EVIDENCE_VERSION,
                },
            )

        plan = assessment.plan
        repriced_kelly = kelly_fraction_yes(p_side, plan.limit_price_cents)
        liquidity_evidence = plan.evidence(freshness.received_at)
        risk_snapshot = dict(decision.risk_snapshot)
        risk_snapshot["execution_reprice"] = {
            "liquidity_role": "taker",
            "decision_price_cents": int(decision.price_cents),
            "decision_count": int(decision.count),
            "decision_notional_cents": int(decision.notional_cents),
            "submitted_price_cents": plan.limit_price_cents,
            "submitted_count": plan.executable_count,
            "submitted_notional_cents": plan.worst_case_notional_cents,
            "submitted_ev_cents_per_contract": round(
                plan.net_ev_cents_per_contract, 2
            ),
            "submitted_kelly_fraction": round(repriced_kelly, 4),
            "executable_liquidity": liquidity_evidence,
        }
        return dataclass_replace(
            decision,
            price_cents=plan.limit_price_cents,
            count=plan.executable_count,
            notional_cents=plan.worst_case_notional_cents,
            ev_cents_per_contract=round(plan.net_ev_cents_per_contract, 2),
            kelly_fraction=round(repriced_kelly, 4),
            risk_snapshot=risk_snapshot,
        )

    def _blocked(
        self,
        decision: Decision,
        reason: str,
        detail: dict[str, Any] | None = None,
    ) -> TradeOutcome:
        payload = {"reason": reason}
        payload.update(detail or {})
        return TradeOutcome(
            decision_id=decision.decision_id,
            market_ticker=decision.market_ticker,
            kind=OutcomeKind.BLOCKED_LOCAL,
            order_id=None,
            fill_count=0,
            fill_price_cents=None,
            pnl_cents=None,
            broker_contacted=False,
            detail=payload,
        )
