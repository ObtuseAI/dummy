"""Decision-matrix tests for StrategyGovernor.

Each row exercises a distinct combination of inputs and asserts the expected
``GovernorDecision``. This guards against ordering regressions in the
multi-factor gating logic.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from core.ontology import ComplianceVerdict, ForecastOpinion, HybridReviewResult, StrategyCritique
from strategies.governor import (
    CapImpact,
    GovernorDecision,
    RiskCritique,
    StrategyGovernor,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _opinion(
    liquidity: float = 0.80,
    spread: float = 0.80,
    freshness: float = 0.95,
    settlement_risk: float = 0.10,
    confidence: float = 0.80,
    proof_reference: str = "proof_1",
) -> ForecastOpinion:
    now = _now()
    return ForecastOpinion(
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        forecast_reference="forecast_1",
        market_implied_probability=Decimal("0.5000"),
        dummy_probability=Decimal("0.5500"),
        probability_delta=Decimal("0.0500"),
        confidence_score=Decimal(str(confidence)),
        uncertainty_band=(Decimal("0.50"), Decimal("0.60")),
        model_summary="test",
        reasoning="decision matrix fixture",
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
        proof_reference=proof_reference,
    )


def _critique(verdict: str = "proceed") -> StrategyCritique:
    return StrategyCritique(
        strategy_family="probability_disagreement",
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        verdict=verdict,
        edge_assessment="ok",
        risk_assessment="ok",
        confidence_adjustment=Decimal("0.0"),
        reasoning="fixture",
        timestamp=_now(),
        proof_reference="critique_1",
    )


def _risk(verdict: str = "proceed", risk_level: str = "low") -> RiskCritique:
    return RiskCritique(verdict=verdict, risk_level=risk_level, reasoning="fixture", proof_reference="risk_1")


def _hybrid(verdict: str = "agree") -> HybridReviewResult:
    return HybridReviewResult(
        task="hybrid_review",
        primary={},
        secondary={},
        agreement_score=Decimal("0.9"),
        confidence_adjustment=Decimal("0.0"),
        verdict=verdict,
        reasoning="fixture",
        timestamp=_now(),
        proof_reference="hybrid_1",
    )


@pytest.mark.parametrize(
    "name,kwargs,expected",
    [
        ("approve", {"strategy_critique": _critique("proceed"), "risk_critique": _risk("proceed", "low"), "calibration_confidence": 0.75, "disagreement_score": 0.05}, GovernorDecision.APPROVE_FOR_FIREWALL_REHEARSAL),
        ("poor_liquidity", {"liquidity": 0.10}, GovernorDecision.NO_TRADE),
        ("wide_spread", {"spread": 0.10}, GovernorDecision.NO_TRADE),
        ("stale_data", {"freshness": 0.10}, GovernorDecision.NO_TRADE),
        ("missing_proof", {"proof_reference": ""}, GovernorDecision.REQUIRE_MORE_EVIDENCE),
        ("low_calibration", {"strategy_critique": _critique("proceed"), "calibration_confidence": 0.10}, GovernorDecision.REQUIRE_MORE_EVIDENCE),
        ("strategy_warn", {"strategy_critique": _critique("warn"), "risk_critique": _risk("proceed", "low"), "calibration_confidence": 0.75, "disagreement_score": 0.05}, GovernorDecision.REQUIRE_OPERATOR_REVIEW),
        ("strategy_block", {"strategy_critique": _critique("block")}, GovernorDecision.NO_TRADE),
        ("risk_high", {"strategy_critique": _critique("proceed"), "risk_critique": _risk("warn", "high"), "calibration_confidence": 0.75}, GovernorDecision.REQUIRE_OPERATOR_REVIEW),
        ("risk_critical", {"strategy_critique": _critique("proceed"), "risk_critique": _risk("block", "critical")}, GovernorDecision.NO_TRADE),
        ("high_settlement_score", {"settlement_risk": 0.75, "strategy_critique": _critique("proceed"), "risk_critique": _risk("proceed", "low"), "calibration_confidence": 0.75}, GovernorDecision.REQUIRE_OPERATOR_REVIEW),
        ("critical_settlement_score", {"settlement_risk": 0.90, "strategy_critique": _critique("proceed"), "risk_critique": _risk("proceed", "low"), "calibration_confidence": 0.75}, GovernorDecision.NO_TRADE),
        ("disagreement_review", {"strategy_critique": _critique("proceed"), "risk_critique": _risk("proceed", "low"), "calibration_confidence": 0.75, "disagreement_score": 0.35}, GovernorDecision.REQUIRE_MINIMAX_REVIEW),
        ("extreme_disagreement_block", {"strategy_critique": _critique("proceed"), "risk_critique": _risk("proceed", "low"), "calibration_confidence": 0.75, "disagreement_score": 0.55}, GovernorDecision.NO_TRADE),
        ("hybrid_conflict", {"strategy_critique": _critique("proceed"), "risk_critique": _risk("proceed", "low"), "hybrid_review": _hybrid("disagree"), "calibration_confidence": 0.75, "disagreement_score": 0.05}, GovernorDecision.REQUIRE_MINIMAX_REVIEW),
        ("compliance_block", {"strategy_critique": _critique("proceed"), "compliance_verdict": ComplianceVerdict(passed=False, blocked_categories=["test"], reason="test")}, GovernorDecision.NO_TRADE),
        ("cap_breach", {"strategy_critique": _critique("proceed"), "cap_impact": CapImpact(would_breach_single_order=True)}, GovernorDecision.NO_TRADE),
        ("model_output_firewall", {"model_output_firewall_blocked": True}, GovernorDecision.NO_TRADE),
    ],
)
def test_decision_matrix(name, kwargs, expected):
    gov = StrategyGovernor()
    opinion_kwargs = {}
    evaluate_kwargs = {}
    for key, value in kwargs.items():
        if key in {"liquidity", "spread", "freshness", "settlement_risk", "confidence", "proof_reference"}:
            opinion_kwargs[key] = value
        else:
            evaluate_kwargs[key] = value

    opinion = _opinion(**opinion_kwargs)
    out = gov.evaluate(opinion, **evaluate_kwargs)
    assert out.decision == expected, f"{name}: expected {expected.value}, got {out.decision.value} ({out.reason})"


def test_firewall_block_takes_precedence_over_healthy_signal():
    """Even with a perfect signal, a model-output firewall block must yield NO_TRADE."""
    gov = StrategyGovernor()
    opinion = _opinion()
    out = gov.evaluate(
        opinion,
        strategy_critique=_critique("proceed"),
        risk_critique=_risk("proceed", "low"),
        calibration_confidence=0.90,
        disagreement_score=0.05,
        model_output_firewall_blocked=True,
    )
    assert out.decision == GovernorDecision.NO_TRADE
    assert out.blocked_by == ["model_output_firewall_block"]


def test_no_trade_bias_tracks_disagreement():
    gov = StrategyGovernor()
    opinion = _opinion()
    out = gov.evaluate(opinion, disagreement_score=0.25)
    assert out.no_trade_bias == pytest.approx(0.25)
