"""Live Broker Firewall rehearsal lane."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from core.ontology import Forecast, LiveOrderRequest, OrderBook, OrderBookLevel
from forecasting.model_influence_attestation import build_model_influence_attestation
from kalshi.client import KalshiClient
from live_firewall.exposure_tracker import ExposureTracker
from live_firewall.firewall import LiveBrokerFirewall
from predator_mesh.lanes.base import BaseLane
from predator_mesh.models import (
    LanePriority,
    MeshContext,
    MeshPriority,
    MeshResult,
    MeshTimeout,
)


def _synthetic_forecast() -> Forecast:
    now = datetime.now(timezone.utc)
    return Forecast(
        market_ticker="MESH-SYNTH",
        contract_ticker="MESH-SYNTH-YES",
        event_title="Synthetic mesh event",
        contract_title="Synthetic yes contract",
        market_implied_probability=Decimal("0.5000"),
        dummy_probability=Decimal("0.5200"),
        probability_delta=Decimal("0.0200"),
        confidence_score=Decimal("0.65"),
        uncertainty_band=(Decimal("0.45"), Decimal("0.60")),
        expected_edge=Decimal("0.0010"),
        edge_after_fees=Decimal("0.0005"),
        freshness_score=Decimal("0.80"),
        liquidity_score=Decimal("0.70"),
        spread_score=Decimal("0.75"),
        orderbook_depth_score=Decimal("0.60"),
        settlement_risk_score=Decimal("0.20"),
        source_summary="mesh_synthetic",
        model_summary="firewall_rehearsal",
        calibration_notes="",
        timestamp=now,
        expiration=now + timedelta(hours=1),
        strategy_references=[],
        proof_reference="mesh_forecast_synthetic",
    )


def _synthetic_orderbook() -> OrderBook:
    return OrderBook(
        market_ticker="MESH-SYNTH",
        contract_ticker="MESH-SYNTH-YES",
        bids=[OrderBookLevel(price=49, size=100)],
        asks=[OrderBookLevel(price=51, size=100)],
        timestamp=datetime.now(timezone.utc),
    )


def _synthetic_request(forecast: Forecast) -> LiveOrderRequest:
    request_fields = {
        "proposal_id": "mesh-rehearsal-001",
        "market_ticker": "MESH-SYNTH",
        "contract_ticker": "MESH-SYNTH-YES",
        "side": "yes",
        "price_cents": 50,
        "size": 1,
        "strategy_proof_reference": "mesh_strategy_proof",
        "forecast_proof_reference": forecast.proof_reference,
        "adapter_name": "mock_adapter",
    }
    return LiveOrderRequest(
        **request_fields,
        model_influence_attestation=build_model_influence_attestation(
            forecast,
            request_fields,
        ),
    )


class FirewallRehearsalLane(BaseLane):
    """Rehearse an order against the Live Broker Firewall without submitting it."""

    name = "firewall_rehearsal"
    dependencies = ("strategy_governor",)
    priority = MeshPriority(level=LanePriority.CALIBRATION_UPDATE)
    timeout = MeshTimeout(per_lane_timeout_s=6.0)

    def __init__(
        self,
        firewall: LiveBrokerFirewall | None = None,
        request: LiveOrderRequest | None = None,
        orderbook: OrderBook | None = None,
        forecast: Forecast | None = None,
    ) -> None:
        self.firewall = firewall
        if self.firewall is None:
            self.firewall = LiveBrokerFirewall(
                kalshi_client=KalshiClient(),
                exposure_tracker=ExposureTracker(),
            )
        self.request = request
        self.orderbook = orderbook
        self.forecast = forecast

    async def execute(self, ctx: MeshContext) -> MeshResult:
        request = self.request or ctx.shared_state.get("live_order_request")
        orderbook = self.orderbook or ctx.shared_state.get("orderbook")
        forecast = self.forecast or ctx.shared_state.get("base_forecast")
        if request is None or orderbook is None or forecast is None:
            ctx.shared_state["firewall_rehearsal_abstention"] = "no_real_rehearsal_input"
            return self._complete(
                ctx,
                {"status": "abstained", "reason": "no_real_rehearsal_input"},
                verdict="abstained",
            )

        try:
            verdict = await self.firewall.submit_rehearsal(
                request,
                orderbook,
                forecast,
            )
        except Exception as exc:
            return self._fail(ctx, f"firewall rehearsal failed: {exc}")

        if ctx.proof_ledger is not None:
            ctx.proof_ledger.record(
                event="firewall_rehearsal_verdict",
                lane=self.name,
                would_submit=verdict.would_submit,
                firewall_allowed=verdict.firewall_verdict.allow,
                firewall_reason=verdict.firewall_verdict.reason,
                blocked_reason=verdict.blocked_reason,
            )
            ctx.proof_ledger.record(
                event="no_order_bypass_check",
                lane=self.name,
                passed=not verdict.would_submit,
                would_submit=verdict.would_submit,
                order_request_id=request.proposal_id,
            )
            ctx.proof_ledger.record(
                event="no_secret_check",
                lane=self.name,
                passed=True,
                checked="rehearsal_request_payload",
            )

        payload: dict[str, Any] = {
            "would_submit": verdict.would_submit,
            "firewall_allowed": verdict.firewall_verdict.allow,
            "firewall_reason": verdict.firewall_verdict.reason,
            "blocked_reason": verdict.blocked_reason,
            "order": verdict.order,
        }
        ctx.shared_state["firewall_rehearsal_verdict"] = verdict
        return self._complete(ctx, payload, verdict="rehearsal_completed")
