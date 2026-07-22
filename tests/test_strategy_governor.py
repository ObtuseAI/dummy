from datetime import datetime, timezone
from decimal import Decimal

import pytest

from core.ontology import ComplianceVerdict, ForecastOpinion, StrategyCritique
from strategies.governor import (
    CapImpact,
    GovernorDecision,
    MarketQualityScores,
    RiskCritique,
    StrategyGovernor,
    generate_strategy_governor_reports,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _base_opinion(
    market_ticker: str = "MKT",
    contract_ticker: str = "MKT-YES",
    liquidity: float = 0.80,
    spread: float = 0.80,
    freshness: float = 0.95,
    settlement_risk: float = 0.10,
    confidence: float = 0.80,
) -> ForecastOpinion:
    now = _now()
    return ForecastOpinion(
        market_ticker=market_ticker,
        contract_ticker=contract_ticker,
        forecast_reference=f"forecast_{market_ticker}_{contract_ticker}",
        market_implied_probability=Decimal("0.5000"),
        dummy_probability=Decimal("0.5500"),
        probability_delta=Decimal("0.0500"),
        confidence_score=Decimal(str(confidence)),
        uncertainty_band=(Decimal("0.50"), Decimal("0.60")),
        model_summary="test",
        reasoning="test fixture",
        no_trade_reason=None,
        calibration_notes=[
            f"liquidity_score={liquidity}",
            f"spread_score={spread}",
            f"freshness_score={freshness}",
            f"depth_score={freshness}",
            f"settlement_risk_score={settlement_risk}",
        ],
        timestamp=now,
        expiration=now,
        proof_reference=f"proof_{market_ticker}_{contract_ticker}",
    )


def _base_critique(verdict: str = "proceed") -> StrategyCritique:
    return StrategyCritique(
        strategy_family="probability_disagreement",
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        verdict=verdict,
        edge_assessment="positive",
        risk_assessment="low",
        confidence_adjustment=Decimal("0.0"),
        reasoning="test critique",
        timestamp=_now(),
        proof_reference="critique_1",
    )


def _base_risk(verdict: str = "proceed", risk_level: str = "low") -> RiskCritique:
    return RiskCritique(verdict=verdict, risk_level=risk_level, reasoning="test risk", proof_reference="risk_1")


def test_poor_liquidity_blocks():
    gov = StrategyGovernor()
    opinion = _base_opinion(liquidity=0.10)
    out = gov.evaluate(opinion)
    assert out.decision == GovernorDecision.NO_TRADE
    assert "poor_liquidity" in out.blocked_by


def test_wide_spread_blocks():
    gov = StrategyGovernor()
    opinion = _base_opinion(spread=0.10)
    out = gov.evaluate(opinion)
    assert out.decision == GovernorDecision.NO_TRADE
    assert "wide_spread" in out.blocked_by


def test_stale_data_blocks():
    gov = StrategyGovernor()
    opinion = _base_opinion(freshness=0.10)
    out = gov.evaluate(opinion)
    assert out.decision == GovernorDecision.NO_TRADE
    assert "stale_data" in out.blocked_by


def test_missing_quality_is_unknown_not_measured_bad():
    opinion = _base_opinion()
    opinion.calibration_notes = []
    out = StrategyGovernor().evaluate(opinion)
    assert out.decision == GovernorDecision.REQUIRE_MORE_EVIDENCE
    assert out.blocked_by == ["missing_quality_evidence"]


def test_equity_target_is_quarantined_before_other_governor_evidence():
    opinion = _base_opinion(
        market_ticker="KXTSLA-26JUL22-B350",
        contract_ticker="KXTSLA-26JUL22-B350",
    )
    opinion.calibration_notes = []

    out = StrategyGovernor().evaluate(opinion)

    assert out.decision == GovernorDecision.NO_TRADE
    assert out.blocked_by == ["prediction_target_quarantine"]


def test_structured_equity_category_is_quarantined_for_opaque_ticker():
    out = StrategyGovernor().evaluate(
        _base_opinion(),
        market_category="Equities",
    )

    assert out.decision == GovernorDecision.NO_TRADE
    assert out.blocked_by == ["prediction_target_quarantine"]


def test_missing_proof_requires_more_evidence():
    gov = StrategyGovernor()
    opinion = _base_opinion()
    opinion.proof_reference = ""
    out = gov.evaluate(opinion, strategy_critique=_base_critique())
    assert out.decision == GovernorDecision.REQUIRE_MORE_EVIDENCE
    assert "missing_proof" in out.blocked_by


def test_low_calibration_confidence_requires_more_evidence():
    gov = StrategyGovernor()
    opinion = _base_opinion()
    out = gov.evaluate(opinion, calibration_confidence=0.10)
    assert out.decision == GovernorDecision.REQUIRE_MORE_EVIDENCE
    assert "low_calibration_confidence" in out.blocked_by


def test_high_settlement_risk_requires_operator_review():
    gov = StrategyGovernor()
    opinion = _base_opinion(settlement_risk=0.75)
    out = gov.evaluate(opinion, risk_critique=_base_risk(risk_level="high"))
    assert out.decision == GovernorDecision.REQUIRE_OPERATOR_REVIEW


def test_critical_settlement_risk_blocks():
    gov = StrategyGovernor()
    opinion = _base_opinion(settlement_risk=0.90)
    out = gov.evaluate(opinion, risk_critique=_base_risk(risk_level="critical"))
    assert out.decision == GovernorDecision.NO_TRADE


def test_high_disagreement_requires_minimax_review():
    gov = StrategyGovernor()
    opinion = _base_opinion()
    out = gov.evaluate(opinion, disagreement_score=0.40)
    assert out.decision == GovernorDecision.REQUIRE_MINIMAX_REVIEW
    assert out.no_trade_bias == pytest.approx(0.40)


def test_extreme_disagreement_blocks():
    gov = StrategyGovernor()
    opinion = _base_opinion()
    out = gov.evaluate(opinion, disagreement_score=0.60)
    assert out.decision == GovernorDecision.NO_TRADE
    assert "extreme_disagreement" in out.blocked_by


def test_strategy_critique_block():
    gov = StrategyGovernor()
    opinion = _base_opinion()
    out = gov.evaluate(opinion, strategy_critique=_base_critique(verdict="block"))
    assert out.decision == GovernorDecision.NO_TRADE
    assert "strategy_critique_block" in out.blocked_by


def test_compliance_fail_blocks():
    gov = StrategyGovernor()
    opinion = _base_opinion()
    compliance = ComplianceVerdict(passed=False, blocked_categories=["test"], reason="test block")
    out = gov.evaluate(opinion, compliance_verdict=compliance)
    assert out.decision == GovernorDecision.NO_TRADE
    assert "compliance_block" in out.blocked_by


def test_cap_breach_blocks():
    gov = StrategyGovernor()
    opinion = _base_opinion()
    cap = CapImpact(would_breach_single_order=True)
    out = gov.evaluate(opinion, cap_impact=cap)
    assert out.decision == GovernorDecision.NO_TRADE
    assert "cap_breach" in out.blocked_by


def test_model_output_firewall_block_converts_to_no_trade():
    gov = StrategyGovernor()
    opinion = _base_opinion()
    out = gov.evaluate(opinion, model_output_firewall_blocked=True)
    assert out.decision == GovernorDecision.NO_TRADE
    assert "model_output_firewall_block" in out.blocked_by


def test_healthy_approves_for_rehearsal():
    gov = StrategyGovernor()
    opinion = _base_opinion()
    out = gov.evaluate(
        opinion,
        strategy_critique=_base_critique("proceed"),
        risk_critique=_base_risk("proceed", "low"),
        calibration_confidence=0.75,
        disagreement_score=0.05,
    )
    assert out.decision == GovernorDecision.APPROVE_FOR_FIREWALL_REHEARSAL
    assert out.no_trade_bias == pytest.approx(0.05)


def test_quality_scores_parsed_from_opinion():
    opinion = _base_opinion(liquidity=0.20, spread=0.90, freshness=0.95, settlement_risk=0.10)
    scores = MarketQualityScores.from_opinion(opinion)
    assert scores.liquidity_score == pytest.approx(0.20)
    assert scores.spread_score == pytest.approx(0.90)


def test_generate_reports_creates_files(tmp_path):
    paths = generate_strategy_governor_reports(artifact_dir=str(tmp_path))
    assert paths["report"].exists()
    assert paths["manifest"].exists()
    report = __import__("json").loads(paths["report"].read_text())
    assert report["report_type"] == "strategy_governor_report_v1"
    assert report["verdict"] == "PASS"
    assert any(d["decision"] == "APPROVE_FOR_FIREWALL_REHEARSAL" for d in report["decisions"])
