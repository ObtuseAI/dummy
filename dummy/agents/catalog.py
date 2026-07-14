"""Canonical Phase 2 contract catalog and dependency-injected runtime builder."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from dummy.agents.contract import AgentContract, AgentRole, AgentVertical
from dummy.agents.incumbent import (
    CalibrationAgent,
    SettlementGraderAgent,
    ShadowExecutionTruthAgent,
    SignalForecastAgent,
    calibration_contract,
    forecast_contract,
    truth_contract,
)
from dummy.agents.runtime import AgentRuntime
from dummy.chronos import ClockDomain
from dummy.protocols import MessageType


def phase2_contract_catalog() -> tuple[AgentContract, ...]:
    """Return the frozen first adapter catalog in dependency order."""

    prior = forecast_contract(
        agent_id="btc-market-prior-v1",
        role=AgentRole.MARKET_PRIOR,
        vertical=AgentVertical.MARKET,
        market_types=("15m_direction",),
        clock_domain=ClockDomain.FIFTEEN_MINUTE,
        calibration_identity="market-price-anchor-v1",
        source_family="market-price",
        version="1.0.0",
        fail_closed_on=("missing_book", "stale_market", "crossed_book"),
        max_input_age_ms=30_000,
    )
    crypto = forecast_contract(
        agent_id="btc-incumbent-specialist-v1",
        role=AgentRole.SPECIALIST,
        vertical=AgentVertical.CRYPTO,
        market_types=("15m_direction",),
        clock_domain=ClockDomain.FIFTEEN_MINUTE,
        calibration_identity="btc-incumbent-v1",
        source_family="crypto-coinbase-distribution",
        version="1.0.0",
        fail_closed_on=(
            "missing_market",
            "missing_spot",
            "invalid_volatility",
            "stale_market",
        ),
        max_input_age_ms=30_000,
    )
    mlb = forecast_contract(
        agent_id="mlb-incumbent-specialist-v1",
        role=AgentRole.SPECIALIST,
        vertical=AgentVertical.MLB,
        market_types=("winner",),
        clock_domain=ClockDomain.PREGAME,
        calibration_identity="mlb-incumbent-v1",
        source_family="mlb-structural",
        version="1.0.0",
        fail_closed_on=(
            "missing_game_identity",
            "stale_lineup",
            "unknown_starter",
            "specialist_abstained",
        ),
        max_input_age_ms=120_000,
    )
    calibrator = calibration_contract(
        agent_id="btc-calibrator-v1",
        vertical=AgentVertical.CRYPTO,
        market_types=("15m_direction",),
        clock_domain=ClockDomain.FIFTEEN_MINUTE,
        calibration_identity="btc-15m-calibration-v1",
        version="1.0.0",
        dependencies=(crypto.agent_id,),
    )
    shadow_truth = truth_contract(
        agent_id="shadow-execution-truth-v1",
        role=AgentRole.EXECUTION_TRUTH,
        output_type=MessageType.FILL_EVIDENCE,
        evidence_requirement="shadow_fill_witness",
        fail_closed_on=("missing_fill_witness", "realized_label_attempt"),
        version="1.0.0",
    )
    settlement = truth_contract(
        agent_id="settlement-grader-v1",
        role=AgentRole.SETTLEMENT_GRADER,
        output_type=MessageType.SETTLEMENT,
        evidence_requirement="verified_settlement",
        fail_closed_on=("missing_settlement", "unverified_settlement"),
        version="1.0.0",
    )
    return (prior, crypto, mlb, shadow_truth, settlement, calibrator)


def phase2_catalog_manifest() -> dict[str, object]:
    contracts = phase2_contract_catalog()
    return {
        "schema_version": 1,
        "maturity": "EXPERIMENTAL_SOVEREIGN_FORECASTING",
        "execution_authority": False,
        "promotion_authority": "HUMAN_ONLY",
        "contracts": [contract.to_dict() for contract in contracts],
    }


def phase2_catalog_digest() -> str:
    payload = json.dumps(
        phase2_catalog_manifest(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_phase2_runtime(
    *,
    crypto_source: Any,
    mlb_specialist: Any,
    calibrate: Callable[[float, str], float | None],
    calibration_map_version: str,
) -> AgentRuntime:
    """Build the sealed, inactive Phase 2 runtime with injected incumbents.

    Construction performs no fetch, model call, credential lookup, ledger
    mutation, activation, or execution. Callers activate contracts explicitly
    in ``runtime.registry.dependency_order`` only inside a shadow episode.
    """

    contracts = {item.agent_id: item for item in phase2_contract_catalog()}
    from autonomy.signals.market_prior import MarketPriorSignal

    runtime = AgentRuntime()
    runtime.register(
        contracts["btc-market-prior-v1"],
        SignalForecastAgent(
            contracts["btc-market-prior-v1"],
            MarketPriorSignal().generate,
        ),
    )
    runtime.register(
        contracts["btc-incumbent-specialist-v1"],
        SignalForecastAgent(
            contracts["btc-incumbent-specialist-v1"],
            crypto_source.generate,
        ),
    )
    runtime.register(
        contracts["mlb-incumbent-specialist-v1"],
        SignalForecastAgent(
            contracts["mlb-incumbent-specialist-v1"],
            mlb_specialist.forecast,
        ),
    )
    runtime.register(
        contracts["shadow-execution-truth-v1"],
        ShadowExecutionTruthAgent(contracts["shadow-execution-truth-v1"]),
    )
    runtime.register(
        contracts["settlement-grader-v1"],
        SettlementGraderAgent(contracts["settlement-grader-v1"]),
    )
    runtime.register(
        contracts["btc-calibrator-v1"],
        CalibrationAgent(
            contracts["btc-calibrator-v1"],
            calibrate,
            map_version=calibration_map_version,
        ),
    )
    runtime.seal()
    return runtime
