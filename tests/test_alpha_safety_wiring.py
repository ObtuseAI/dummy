"""Evidence-independent safety wiring for launch-plan alpha items 3.2/3.4/3.5."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from autonomy.adverse_selection import (
    MakerAdverseSelectionEvidence,
    load_maker_adverse_selection_evidence,
)
from autonomy.allocator import Allocator
from autonomy.execution_policy import ExecutionPolicy
from autonomy.executor import Executor
from autonomy.forecaster import EnsembleForecaster
from autonomy.ontology import (
    DecisionAction,
    Forecast,
    MarketView,
    Signal,
    SessionMode,
    Vertical,
)
from autonomy.picks import (
    FUSED_SOURCE,
    apply_promoted_fused_calibration,
    build_fused_signal,
    load_fused_calibration_evidence,
)
from autonomy.promotion import PromotionRegistry
from autonomy.reliability import build_reliability_artifact
from autonomy.risk_brain import RiskBrain
from autonomy.taxonomy import grading_scope


class _Ledger:
    @staticmethod
    def get_weight_for_signal(_source, _vertical, _ticker, _features):
        return 1.0


class _AdmitNoChallengers:
    @staticmethod
    def is_promoted_signal(_source, _ticker, _features):
        return False


def _market() -> MarketView:
    return MarketView(
        ticker="KXMLBGAME-26JUL18NYYBOS-NYY",
        title="NYY at BOS",
        vertical=Vertical.SPORTS,
        status="open",
        close_time=(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        yes_bid=40,
        yes_ask=44,
        no_bid=56,
        no_ask=60,
        volume=2_000,
        liquidity=2_000,
        raw={},
    )


def _forecast(probability: float = 0.70) -> Forecast:
    return Forecast(
        market_ticker=_market().ticker,
        probability_yes=probability,
        uncertainty=0.10,
        sources_used={"market_prior": 0.5, "model": 0.5},
        market_implied_yes=0.42,
        edge_yes=probability - 0.42,
        rationale="raw fused forecast",
    )


def test_market_prior_cannot_mechanically_erase_admitted_evidence():
    market = _market()
    prior = Signal(
        source="market_prior",
        market_ticker=market.ticker,
        probability_yes=0.50,
        uncertainty=0.02,
        rationale="tight book",
    )
    model = Signal(
        source="model",
        market_ticker=market.ticker,
        probability_yes=0.80,
        uncertainty=0.30,
        rationale="independent admitted evidence",
    )

    fused = EnsembleForecaster(
        _Ledger(),
        promotion=_AdmitNoChallengers(),
    ).fuse(market, [prior, model])

    assert fused is not None
    assert fused.sources_used == {"market_prior": 0.6, "model": 0.4}
    assert fused.probability_yes == pytest.approx(0.62)


def test_market_prior_only_forecast_does_not_invent_an_alternative_source():
    market = _market()
    prior = Signal(
        source="market_prior",
        market_ticker=market.ticker,
        probability_yes=0.50,
        uncertainty=0.02,
        rationale="only evidence",
    )

    fused = EnsembleForecaster(
        _Ledger(),
        promotion=_AdmitNoChallengers(),
    ).fuse(market, [prior])

    assert fused is not None
    assert fused.sources_used == {"market_prior": 1.0}
    assert fused.probability_yes == pytest.approx(0.50)


def _adverse_report(generated_at: datetime) -> dict:
    cluster_method = "event_cluster_bootstrap_95"
    return {
        "report_name": "EXECUTION_ADVERSE_SELECTION",
        "generated_at": generated_at.isoformat(),
        "adverse_selection_metrics": {
            "fill_vs_nofill_outcome_delta": {
                "filled_cluster_robust_brier_edge_vs_market": {
                    "mean": -0.03,
                    "clusters": 20,
                    "method": cluster_method,
                },
                "unfilled_cluster_robust_brier_edge_vs_market": {
                    "mean": 0.02,
                    "clusters": 21,
                    "method": cluster_method,
                },
            }
        },
    }


def test_fresh_cluster_evidence_becomes_a_nonnegative_maker_haircut(tmp_path):
    now = datetime(2026, 7, 26, 12, tzinfo=timezone.utc)
    path = tmp_path / "adverse.json"
    path.write_text(json.dumps(_adverse_report(now)), encoding="utf-8")

    evidence = load_maker_adverse_selection_evidence(path, now=now)

    assert evidence is not None
    assert evidence.haircut_cents == pytest.approx(5.0)
    assert evidence.filled_clusters == 20
    assert evidence.unfilled_clusters == 21
    assert len(evidence.source_report_sha256) == 64


def test_stale_adverse_selection_evidence_fails_closed(tmp_path):
    now = datetime(2026, 7, 26, 12, tzinfo=timezone.utc)
    path = tmp_path / "adverse.json"
    path.write_text(
        json.dumps(_adverse_report(now - timedelta(hours=25))),
        encoding="utf-8",
    )

    assert load_maker_adverse_selection_evidence(path, now=now) is None
    assert load_maker_adverse_selection_evidence(
        path,
        now=now.replace(tzinfo=None),
    ) is None


def test_favorable_fill_gap_cannot_manufacture_maker_alpha(tmp_path):
    now = datetime(2026, 7, 26, 12, tzinfo=timezone.utc)
    report = _adverse_report(now)
    delta = report["adverse_selection_metrics"]["fill_vs_nofill_outcome_delta"]
    delta["filled_cluster_robust_brier_edge_vs_market"]["mean"] = 0.03
    delta["unfilled_cluster_robust_brier_edge_vs_market"]["mean"] = 0.02
    path = tmp_path / "adverse.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    evidence = load_maker_adverse_selection_evidence(path, now=now)

    assert evidence is not None
    assert evidence.haircut_cents == 0.0


def test_maker_haircut_reduces_ev_and_kelly_without_changing_taker_math(tmp_path):
    digest = "a" * 64
    evidence = MakerAdverseSelectionEvidence(
        haircut_cents=5.0,
        generated_at=datetime.now(timezone.utc).isoformat(),
        source_report_sha256=digest,
        filled_clusters=20,
        unfilled_clusters=21,
    )
    baseline_brain = RiskBrain(state_path=tmp_path / "baseline-risk.json")
    guarded_brain = RiskBrain(state_path=tmp_path / "guarded-risk.json")
    baseline = Allocator(baseline_brain).decide(
        _market(),
        _forecast(),
        baseline_brain.load_state(100_000),
    )
    guarded = Allocator(
        guarded_brain,
        maker_adverse_selection_evidence=evidence,
        require_maker_adverse_selection_evidence=True,
    ).decide(
        _market(),
        _forecast(),
        guarded_brain.load_state(100_000),
    )

    assert baseline.action is DecisionAction.BUY_YES
    assert guarded.action is DecisionAction.BUY_YES
    assert guarded.ev_cents_per_contract == pytest.approx(
        baseline.ev_cents_per_contract - 5.0
    )
    assert guarded.kelly_fraction < baseline.kelly_fraction
    assert guarded.risk_snapshot["maker_adverse_selection_haircut_cents"] == 5.0
    assert guarded.risk_snapshot["maker_adverse_selection_report_sha256"] == digest
    executor = Executor(
        SessionMode.SHADOW,
        session_path=tmp_path / "session.json",
        kill_path=tmp_path / "KILL",
    )
    execution_detail = executor._execution_detail(guarded)
    assert execution_detail["maker_adverse_selection_haircut_cents"] == 5.0
    assert execution_detail["maker_adverse_selection_report_sha256"] == digest


def test_required_missing_maker_evidence_abstains(tmp_path):
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    decision = Allocator(
        brain,
        require_maker_adverse_selection_evidence=True,
    ).decide(_market(), _forecast(), brain.load_state(100_000))

    assert decision.action is DecisionAction.ABSTAIN
    assert decision.abstain_reason == (
        "maker adverse-selection evidence unavailable or stale"
    )


def test_missing_maker_evidence_does_not_change_taker_math(tmp_path):
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    decision = Allocator(
        brain,
        execution_policy=ExecutionPolicy.taker_only(),
        require_maker_adverse_selection_evidence=True,
    ).decide(_market(), _forecast(), brain.load_state(100_000))

    assert decision.action is DecisionAction.BUY_YES
    assert decision.price_cents == _market().yes_ask


def _fused_scope() -> str:
    signal = build_fused_signal(_market().ticker, _forecast())
    return grading_scope(FUSED_SOURCE, _market().ticker, signal.features)


def _write_reliability_artifact(path, *, tamper: bool = False) -> None:
    maps = {
        _fused_scope(): [(0.0, 0.05), (0.5, 0.45), (1.0, 0.9)],
    }
    artifact = build_reliability_artifact(
        maps,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    if tamper:
        artifact["maps"][_fused_scope()][1] = (0.5, 0.99)
    path.write_text(json.dumps(artifact), encoding="utf-8")


def test_fused_calibration_cannot_reach_decisions_without_exact_promotion(tmp_path):
    maps_path = tmp_path / "reliability.json"
    _write_reliability_artifact(maps_path)
    evidence = load_fused_calibration_evidence(maps_path)
    assert evidence is not None
    raw = _forecast()
    empty = PromotionRegistry(
        tmp_path / "promotions.json",
        tmp_path / "demotions.json",
    )

    unchanged = apply_promoted_fused_calibration(
        _market().ticker,
        raw,
        evidence,
        empty,
    )

    assert unchanged is raw


def test_exact_promoted_calibration_reaches_decision_with_audit_binding(tmp_path):
    maps_path = tmp_path / "reliability.json"
    _write_reliability_artifact(maps_path)
    evidence = load_fused_calibration_evidence(maps_path)
    assert evidence is not None
    promotions_path = tmp_path / "promotions.json"
    promotions_path.write_text(
        json.dumps(
            {
                "promotions": [
                        {
                            "source": "fused_forecast::cal",
                            "subject": "mlb",
                            "market_type": "na",
                            "horizon": "pre",
                        }
                ]
            }
        ),
        encoding="utf-8",
    )
    promoted = PromotionRegistry(
        promotions_path,
        tmp_path / "demotions.json",
    )

    calibrated = apply_promoted_fused_calibration(
        _market().ticker,
        _forecast(),
        evidence,
        promoted,
    )

    assert calibrated.probability_yes == pytest.approx(0.63)
    assert calibrated.uncalibrated_probability_yes == pytest.approx(0.70)
    assert calibrated.calibration_source == "fused_forecast::cal"
    assert calibrated.sources_used == {"fused_forecast::cal": 1.0}
    assert calibrated.calibration_scope == _fused_scope()
    assert calibrated.calibration_evidence_sha256 == evidence.maps_sha256
    assert calibrated.edge_yes == pytest.approx(0.21)


def test_tampered_reliability_artifact_cannot_reach_decisions(tmp_path):
    path = tmp_path / "reliability.json"
    _write_reliability_artifact(path, tamper=True)

    assert load_fused_calibration_evidence(path) is None


def test_content_bound_but_nonmonotone_reliability_map_is_rejected(tmp_path):
    path = tmp_path / "reliability.json"
    artifact = build_reliability_artifact(
        {
            _fused_scope(): [
                (0.0, 0.1),
                (0.5, 0.8),
                (1.0, 0.7),
            ]
        },
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    path.write_text(json.dumps(artifact), encoding="utf-8")

    assert load_fused_calibration_evidence(path) is None
