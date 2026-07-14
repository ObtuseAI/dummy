"""Read-only adapters around incumbent forecasting and evidence surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any, Callable

from autonomy.ontology import MarketView, Signal, Vertical

from dummy.agents.contract import (
    AgentBudget,
    AgentContract,
    AgentRole,
    AgentVertical,
)
from dummy.agents.runtime import AgentInvocation
from dummy.chronos import ClockDomain
from dummy.constitution import Authority
from dummy.protocols import MessageEnvelope, MessageType


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("adapter timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def _only_message(
    invocation: AgentInvocation,
    expected: MessageType,
) -> MessageEnvelope:
    if len(invocation.input_messages) != 1:
        raise ValueError("adapter requires exactly one input message")
    message = invocation.input_messages[0]
    if message.message_type is not expected:
        raise ValueError(f"adapter requires {expected.value}")
    if message.market_id != invocation.market_id:
        raise ValueError("input market_id differs from invocation")
    return message


def market_view_observation(
    market: MarketView,
    *,
    sender: str,
    issued_at: datetime,
    effective_time: datetime,
    received_at: datetime,
    model_version: str,
    policy_version: str,
    evidence_ids: tuple[str, ...] = (),
) -> MessageEnvelope:
    """Freeze the incumbent MarketView as a typed point-in-time observation."""

    return MessageEnvelope.create(
        message_type=MessageType.OBSERVATION,
        sender=sender,
        market_id=market.ticker,
        issued_at=issued_at,
        effective_time=effective_time,
        received_at=received_at,
        model_version=model_version,
        policy_version=policy_version,
        evidence_ids=evidence_ids,
        payload={
            "observation_kind": "market_view",
            "ticker": market.ticker,
            "title": market.title,
            "vertical": market.vertical.value,
            "status": market.status,
            "close_time": market.close_time,
            "yes_bid": market.yes_bid,
            "yes_ask": market.yes_ask,
            "no_bid": market.no_bid,
            "no_ask": market.no_ask,
            "volume": market.volume,
            "liquidity": market.liquidity,
            "tick_size": market.tick_size,
            "raw": market.raw,
        },
    )


def market_view_from_observation(message: MessageEnvelope) -> MarketView:
    if message.message_type is not MessageType.OBSERVATION:
        raise ValueError("market view requires an OBSERVATION message")
    payload = message.payload
    if payload.get("observation_kind") != "market_view":
        raise ValueError("observation is not a market view")
    ticker = str(payload.get("ticker", ""))
    if ticker != message.market_id:
        raise ValueError("market view ticker differs from envelope market_id")
    try:
        vertical = Vertical(str(payload["vertical"]))
        return MarketView(
            ticker=ticker,
            title=str(payload["title"]),
            vertical=vertical,
            status=str(payload["status"]),
            close_time=str(payload["close_time"]),
            yes_bid=_optional_int(payload.get("yes_bid")),
            yes_ask=_optional_int(payload.get("yes_ask")),
            no_bid=_optional_int(payload.get("no_bid")),
            no_ask=_optional_int(payload.get("no_ask")),
            volume=int(payload["volume"]),
            liquidity=int(payload["liquidity"]),
            tick_size=int(payload.get("tick_size", 1)),
            raw=dict(payload.get("raw", {})),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("malformed market view observation") from exc


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def forecast_contract(
    *,
    agent_id: str,
    role: AgentRole,
    vertical: AgentVertical,
    market_types: tuple[str, ...],
    clock_domain: ClockDomain,
    calibration_identity: str,
    source_family: str,
    version: str,
    fail_closed_on: tuple[str, ...],
    dependencies: tuple[str, ...] = (),
    max_input_age_ms: int = 60_000,
) -> AgentContract:
    return AgentContract(
        agent_id=agent_id,
        role=role,
        vertical=vertical,
        supported_market_types=market_types,
        input_types=(MessageType.OBSERVATION,),
        output_types=(MessageType.FORECAST,),
        clock_domain=clock_domain,
        authority=Authority.FORECAST,
        evidence_requirements=("fresh_market_view",),
        fail_closed_on=fail_closed_on,
        budget=AgentBudget(max_messages_per_invocation=1),
        calibration_identity=calibration_identity,
        source_family=source_family,
        version=version,
        dependencies=dependencies,
        max_input_age_ms=max_input_age_ms,
    )


def build_market_prior_agent(
    *,
    agent_id: str,
    vertical: AgentVertical,
    market_types: tuple[str, ...],
    clock_domain: ClockDomain,
    version: str = "1.0.0",
    source: Any = None,
) -> tuple[AgentContract, SignalForecastAgent]:
    """Build a typed wrapper around the incumbent market-price anchor."""

    if source is None:
        from autonomy.signals.market_prior import MarketPriorSignal

        source = MarketPriorSignal()
    contract = forecast_contract(
        agent_id=agent_id,
        role=AgentRole.MARKET_PRIOR,
        vertical=vertical,
        market_types=market_types,
        clock_domain=clock_domain,
        calibration_identity="market-price-anchor-v1",
        source_family="market-price",
        version=version,
        fail_closed_on=("missing_book", "stale_market", "crossed_book"),
    )
    return contract, SignalForecastAgent(contract, source.generate)


def build_crypto_signal_agent(
    source: Any,
    *,
    agent_id: str,
    market_types: tuple[str, ...],
    clock_domain: ClockDomain,
    calibration_identity: str,
    source_family: str,
    version: str = "1.0.0",
) -> tuple[AgentContract, SignalForecastAgent]:
    contract = forecast_contract(
        agent_id=agent_id,
        role=AgentRole.SPECIALIST,
        vertical=AgentVertical.CRYPTO,
        market_types=market_types,
        clock_domain=clock_domain,
        calibration_identity=calibration_identity,
        source_family=source_family,
        version=version,
        fail_closed_on=(
            "missing_market",
            "missing_spot",
            "invalid_volatility",
            "stale_market",
        ),
    )
    return contract, SignalForecastAgent(contract, source.generate)


def build_mlb_specialist_agent(
    specialist: Any,
    *,
    agent_id: str,
    market_types: tuple[str, ...] = ("winner",),
    clock_domain: ClockDomain = ClockDomain.PREGAME,
    version: str = "1.0.0",
) -> tuple[AgentContract, SignalForecastAgent]:
    contract = forecast_contract(
        agent_id=agent_id,
        role=AgentRole.SPECIALIST,
        vertical=AgentVertical.MLB,
        market_types=market_types,
        clock_domain=clock_domain,
        calibration_identity="mlb-incumbent-v1",
        source_family="mlb-structural",
        version=version,
        fail_closed_on=(
            "missing_game_identity",
            "stale_lineup",
            "unknown_starter",
            "specialist_abstained",
        ),
    )
    return contract, SignalForecastAgent(contract, specialist.forecast)


class SignalForecastAgent:
    """Mirror one incumbent Signal into the vNext forecast protocol."""

    def __init__(
        self,
        contract: AgentContract,
        forecast: Callable[[MarketView], Signal | None],
    ) -> None:
        if MessageType.FORECAST not in contract.output_types:
            raise ValueError("signal adapter contract must emit FORECAST")
        self.contract = contract
        self.forecast = forecast

    def __call__(self, invocation: AgentInvocation) -> MessageEnvelope | None:
        observation = _only_message(invocation, MessageType.OBSERVATION)
        market = market_view_from_observation(observation)
        signal = self.forecast(market)
        if signal is None:
            return None
        if signal.market_ticker != market.ticker:
            raise ValueError("incumbent signal market differs from input")
        probability = float(signal.probability_yes)
        uncertainty = float(signal.uncertainty)
        if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
            raise ValueError("incumbent signal probability is invalid")
        if not math.isfinite(uncertainty) or not 0.0 <= uncertainty <= 0.5:
            raise ValueError("incumbent signal uncertainty is invalid")
        if not signal.source.strip() or not signal.rationale.strip():
            raise ValueError("incumbent signal identity and rationale are required")
        source_model_version = str(
            signal.features.get("model_version", self.contract.version)
        )
        return MessageEnvelope.create(
            message_type=MessageType.FORECAST,
            sender=self.contract.agent_id,
            market_id=market.ticker,
            issued_at=invocation.invoked_at,
            effective_time=observation.effective_time,
            received_at=invocation.invoked_at,
            model_version=source_model_version,
            policy_version=invocation.policy_version,
            evidence_ids=(observation.message_id,),
            limitations=("incumbent_adapter", "shadow_only"),
            payload={
                "probability": probability,
                "uncertainty": uncertainty,
                "rationale": signal.rationale,
                "features": signal.features,
                "incumbent_source": signal.source,
                "calibration_identity": self.contract.calibration_identity,
                "source_family": self.contract.source_family,
                "adapter_version": self.contract.version,
            },
        )


class CalibrationAgent:
    """Proposal-only calibration view; it never rewrites a base forecast."""

    def __init__(
        self,
        contract: AgentContract,
        calibrate: Callable[[float, str], float | None],
        *,
        map_version: str,
    ) -> None:
        if contract.role is not AgentRole.CALIBRATOR:
            raise ValueError("calibration adapter requires CALIBRATOR role")
        self.contract = contract
        self.calibrate = calibrate
        self.map_version = map_version

    def __call__(self, invocation: AgentInvocation) -> MessageEnvelope | None:
        base = _only_message(invocation, MessageType.FORECAST)
        probability = float(base.payload["probability"])
        calibrated = self.calibrate(probability, invocation.market_type)
        if calibrated is None:
            return None
        if not 0.0 <= calibrated <= 1.0:
            raise ValueError("calibrator returned probability outside [0, 1]")
        return MessageEnvelope.create(
            message_type=MessageType.CALIBRATION_UPDATE,
            sender=self.contract.agent_id,
            market_id=invocation.market_id,
            issued_at=invocation.invoked_at,
            effective_time=base.effective_time,
            received_at=invocation.invoked_at,
            model_version=self.map_version,
            policy_version=invocation.policy_version,
            evidence_ids=(base.message_id,),
            limitations=("proposal_only", "does_not_rewrite_base_forecast"),
            payload={
                "base_forecast_id": base.message_id,
                "original_probability": probability,
                "calibrated_probability": calibrated,
                "calibration_identity": self.contract.calibration_identity,
                "map_version": self.map_version,
            },
        )


@dataclass(frozen=True, slots=True)
class ShadowFillRecord:
    market_id: str
    decision_id: str
    fill_count: int
    fill_price_cents: int
    observed_at: datetime
    witness_type: str
    source_reference: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", _utc(self.observed_at))
        if not self.market_id.strip() or not self.decision_id.strip():
            raise ValueError("shadow fill identifiers must be non-empty")
        if self.fill_count <= 0 or not 1 <= self.fill_price_cents <= 99:
            raise ValueError("shadow fill count and price must be valid")
        if not self.witness_type.strip() or not self.source_reference.strip():
            raise ValueError("shadow fill witness must be explicit")


def shadow_fill_observation(
    record: ShadowFillRecord,
    *,
    sender: str,
    received_at: datetime,
    policy_version: str,
) -> MessageEnvelope:
    return MessageEnvelope.create(
        message_type=MessageType.OBSERVATION,
        sender=sender,
        market_id=record.market_id,
        issued_at=record.observed_at,
        effective_time=record.observed_at,
        received_at=received_at,
        model_version="shadow-fill-witness-v1",
        policy_version=policy_version,
        evidence_ids=(record.source_reference,),
        payload={
            "observation_kind": "shadow_fill",
            "decision_id": record.decision_id,
            "fill_count": record.fill_count,
            "fill_price_cents": record.fill_price_cents,
            "witness_type": record.witness_type,
            "source_reference": record.source_reference,
            "lane": "shadow",
            "evidence_class": "simulated",
            "realized": False,
        },
    )


class ShadowExecutionTruthAgent:
    def __init__(self, contract: AgentContract) -> None:
        self.contract = contract

    def __call__(self, invocation: AgentInvocation) -> MessageEnvelope | None:
        observation = _only_message(invocation, MessageType.OBSERVATION)
        payload = observation.payload
        if payload.get("observation_kind") != "shadow_fill":
            return None
        if (
            payload.get("lane") != "shadow"
            or payload.get("evidence_class") != "simulated"
            or payload.get("realized") is not False
        ):
            raise ValueError("shadow evidence cannot masquerade as realized")
        fill_count = int(payload.get("fill_count", 0))
        fill_price = int(payload.get("fill_price_cents", 0))
        witness_type = str(payload.get("witness_type", ""))
        if fill_count <= 0 or not 1 <= fill_price <= 99 or not witness_type.strip():
            raise ValueError("shadow fill evidence is malformed")
        return MessageEnvelope.create(
            message_type=MessageType.FILL_EVIDENCE,
            sender=self.contract.agent_id,
            market_id=invocation.market_id,
            issued_at=invocation.invoked_at,
            effective_time=observation.effective_time,
            received_at=invocation.invoked_at,
            model_version=self.contract.version,
            policy_version=invocation.policy_version,
            evidence_ids=(observation.message_id,),
            limitations=("shadow_only", "not_realized_execution"),
            payload={
                "decision_id": payload["decision_id"],
                "fill_count": fill_count,
                "fill_price_cents": fill_price,
                "witness_type": witness_type,
                "lane": "shadow",
                "evidence_class": "simulated",
                "realized": False,
            },
        )


@dataclass(frozen=True, slots=True)
class SettlementRecord:
    market_id: str
    result_yes: bool
    settled_at: datetime
    source: str
    source_reference: str
    verified: bool
    lane: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "settled_at", _utc(self.settled_at))
        if not self.market_id.strip() or not self.source.strip():
            raise ValueError("settlement identifiers must be non-empty")
        if not self.source_reference.strip():
            raise ValueError("settlement source reference must be non-empty")
        if self.lane not in {"shadow", "live"}:
            raise ValueError("settlement lane must be shadow or live")


def settlement_observation(
    record: SettlementRecord,
    *,
    sender: str,
    received_at: datetime,
    policy_version: str,
) -> MessageEnvelope:
    return MessageEnvelope.create(
        message_type=MessageType.OBSERVATION,
        sender=sender,
        market_id=record.market_id,
        issued_at=record.settled_at,
        effective_time=record.settled_at,
        received_at=received_at,
        model_version="settlement-observer-v1",
        policy_version=policy_version,
        evidence_ids=(record.source_reference,),
        payload={
            "observation_kind": "settlement",
            "result_yes": record.result_yes,
            "source": record.source,
            "source_reference": record.source_reference,
            "verified": record.verified,
            "lane": record.lane,
        },
    )


class SettlementGraderAgent:
    def __init__(self, contract: AgentContract) -> None:
        self.contract = contract

    def __call__(self, invocation: AgentInvocation) -> MessageEnvelope | None:
        observation = _only_message(invocation, MessageType.OBSERVATION)
        payload = observation.payload
        if payload.get("observation_kind") != "settlement":
            return None
        if payload.get("verified") is not True:
            return None
        source = str(payload.get("source", ""))
        source_reference = str(payload.get("source_reference", ""))
        lane = str(payload.get("lane", ""))
        if not source.strip() or not source_reference.strip():
            raise ValueError("verified settlement is missing source evidence")
        if lane not in {"shadow", "live"}:
            raise ValueError("verified settlement has invalid lane")
        return MessageEnvelope.create(
            message_type=MessageType.SETTLEMENT,
            sender=self.contract.agent_id,
            market_id=invocation.market_id,
            issued_at=invocation.invoked_at,
            effective_time=observation.effective_time,
            received_at=invocation.invoked_at,
            model_version=self.contract.version,
            policy_version=invocation.policy_version,
            evidence_ids=(observation.message_id,),
            payload={
                "result_yes": payload["result_yes"],
                "source": source,
                "source_reference": source_reference,
                "verified": True,
                "lane": lane,
            },
        )


def calibration_contract(
    *,
    agent_id: str,
    vertical: AgentVertical,
    market_types: tuple[str, ...],
    clock_domain: ClockDomain,
    calibration_identity: str,
    version: str,
    dependencies: tuple[str, ...],
) -> AgentContract:
    return AgentContract(
        agent_id=agent_id,
        role=AgentRole.CALIBRATOR,
        vertical=vertical,
        supported_market_types=market_types,
        input_types=(MessageType.FORECAST,),
        output_types=(MessageType.CALIBRATION_UPDATE,),
        clock_domain=clock_domain,
        authority=Authority.MODEL,
        evidence_requirements=("base_forecast",),
        fail_closed_on=("missing_map", "outside_calibration_scope"),
        budget=AgentBudget(max_messages_per_invocation=1),
        calibration_identity=calibration_identity,
        source_family="calibration",
        version=version,
        dependencies=dependencies,
    )


def truth_contract(
    *,
    agent_id: str,
    role: AgentRole,
    output_type: MessageType,
    evidence_requirement: str,
    fail_closed_on: tuple[str, ...],
    version: str,
) -> AgentContract:
    return AgentContract(
        agent_id=agent_id,
        role=role,
        vertical=AgentVertical.SYSTEM,
        supported_market_types=("*",),
        input_types=(MessageType.OBSERVATION,),
        output_types=(output_type,),
        clock_domain=ClockDomain.SETTLEMENT,
        authority=Authority.OBSERVE,
        evidence_requirements=(evidence_requirement,),
        fail_closed_on=fail_closed_on,
        budget=AgentBudget(max_messages_per_invocation=1),
        calibration_identity=f"{agent_id}-truth",
        source_family="execution-settlement-truth",
        version=version,
    )
