from __future__ import annotations

import json

from autonomy.allocator import Allocator
from autonomy.ontology import DecisionAction, Forecast, MarketView, Vertical
from autonomy.self_improvement import (
    PerformanceGuard,
    build_performance_quarantines,
    build_self_improvement_report,
    write_self_improvement_artifacts,
)


def _cohort(status: str, edge: float, *, n: int = 42, clusters: int = 18) -> dict:
    return {
        "n": n,
        "event_clusters": clusters,
        "mean_brier_advantage_vs_market": edge,
        "evidence_disposition": {
            "status": status,
            "cluster_robust_brier_advantage": {
                "mean": edge,
                "lower": edge - 0.003,
                "upper": edge + 0.003,
                "clusters": clusters,
            },
        },
    }


def _backtest() -> dict:
    return {
        "created_at": "2026-07-15T05:21:33+00:00",
        "weights_written": True,
        "sources_by_scope": {"a|winner|pre": {}, "b|total|pre": {}},
        "decision_policy": {
            "sports_performance_cohorts": {
                "by_joint_scope": {
                    "mlb|total|pre|underdog_lt_40": _cohort(
                        "QUARANTINE_NEGATIVE_EDGE", -0.0105,
                    ),
                    "mlb|total|pre|favorite_gt_60": _cohort(
                        "SUPPORTED_POSITIVE_EDGE", 0.0041,
                    ),
                },
            },
        },
        "crypto_challenger_gates": {
            "crypto_candidate": {"ready_for_explicit_fusion_review": True},
        },
    }


def _market(ticker: str, implied_cents: int) -> MarketView:
    return MarketView(
        ticker=ticker,
        title="test",
        vertical=Vertical.SPORTS,
        status="active",
        close_time="2026-07-16T00:00:00+00:00",
        yes_bid=implied_cents - 1,
        yes_ask=implied_cents + 1,
        no_bid=99 - implied_cents,
        no_ask=101 - implied_cents,
        volume=100,
        liquidity=100,
    )


def _forecast(ticker: str, implied: float) -> Forecast:
    return Forecast(
        market_ticker=ticker,
        probability_yes=implied + 0.1,
        uncertainty=0.08,
        sources_used={"market_prior": 0.5, "mlb_total_runs": 0.5},
        market_implied_yes=implied,
        edge_yes=0.1,
        rationale="test",
    )


def test_only_decisive_negative_joint_cohort_is_auto_quarantined():
    guard = build_performance_quarantines(_backtest())
    assert [entry["scope"] for entry in guard["quarantines"]] == [
        "mlb|total|pre|underdog_lt_40",
    ]
    assert guard["authority"] == {
        "contraction_only": True,
        "can_abstain": True,
        "can_keep_grading": True,
        "can_release_quarantine": False,
        "can_promote": False,
        "can_enable_execution": False,
        "can_increase_capital": False,
    }


def test_guard_abstains_exact_cohort_without_transferring_to_other_leagues(tmp_path):
    guard_path = tmp_path / "guard.json"
    report_path = tmp_path / "improvement.json"
    guard_doc, _report = write_self_improvement_artifacts(
        _backtest(), guard_path=guard_path, report_path=report_path,
    )
    assert json.loads(guard_path.read_text())["quarantines"] == guard_doc["quarantines"]
    guard = PerformanceGuard(guard_path)

    mlb = _market("KXMLBTOTAL-26JUL15-CHCCIN-T8", 35)
    decision = Allocator(object(), performance_guard=guard).decide(
        mlb, _forecast(mlb.ticker, 0.35), object(),
    )
    assert decision.action is DecisionAction.ABSTAIN
    assert decision.abstain_reason.startswith("performance quarantine:")

    nba = _market("KXNBATOTAL-26JUL15-BOSNYK-T220", 35)
    assert guard.reason_for(nba, _forecast(nba.ticker, 0.35)) is None
    favorite = _market("KXMLBTOTAL-26JUL15-CHCCIN-T8", 70)
    assert guard.reason_for(favorite, _forecast(favorite.ticker, 0.70)) is None

    # Long-lived brains can refresh between cycles without a restart.
    guard_path.write_text(json.dumps({"quarantines": []}), encoding="utf-8")
    guard.reload()
    assert guard.reason_for(mlb, _forecast(mlb.ticker, 0.35)) is None


def test_recursive_report_keeps_expansion_human_only():
    backtest = _backtest()
    guard = build_performance_quarantines(backtest)
    report = build_self_improvement_report(backtest, guard)
    assert report["automatic_actions"]["exact_scope_weights_written"] is True
    assert report["human_review_only_proposals"]["crypto_challenger_fusion_reviews"] == [
        "crypto_candidate",
    ]
    assert report["human_review_only_proposals"]["auto_promote"] is False
    assert report["authority"]["can_promote"] is False


def test_written_quarantines_are_sticky_pending_human_release(tmp_path):
    guard_path = tmp_path / "guard.json"
    report_path = tmp_path / "improvement.json"
    first, _ = write_self_improvement_artifacts(
        _backtest(), guard_path=guard_path, report_path=report_path,
    )
    recovered = _backtest()
    recovered["decision_policy"]["sports_performance_cohorts"][
        "by_joint_scope"
    ].pop("mlb|total|pre|underdog_lt_40")
    second, _ = write_self_improvement_artifacts(
        recovered, guard_path=guard_path, report_path=report_path,
    )
    assert second["quarantines"] == first["quarantines"]
    assert second["authority"]["can_release_quarantine"] is False
    assert second["human_release_review_candidates"] == [
        "mlb|total|pre|underdog_lt_40",
    ]
