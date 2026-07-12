"""WS-14 promotion protocol: registry, readiness math, fuse integration."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from autonomy.forecaster import EnsembleForecaster
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.promotion import (
    DEGRADE_EDGE_FLOOR,
    MIN_CONTESTED_CLUSTERS,
    PromotionRegistry,
    build_readiness,
    cluster_series,
    scope_readiness,
)

NOW_TS = 1_800_000_000.0


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


# -- registry ------------------------------------------------------------------

def test_missing_files_promote_nobody(tmp_path):
    reg = PromotionRegistry(tmp_path / "promotions.json", tmp_path / "demotions.json")
    assert reg.is_promoted("crypto_ewma_t|ladder|daily+") is False
    assert reg.snapshot()["promoted"] == []


def test_promotion_is_scope_exact_and_demotion_overrides(tmp_path):
    promotions = tmp_path / "promotions.json"
    demotions = tmp_path / "demotions.json"
    _write(promotions, {"promotions": [
        {"source": "crypto_ewma_t", "market_type": "ladder", "horizon": "daily+",
         "promoted_at": "2026-07-12T00:00:00+00:00", "evidence_ref": "readiness"},
    ]})
    reg = PromotionRegistry(promotions, demotions)
    assert reg.is_promoted("crypto_ewma_t|ladder|daily+") is True
    # A different horizon / market_type / source of the same family is NOT
    # promoted -- promotion is per exact scope.
    assert reg.is_promoted("crypto_ewma_t|ladder|15m") is False
    assert reg.is_promoted("crypto_ewma_t|15m_direction|daily+") is False
    assert reg.is_promoted("crypto_spot_vol|ladder|daily+") is False

    # Machine demotion overrides the human promotion immediately.
    _write(demotions, {"demotions": [{"scope": "crypto_ewma_t|ladder|daily+"}]})
    reg2 = PromotionRegistry(promotions, demotions)
    assert reg2.is_promoted("crypto_ewma_t|ladder|daily+") is False
    assert reg2.snapshot()["active"] == []


def test_is_promoted_signal_derives_scope(tmp_path):
    promotions = tmp_path / "promotions.json"
    _write(promotions, {"promotions": [
        {"source": "crypto_ewma_t", "market_type": "ladder", "horizon": "daily+"},
    ]})
    reg = PromotionRegistry(promotions, tmp_path / "d.json")
    assert reg.is_promoted_signal(
        "crypto_ewma_t", "KXBTCD-26JUL0917-T71000", {"hours_to_close": 26.0}) is True
    # Same source, hourly contract -> different scope -> not promoted.
    assert reg.is_promoted_signal(
        "crypto_ewma_t", "KXBTCD-26JUL0917-T71000", {"hours_to_close": 2.0}) is False


# -- readiness math ------------------------------------------------------------

def _series(n, edge, start_ts=NOW_TS - 300 * 86400, step=86400):
    # n clusters, one edge each, one per `step` seconds ending near now.
    return [(start_ts + i * step, float(edge)) for i in range(n)]


def test_cluster_series_collapses_correlated_rows():
    rows = [
        (100.0, "E1", 0.02), (110.0, "E1", 0.04),  # same cluster -> mean 0.03
        (200.0, "E2", -0.01),
    ]
    series = cluster_series(rows)
    assert series == [(100.0, pytest.approx(0.03)), (200.0, -0.01)]


def test_eligible_scope_passes_all_criteria():
    series = _series(MIN_CONTESTED_CLUSTERS + 20, 0.01)
    r = scope_readiness("crypto_ewma_t|ladder|daily+", series, NOW_TS)
    assert r.n_clusters == MIN_CONTESTED_CLUSTERS + 20
    assert r.criteria == {
        "clusters_ge_min": True, "edge_ci95_lower_positive": True,
        "clv_nonneg_or_absent": True, "not_degrading": True,
    }
    assert r.eligible is True and r.demote is False
    assert r.days_to_eligibility == 0.0


def test_insufficient_clusters_projects_days_to_eligibility():
    # 140 clusters spaced 1 hour apart -> all within the last 14 days ->
    # accrual = 140/14 = 10/day.
    series = [(NOW_TS - i * 3600, 0.01) for i in range(140)]
    r = scope_readiness("crypto_ewma_t|ladder|hourly", series, NOW_TS)
    assert r.eligible is False
    assert r.criteria["clusters_ge_min"] is False
    assert r.accrual_per_day == pytest.approx(140 / 14.0)
    # remaining = 300-140 = 160; days = 160 / (140/14) = 16.0
    assert r.days_to_eligibility == pytest.approx(16.0, abs=0.1)


def test_no_recent_accrual_gives_unknown_projection():
    series = _series(50, 0.01, start_ts=NOW_TS - 400 * 86400, step=86400)
    r = scope_readiness("crypto_ewma_t|ladder|daily+", series, NOW_TS)
    assert r.accrual_per_day == 0.0
    assert r.days_to_eligibility is None  # unknown, never falsely zero


def test_degradation_blocks_eligibility():
    good = [(NOW_TS - (400 - i) * 86400, 0.01) for i in range(300)]
    bad = [(NOW_TS - (100 - i) * 3600, -0.02) for i in range(100)]  # recent, negative
    r = scope_readiness("crypto_ewma_t|ladder|daily+", good + bad, NOW_TS)
    assert r.n_clusters == 400
    assert r.trailing_degrade_mean is not None and r.trailing_degrade_mean < DEGRADE_EDGE_FLOOR
    assert r.degrading is True
    assert r.criteria["not_degrading"] is False
    assert r.eligible is False


def test_demote_only_when_promoted_and_trailing_ci_negative():
    series = _series(250, -0.02)
    promoted = scope_readiness("s|ladder|daily+", series, NOW_TS, is_currently_promoted=True)
    assert promoted.demote_ci95_high is not None and promoted.demote_ci95_high < 0
    assert promoted.demote is True
    # Same evidence but NOT currently promoted -> nothing to demote.
    unpromoted = scope_readiness("s|ladder|daily+", series, NOW_TS, is_currently_promoted=False)
    assert unpromoted.demote is False
    # Positive trailing record -> promoted scope stays.
    healthy = scope_readiness("s|ladder|daily+", _series(250, 0.02), NOW_TS,
                              is_currently_promoted=True)
    assert healthy.demote is False


def test_clv_negative_fails_criterion():
    series = _series(MIN_CONTESTED_CLUSTERS + 5, 0.01)
    r = scope_readiness("s|ladder|daily+", series, NOW_TS, clv_mean=-30.0)
    assert r.criteria["clv_nonneg_or_absent"] is False
    assert r.eligible is False


def test_build_readiness_ranks_candidates_and_emits_demotions():
    scope_rows = {
        "crypto_a|ladder|daily+": [  # eligible, unpromoted -> candidate
            (NOW_TS - i * 3600, f"E{i}", 0.01) for i in range(MIN_CONTESTED_CLUSTERS + 10)
        ],
        "crypto_b|ladder|daily+": [  # promoted but degraded -> demote
            (NOW_TS - i * 3600, f"F{i}", -0.02) for i in range(250)
        ],
    }
    built = build_readiness(
        scope_rows, promoted_scopes={"crypto_b|ladder|daily+"},
        now_ts=NOW_TS, now_iso="2026-07-12T00:00:00+00:00")
    report = built["report"]
    assert report["promotion_candidates"] == ["crypto_a|ladder|daily+"]
    assert report["auto_demotions"] == ["crypto_b|ladder|daily+"]
    assert built["demotions"]["demotions"][0]["scope"] == "crypto_b|ladder|daily+"
    # Candidate sorts first.
    assert report["scopes"][0]["scope"] == "crypto_a|ladder|daily+"


def test_non_challenger_gated_scope_is_not_a_candidate():
    # An eligible scope whose source already fuses (not challenger-gated) must
    # NOT be recommended -- promoting it is a no-op and demotion could not
    # remove it.
    scope_rows = {
        "champion_x|ladder|daily+": [
            (NOW_TS - i * 3600, f"E{i}", 0.01) for i in range(MIN_CONTESTED_CLUSTERS + 10)
        ],
        "challenger_y|ladder|daily+": [
            (NOW_TS - i * 3600, f"F{i}", 0.01) for i in range(MIN_CONTESTED_CLUSTERS + 10)
        ],
    }
    built = build_readiness(
        scope_rows, promoted_scopes=set(), now_ts=NOW_TS,
        now_iso="2026-07-12T00:00:00+00:00",
        challenger_gated_scopes={"challenger_y|ladder|daily+"})
    report = built["report"]
    assert report["promotion_candidates"] == ["challenger_y|ladder|daily+"]
    by_scope = {s["scope"]: s for s in report["scopes"]}
    assert by_scope["champion_x|ladder|daily+"]["eligible"] is True
    assert by_scope["champion_x|ladder|daily+"]["challenger_gated"] is False


# -- forecaster integration ----------------------------------------------------

def _crypto_market():
    return MarketView(
        ticker="KXBTCD-26JUL0917-T71000", title="BTC above?", vertical=Vertical.CRYPTO,
        status="open", close_time="2026-07-10T00:00:00+00:00",
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56, volume=100, liquidity=1000,
        raw={},
    )


def _signals():
    prior = Signal(source="market_prior", market_ticker="KXBTCD-26JUL0917-T71000",
                   probability_yes=0.5, uncertainty=0.1, rationale="")
    challenger = Signal(
        source="crypto_ewma_t", market_ticker="KXBTCD-26JUL0917-T71000",
        probability_yes=0.85, uncertainty=0.1, rationale="",
        features={"challenger_only": True, "hours_to_close": 26.0})
    return prior, challenger


def test_empty_registry_excludes_challenger_promoted_scope_enters_ensemble(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        market = _crypto_market()
        prior, challenger = _signals()

        empty = PromotionRegistry(tmp_path / "p.json", tmp_path / "d.json")
        forecaster = EnsembleForecaster(ledger, promotion=empty)
        excluded = forecaster.fuse(market, [prior, challenger])
        assert excluded is not None
        # Challenger filtered: fused prob stays at the prior (only active signal).
        assert excluded.probability_yes == pytest.approx(0.5, abs=1e-9)

        _write(tmp_path / "p.json", {"promotions": [
            {"source": "crypto_ewma_t", "market_type": "ladder", "horizon": "daily+"},
        ]})
        promoted = PromotionRegistry(tmp_path / "p.json", tmp_path / "d.json")
        forecaster2 = EnsembleForecaster(ledger, promotion=promoted)
        included = forecaster2.fuse(market, [prior, challenger])
        assert included is not None
        # Promoted challenger now pulls the fused probability off the prior.
        assert included.probability_yes > 0.5
    finally:
        ledger.close()


def test_non_challenger_signal_always_active_regardless_of_registry(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        market = _crypto_market()
        prior = Signal(source="market_prior", market_ticker=market.ticker,
                       probability_yes=0.5, uncertainty=0.1, rationale="")
        plain = Signal(source="crypto_spot_vol", market_ticker=market.ticker,
                       probability_yes=0.8, uncertainty=0.1, rationale="",
                       features={})  # no challenger_only -> always active
        empty = PromotionRegistry(tmp_path / "p.json", tmp_path / "d.json")
        forecaster = EnsembleForecaster(ledger, promotion=empty)
        fused = forecaster.fuse(market, [prior, plain])
        assert fused is not None and fused.probability_yes > 0.5
    finally:
        ledger.close()
