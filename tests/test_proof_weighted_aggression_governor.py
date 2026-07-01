"""Tests for the proof-weighted aggression governor."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from core.ontology import ForecastOpinion
from predator_mesh.aggression.governor import ProofWeightedAggressionGovernor
from predator_mesh.aggression.models import AggressionDecision
from predator_mesh.data_inflow.scoring import DataSourceScore, SourceTier
from predator_mesh.edge.models import EdgeCandidate, EdgeDecision, EdgeScore, MarketTerrainSnapshot
from predator_mesh.signals.models import NormalizedSignal, SignalType
from strategies.governor import (
    CapImpact,
    GovernorDecision,
    StrategyGovernor,
    StrategyGovernorOutput,
)


def _edge_candidate(composite: float = 0.8) -> EdgeCandidate:
    return EdgeCandidate(
        signals=[
            NormalizedSignal(
                signal_type=SignalType.PRICE_MOVE,
                strength=0.8,
                confidence=0.9,
            )
        ],
        terrain=MarketTerrainSnapshot(),
        score=EdgeScore(composite=composite),
        decision=EdgeDecision.ATTACK_REHEARSAL,
    )


def _source_scores(tier: SourceTier = SourceTier.PROMOTE) -> list[DataSourceScore]:
    return [
        DataSourceScore(
            source_id="src-1",
            reliability_score=0.9,
            freshness_score=0.9,
            latency_score=0.9,
            uniqueness_score=0.9,
            edge_contribution_score=0.9,
            composite_score=0.9,
            tier=tier,
        )
    ]


def _governor_output(decision: GovernorDecision = GovernorDecision.APPROVE_FOR_FIREWALL_REHEARSAL) -> StrategyGovernorOutput:
    return StrategyGovernorOutput(
        decision=decision,
        reason="fixture",
        no_trade_bias=0.0,
        blocked_by=[],
        proof_reference="gov_fixture",
    )


def test_attack_when_all_signals_are_strong() -> None:
    gov = ProofWeightedAggressionGovernor()
    allocation = gov.allocate(
        edge_candidate=_edge_candidate(0.98),
        source_scores=_source_scores(SourceTier.PROMOTE),
        forecast_confidence=0.98,
        model_agreement=0.98,
        calibration_support=0.98,
        liquidity_score=0.98,
        spread_score=0.98,
        settlement_risk_score=0.02,
        cap_impact=CapImpact(),
        no_trade_pressure=0.0,
        timeout_pressure=0.0,
        source_decay=0.0,
        governor_output=_governor_output(GovernorDecision.APPROVE_FOR_FIREWALL_REHEARSAL),
    )
    assert allocation.decision == AggressionDecision.ATTACK
    assert allocation.size_pct > 0.5
    assert allocation.confidence > 0.5
    assert not allocation.blocked_by


def test_pass_when_governor_says_no_trade() -> None:
    gov = ProofWeightedAggressionGovernor()
    allocation = gov.allocate(
        edge_candidate=_edge_candidate(0.9),
        source_scores=_source_scores(SourceTier.PROMOTE),
        forecast_confidence=0.9,
        governor_output=_governor_output(GovernorDecision.NO_TRADE),
    )
    assert allocation.decision == AggressionDecision.PASS
    assert allocation.size_pct == pytest.approx(0.0)
    assert "governor_no_trade" in allocation.blocked_by


def test_pass_when_cap_would_breach() -> None:
    gov = ProofWeightedAggressionGovernor()
    allocation = gov.allocate(
        edge_candidate=_edge_candidate(0.9),
        forecast_confidence=0.9,
        cap_impact=CapImpact(would_breach_single_order=True),
    )
    assert allocation.decision == AggressionDecision.PASS
    assert "cap_breach" in allocation.blocked_by


def test_reduce_when_model_disagreement_is_high() -> None:
    gov = ProofWeightedAggressionGovernor()
    allocation = gov.allocate(
        edge_candidate=_edge_candidate(0.8),
        source_scores=_source_scores(SourceTier.PROMOTE),
        forecast_confidence=0.8,
        model_agreement=0.6,
        calibration_support=0.8,
        liquidity_score=0.8,
        spread_score=0.8,
        settlement_risk_score=0.1,
    )
    assert allocation.decision in {AggressionDecision.REDUCE, AggressionDecision.HOLD, AggressionDecision.PASS}
    assert allocation.size_pct < 0.8


def test_pass_when_extreme_model_disagreement() -> None:
    gov = ProofWeightedAggressionGovernor()
    allocation = gov.allocate(
        edge_candidate=_edge_candidate(0.9),
        forecast_confidence=0.9,
        model_agreement=0.3,
    )
    assert allocation.decision == AggressionDecision.PASS
    assert "extreme_model_disagreement" in allocation.blocked_by


def test_escalate_when_governor_requires_review() -> None:
    gov = ProofWeightedAggressionGovernor()
    allocation = gov.allocate(
        edge_candidate=_edge_candidate(0.8),
        forecast_confidence=0.8,
        model_agreement=0.9,
        governor_output=_governor_output(GovernorDecision.REQUIRE_OPERATOR_REVIEW),
    )
    assert allocation.decision == AggressionDecision.ESCALATE


def test_poor_liquidity_blocks_attack() -> None:
    gov = ProofWeightedAggressionGovernor()
    allocation = gov.allocate(
        edge_candidate=_edge_candidate(0.9),
        forecast_confidence=0.9,
        liquidity_score=0.1,
        spread_score=0.9,
    )
    assert allocation.decision == AggressionDecision.PASS
    assert "poor_liquidity" in allocation.blocked_by


def test_wide_spread_blocks_attack() -> None:
    gov = ProofWeightedAggressionGovernor()
    allocation = gov.allocate(
        edge_candidate=_edge_candidate(0.9),
        forecast_confidence=0.9,
        liquidity_score=0.9,
        spread_score=0.1,
    )
    assert allocation.decision == AggressionDecision.PASS
    assert "wide_spread" in allocation.blocked_by


def test_critical_settlement_risk_blocks() -> None:
    gov = ProofWeightedAggressionGovernor()
    allocation = gov.allocate(
        edge_candidate=_edge_candidate(0.9),
        forecast_confidence=0.9,
        settlement_risk_score=0.9,
    )
    assert allocation.decision == AggressionDecision.PASS
    assert "critical_settlement_risk" in allocation.blocked_by


def test_no_trade_pressure_reduces_size() -> None:
    gov = ProofWeightedAggressionGovernor()
    strong = gov.allocate(
        edge_candidate=_edge_candidate(0.9),
        forecast_confidence=0.9,
        no_trade_pressure=0.0,
    )
    pressured = gov.allocate(
        edge_candidate=_edge_candidate(0.9),
        forecast_confidence=0.9,
        no_trade_pressure=0.5,
    )
    assert pressured.size_pct < strong.size_pct


def test_timeout_pressure_reduces_size() -> None:
    gov = ProofWeightedAggressionGovernor()
    strong = gov.allocate(
        edge_candidate=_edge_candidate(0.9),
        forecast_confidence=0.9,
        timeout_pressure=0.0,
    )
    pressured = gov.allocate(
        edge_candidate=_edge_candidate(0.9),
        forecast_confidence=0.9,
        timeout_pressure=0.5,
    )
    assert pressured.size_pct < strong.size_pct


def test_source_decay_reduces_size() -> None:
    gov = ProofWeightedAggressionGovernor()
    fresh = gov.allocate(
        edge_candidate=_edge_candidate(0.9),
        forecast_confidence=0.9,
        source_decay=0.0,
    )
    decayed = gov.allocate(
        edge_candidate=_edge_candidate(0.9),
        forecast_confidence=0.9,
        source_decay=0.5,
    )
    assert decayed.size_pct < fresh.size_pct


def test_source_decay_half_life() -> None:
    """Source decay follows exponential half-life semantics."""
    gov = ProofWeightedAggressionGovernor()
    base = gov.allocate(
        edge_candidate=_edge_candidate(0.9),
        forecast_confidence=0.9,
        source_decay=0.0,
    )
    half_life = gov.allocate(
        edge_candidate=_edge_candidate(0.9),
        forecast_confidence=0.9,
        source_decay=ProofWeightedAggressionGovernor.SOURCE_DECAY_HALF_LIFE,
    )
    two_half_lives = gov.allocate(
        edge_candidate=_edge_candidate(0.9),
        forecast_confidence=0.9,
        source_decay=2.0 * ProofWeightedAggressionGovernor.SOURCE_DECAY_HALF_LIFE,
    )

    assert base.size_pct == pytest.approx(half_life.size_pct * 2.0, rel=1e-9)
    assert base.size_pct == pytest.approx(two_half_lives.size_pct * 4.0, rel=1e-9)
    assert half_life.size_pct == pytest.approx(two_half_lives.size_pct * 2.0, rel=1e-9)


def test_pruned_sources_without_promoted_collapse_quality() -> None:
    gov = ProofWeightedAggressionGovernor()
    allocation = gov.allocate(
        edge_candidate=_edge_candidate(0.9),
        source_scores=_source_scores(SourceTier.PRUNE),
        forecast_confidence=0.9,
    )
    assert allocation.decision == AggressionDecision.PASS


def test_low_forecast_confidence_blocks() -> None:
    gov = ProofWeightedAggressionGovernor()
    allocation = gov.allocate(
        edge_candidate=_edge_candidate(0.9),
        forecast_confidence=0.1,
    )
    assert allocation.decision == AggressionDecision.PASS
    assert "low_forecast_confidence" in allocation.blocked_by


def test_low_calibration_support_blocks() -> None:
    gov = ProofWeightedAggressionGovernor()
    allocation = gov.allocate(
        edge_candidate=_edge_candidate(0.9),
        forecast_confidence=0.9,
        calibration_support=0.1,
    )
    assert allocation.decision == AggressionDecision.PASS
    assert "low_calibration_support" in allocation.blocked_by


def test_no_edge_candidate_uses_default_base() -> None:
    gov = ProofWeightedAggressionGovernor()
    allocation = gov.allocate(
        forecast_confidence=0.9,
        model_agreement=0.9,
        calibration_support=0.9,
        liquidity_score=0.9,
        spread_score=0.9,
        settlement_risk_score=0.1,
    )
    assert allocation.size_pct > 0.0
    assert allocation.decision in {
        AggressionDecision.HOLD,
        AggressionDecision.ATTACK,
        AggressionDecision.REDUCE,
        AggressionDecision.PASS,
    }


def test_meta_contains_key_inputs() -> None:
    gov = ProofWeightedAggressionGovernor()
    allocation = gov.allocate(
        edge_candidate=_edge_candidate(0.8),
        source_scores=_source_scores(SourceTier.PROMOTE),
        forecast_confidence=0.8,
        model_agreement=0.9,
        calibration_support=0.8,
        liquidity_score=0.8,
        spread_score=0.8,
        settlement_risk_score=0.1,
        no_trade_pressure=0.1,
        timeout_pressure=0.0,
        source_decay=0.0,
    )
    meta = allocation.meta
    assert meta["edge_candidate_id"] is not None
    assert meta["source_count"] == 1
    assert meta["forecast_confidence"] == pytest.approx(0.8)
    assert meta["model_agreement"] == pytest.approx(0.9)
    assert meta["calibration_support"] == pytest.approx(0.8)
    assert meta["liquidity_score"] == pytest.approx(0.8)
    assert meta["spread_score"] == pytest.approx(0.8)
    assert meta["settlement_risk_score"] == pytest.approx(0.1)
    assert meta["no_trade_pressure"] == pytest.approx(0.1)


def test_allocate_with_real_strategy_governor_output() -> None:
    """The aggression governor can consume the real StrategyGovernor output."""
    from core.ontology import StrategyCritique
    from strategies.governor import RiskCritique

    now = datetime.now(timezone.utc)
    opinion = ForecastOpinion(
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        forecast_reference="forecast_1",
        market_implied_probability=Decimal("0.5000"),
        dummy_probability=Decimal("0.5500"),
        probability_delta=Decimal("0.0500"),
        confidence_score=Decimal("0.80"),
        uncertainty_band=(Decimal("0.50"), Decimal("0.60")),
        model_summary="test",
        reasoning="integration fixture",
        no_trade_reason=None,
        calibration_notes=[
            "liquidity_score=0.80",
            "spread_score=0.80",
            "freshness_score=0.95",
            "depth_score=0.95",
            "settlement_risk_score=0.10",
        ],
        timestamp=now,
        expiration=now,
        proof_reference="proof_1",
    )
    strategy_critique = StrategyCritique(
        strategy_family="probability_disagreement",
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        verdict="proceed",
        edge_assessment="positive",
        risk_assessment="low",
        confidence_adjustment=Decimal("0.0"),
        reasoning="clean signal",
        timestamp=now,
        proof_reference="critique_1",
    )
    risk_critique = RiskCritique(
        verdict="proceed", risk_level="low", reasoning="low risk", proof_reference="risk_1"
    )
    strategy_gov = StrategyGovernor()
    gov_output = strategy_gov.evaluate(
        opinion,
        strategy_critique=strategy_critique,
        risk_critique=risk_critique,
        calibration_confidence=0.75,
        disagreement_score=0.05,
    )

    agg_gov = ProofWeightedAggressionGovernor()
    allocation = agg_gov.allocate(
        edge_candidate=_edge_candidate(0.98),
        source_scores=_source_scores(SourceTier.PROMOTE),
        forecast_confidence=0.95,
        model_agreement=0.95,
        calibration_support=0.9,
        liquidity_score=0.9,
        spread_score=0.9,
        settlement_risk_score=0.05,
        governor_output=gov_output,
    )
    assert allocation.decision in {AggressionDecision.ATTACK, AggressionDecision.HOLD}
    assert allocation.meta["governor_decision"] == "APPROVE_FOR_FIREWALL_REHEARSAL"
