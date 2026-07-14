from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals import crypto_spot as crypto_spot_module
from autonomy.signals.crypto_spot import CryptoSpotVolSignal
from autonomy.signals.market_prior import MarketPriorSignal
from dummy.agents import (
    AgentInvocation,
    AgentContract,
    AgentRole,
    AgentRuntime,
    AgentVertical,
    CalibrationAgent,
    InvocationStatus,
    SettlementGraderAgent,
    SettlementRecord,
    ShadowExecutionTruthAgent,
    ShadowFillRecord,
    SignalForecastAgent,
    build_crypto_signal_agent,
    build_market_prior_agent,
    build_mlb_specialist_agent,
    build_phase2_runtime,
    calibration_contract,
    forecast_contract,
    market_view_from_observation,
    market_view_observation,
    settlement_observation,
    shadow_fill_observation,
    phase2_catalog_digest,
    phase2_catalog_manifest,
    phase2_contract_catalog,
    truth_contract,
)
from dummy.chronos import ClockDomain
from dummy.protocols import MessageEnvelope, MessageType


NOW = datetime(2026, 7, 14, 22, 0, tzinfo=timezone.utc)
POLICY = "vnext-shadow-1"
OBSERVER = "market-observer-v1"


def _market(
    *,
    ticker: str = "KXBTC15M-26JUL142215-15",
    vertical: Vertical = Vertical.CRYPTO,
    close_time: str = "2026-07-14T22:15:00Z",
    raw: dict[str, object] | None = None,
) -> MarketView:
    return MarketView(
        ticker=ticker,
        title="Will BTC be higher?",
        vertical=vertical,
        status="active",
        close_time=close_time,
        yes_bid=48,
        yes_ask=52,
        no_bid=48,
        no_ask=52,
        volume=1_200,
        liquidity=5_000,
        raw=raw or {"strike_type": "greater", "floor_strike": 60_000.0},
    )


def _market_observation(market: MarketView | None = None) -> MessageEnvelope:
    return market_view_observation(
        market or _market(),
        sender=OBSERVER,
        issued_at=NOW,
        effective_time=NOW,
        received_at=NOW,
        model_version="scanner-1",
        policy_version=POLICY,
        evidence_ids=("exchange-snapshot-1",),
    )


def _invocation(
    *,
    agent_id: str,
    message: MessageEnvelope,
    market_type: str,
    clock_domain: ClockDomain,
    evidence_keys: tuple[str, ...],
    invoked_at: datetime = NOW,
) -> AgentInvocation:
    return AgentInvocation.create(
        agent_id=agent_id,
        market_id=message.market_id,
        market_type=market_type,
        clock_domain=clock_domain,
        policy_version=POLICY,
        invoked_at=invoked_at,
        evidence_keys=evidence_keys,
        input_messages=(message,),
    )


def _forecast_contract(
    *,
    agent_id: str,
    vertical: AgentVertical,
    market_type: str,
    clock_domain: ClockDomain,
    role: AgentRole = AgentRole.SPECIALIST,
) -> AgentContract:
    return forecast_contract(
        agent_id=agent_id,
        role=role,
        vertical=vertical,
        market_types=(market_type,),
        clock_domain=clock_domain,
        calibration_identity=f"{agent_id}-cal",
        source_family=f"{agent_id}-family",
        version="1.0.0",
        fail_closed_on=("missing_market", "stale_market", "source_abstained"),
    )


def test_market_view_observation_round_trips_without_mutation() -> None:
    market = _market()
    message = _market_observation(market)
    restored = market_view_from_observation(message)
    assert restored == market
    assert message.message_type is MessageType.OBSERVATION
    assert message.evidence_ids == ("exchange-snapshot-1",)


def test_market_prior_adapter_matches_incumbent_signal() -> None:
    market = _market()
    incumbent = MarketPriorSignal()
    expected = incumbent.generate(market)
    contract, adapter = build_market_prior_agent(
        agent_id="market-prior-v1",
        vertical=AgentVertical.MARKET,
        market_types=("15m_direction",),
        clock_domain=ClockDomain.FIFTEEN_MINUTE,
        source=incumbent,
    )
    message = _market_observation(market)
    output = adapter(
        _invocation(
            agent_id="market-prior-v1",
            message=message,
            market_type="15m_direction",
            clock_domain=ClockDomain.FIFTEEN_MINUTE,
            evidence_keys=("fresh_market_view",),
        )
    )
    assert output is not None and expected is not None
    assert output.payload["probability"] == expected.probability_yes
    assert output.payload["uncertainty"] == expected.uncertainty
    assert output.payload["features"] == expected.features
    assert output.payload["incumbent_source"] == "market_prior"
    assert output.limitations == ("incumbent_adapter", "shadow_only")


def test_crypto_adapter_matches_incumbent_source_on_frozen_market(monkeypatch) -> None:
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW if tz is not None else NOW.replace(tzinfo=None)

    monkeypatch.setattr(crypto_spot_module, "datetime", FrozenDateTime)
    market = _market()
    direct = CryptoSpotVolSignal(fetch_spot_and_vol=lambda _asset: (61_000.0, 0.5))
    adapted = CryptoSpotVolSignal(fetch_spot_and_vol=lambda _asset: (61_000.0, 0.5))
    expected = direct.generate(market)
    contract, adapter = build_crypto_signal_agent(
        adapted,
        agent_id="crypto-spot-v1",
        market_types=("15m_direction",),
        clock_domain=ClockDomain.FIFTEEN_MINUTE,
        calibration_identity="crypto-spot-v1-cal",
        source_family="crypto-coinbase-distribution",
    )
    output = adapter(
        _invocation(
            agent_id="crypto-spot-v1",
            message=_market_observation(market),
            market_type="15m_direction",
            clock_domain=ClockDomain.FIFTEEN_MINUTE,
            evidence_keys=("fresh_market_view",),
        )
    )
    assert output is not None and expected is not None
    assert output.payload["probability"] == expected.probability_yes
    assert output.payload["uncertainty"] == expected.uncertainty
    assert output.payload["features"] == expected.features


def test_mlb_specialist_forecast_method_is_wrapped_without_reinterpretation() -> None:
    market = _market(
        ticker="KXMLBGAME-26JUL14NYYBOS-NYY",
        vertical=Vertical.SPORTS,
        close_time="2026-07-14T23:00:00Z",
        raw={},
    )

    class Specialist:
        def forecast(self, view: MarketView) -> Signal:
            return Signal(
                source="mlb_structural_winner",
                market_ticker=view.ticker,
                probability_yes=0.57,
                uncertainty=0.12,
                rationale="frozen MLB fixture",
                features={"starter_confirmed": True},
            )

    specialist = Specialist()
    contract, adapter = build_mlb_specialist_agent(
        specialist,
        agent_id="mlb-specialist-v1",
    )
    output = adapter(
        _invocation(
            agent_id="mlb-specialist-v1",
            message=_market_observation(market),
            market_type="winner",
            clock_domain=ClockDomain.PREGAME,
            evidence_keys=("fresh_market_view",),
        )
    )
    assert output is not None
    assert output.payload["probability"] == 0.57
    assert output.payload["features"] == {"starter_confirmed": True}
    assert output.payload["incumbent_source"] == "mlb_structural_winner"


def test_calibration_agent_proposes_update_without_rewriting_base() -> None:
    base_contract = _forecast_contract(
        agent_id="market-prior-v1",
        vertical=AgentVertical.MARKET,
        market_type="15m_direction",
        clock_domain=ClockDomain.FIFTEEN_MINUTE,
        role=AgentRole.MARKET_PRIOR,
    )
    base = SignalForecastAgent(base_contract, MarketPriorSignal().generate)(  # type: ignore[arg-type]
        _invocation(
            agent_id="market-prior-v1",
            message=_market_observation(),
            market_type="15m_direction",
            clock_domain=ClockDomain.FIFTEEN_MINUTE,
            evidence_keys=("fresh_market_view",),
        )
    )
    assert base is not None
    contract = calibration_contract(
        agent_id="calibrator-v1",
        vertical=AgentVertical.CRYPTO,
        market_types=("15m_direction",),
        clock_domain=ClockDomain.FIFTEEN_MINUTE,
        calibration_identity="btc-15m-isotonic-v1",
        version="1.0.0",
        dependencies=("market-prior-v1",),
    )
    output = CalibrationAgent(
        contract,
        lambda probability, _scope: probability * 0.9 + 0.05,
        map_version="map-1",
    )(
        _invocation(
            agent_id="calibrator-v1",
            message=base,
            market_type="15m_direction",
            clock_domain=ClockDomain.FIFTEEN_MINUTE,
            evidence_keys=("base_forecast",),
        )
    )
    assert output is not None
    assert output.message_type is MessageType.CALIBRATION_UPDATE
    assert output.payload["base_forecast_id"] == base.message_id
    assert output.payload["original_probability"] == base.payload["probability"]
    assert base.message_type is MessageType.FORECAST
    assert "does_not_rewrite_base_forecast" in output.limitations


def test_shadow_fill_truth_remains_explicitly_simulated() -> None:
    contract = truth_contract(
        agent_id="shadow-execution-truth-v1",
        role=AgentRole.EXECUTION_TRUTH,
        output_type=MessageType.FILL_EVIDENCE,
        evidence_requirement="shadow_fill_witness",
        fail_closed_on=("missing_fill_witness", "realized_label_attempt"),
        version="1.0.0",
    )
    record = ShadowFillRecord(
        market_id=_market().ticker,
        decision_id="decision-1",
        fill_count=2,
        fill_price_cents=51,
        observed_at=NOW,
        witness_type="public_trade_queue_consumed",
        source_reference="shadow-ledger-row-1",
    )
    observation = shadow_fill_observation(
        record,
        sender="shadow-observer-v1",
        received_at=NOW,
        policy_version=POLICY,
    )
    output = ShadowExecutionTruthAgent(contract)(
        _invocation(
            agent_id="shadow-execution-truth-v1",
            message=observation,
            market_type="15m_direction",
            clock_domain=ClockDomain.SETTLEMENT,
            evidence_keys=("shadow_fill_witness",),
        )
    )
    assert output is not None
    assert output.message_type is MessageType.FILL_EVIDENCE
    assert output.payload["lane"] == "shadow"
    assert output.payload["evidence_class"] == "simulated"
    assert output.payload["realized"] is False
    assert "not_realized_execution" in output.limitations


def test_verified_settlement_is_graded_and_unverified_settlement_abstains() -> None:
    contract = truth_contract(
        agent_id="settlement-grader-v1",
        role=AgentRole.SETTLEMENT_GRADER,
        output_type=MessageType.SETTLEMENT,
        evidence_requirement="verified_settlement",
        fail_closed_on=("missing_settlement", "unverified_settlement"),
        version="1.0.0",
    )
    grader = SettlementGraderAgent(contract)
    unverified = SettlementRecord(
        market_id=_market().ticker,
        result_yes=True,
        settled_at=NOW,
        source="exchange-settlement-feed",
        source_reference="settlement-1",
        verified=False,
        lane="shadow",
    )
    observation = settlement_observation(
        unverified,
        sender="settlement-observer-v1",
        received_at=NOW,
        policy_version=POLICY,
    )
    assert grader(
        _invocation(
            agent_id="settlement-grader-v1",
            message=observation,
            market_type="15m_direction",
            clock_domain=ClockDomain.SETTLEMENT,
            evidence_keys=("verified_settlement",),
        )
    ) is None

    verified = SettlementRecord(
        market_id=_market().ticker,
        result_yes=False,
        settled_at=NOW,
        source="exchange-settlement-feed",
        source_reference="settlement-2",
        verified=True,
        lane="shadow",
    )
    verified_observation = settlement_observation(
        verified,
        sender="settlement-observer-v1",
        received_at=NOW,
        policy_version=POLICY,
    )
    output = grader(
        _invocation(
            agent_id="settlement-grader-v1",
            message=verified_observation,
            market_type="15m_direction",
            clock_domain=ClockDomain.SETTLEMENT,
            evidence_keys=("verified_settlement",),
        )
    )
    assert output is not None
    assert output.payload["verified"] is True
    assert output.payload["result_yes"] is False


def test_runtime_fail_closes_when_incumbent_adapter_abstains() -> None:
    contract = _forecast_contract(
        agent_id="mlb-specialist-v1",
        vertical=AgentVertical.MLB,
        market_type="winner",
        clock_domain=ClockDomain.PREGAME,
    )
    runtime = AgentRuntime()
    runtime.register(contract, SignalForecastAgent(contract, lambda _market: None))  # type: ignore[arg-type]
    runtime.seal()
    runtime.activate("mlb-specialist-v1", at=NOW)
    result = runtime.invoke(
        _invocation(
            agent_id="mlb-specialist-v1",
            message=_market_observation(
                _market(
                    ticker="KXMLBGAME-26JUL14NYYBOS-NYY",
                    vertical=Vertical.SPORTS,
                    raw={},
                )
            ),
            market_type="winner",
            clock_domain=ClockDomain.PREGAME,
            evidence_keys=("fresh_market_view",),
        )
    )
    assert result.status is InvocationStatus.ABSTAINED
    assert result.reasons == ("handler_abstained",)


def test_phase2_catalog_is_deterministic_research_only_and_complete() -> None:
    first = phase2_contract_catalog()
    second = phase2_contract_catalog()
    assert [item.to_dict() for item in first] == [item.to_dict() for item in second]
    assert {item.agent_id for item in first} == {
        "btc-market-prior-v1",
        "btc-incumbent-specialist-v1",
        "mlb-incumbent-specialist-v1",
        "btc-calibrator-v1",
        "shadow-execution-truth-v1",
        "settlement-grader-v1",
    }
    assert all(item.authority.name not in {"PAPER_ALLOCATE", "LIVE_PROPOSE", "EXECUTE"} for item in first)
    assert phase2_catalog_manifest()["execution_authority"] is False
    assert phase2_catalog_digest() == phase2_catalog_digest()
    assert len(phase2_catalog_digest()) == 64
    persisted = json.loads(
        Path("docs/VNEXT_PHASE2_CONTRACT_CATALOG.json").read_text(encoding="utf-8")
    )
    assert persisted == phase2_catalog_manifest()


def test_phase2_runtime_build_is_inactive_and_dependency_ordered() -> None:
    class Crypto:
        def generate(self, market: MarketView) -> Signal:
            return Signal(
                source="crypto_spot_vol",
                market_ticker=market.ticker,
                probability_yes=0.55,
                uncertainty=0.1,
                rationale="fixture",
            )

    class Mlb:
        def forecast(self, market: MarketView) -> Signal:
            return Signal(
                source="mlb_structural_winner",
                market_ticker=market.ticker,
                probability_yes=0.57,
                uncertainty=0.12,
                rationale="fixture",
            )

    runtime = build_phase2_runtime(
        crypto_source=Crypto(),
        mlb_specialist=Mlb(),
        calibrate=lambda probability, _scope: probability,
        calibration_map_version="map-1",
    )
    assert runtime.registry.sealed is True
    assert all(
        runtime.lifecycle(agent_id).state.name == "REGISTERED"
        for agent_id in runtime.registry.dependency_order
    )
    for agent_id in runtime.registry.dependency_order:
        runtime.activate(agent_id, at=NOW)
    assert all(
        runtime.lifecycle(agent_id).state.name == "ACTIVE"
        for agent_id in runtime.registry.dependency_order
    )
    assert runtime.mailbox().entries == ()
    assert runtime.mailbox() is runtime.mailbox()
