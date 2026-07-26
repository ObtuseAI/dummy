"""Wave-19: declined dossiers, the fusion scope floor, tuner coverage."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from autonomy import no_edge_map
from autonomy.no_edge_map import load_negative_scopes
from autonomy.ontology import MarketView, Signal, Vertical


def _map_payload(scopes, age_hours=1.0):
    generated = datetime.now(timezone.utc) - timedelta(hours=age_hours)
    negative = [
        {
            "scope": scope,
            "clusters": 50,
            "edge_mean": -0.01,
            "ci_lower": -0.02,
            "ci_upper": -0.001,
        }
        for scope in scopes
    ]
    return {
        "report_name": "NO_EDGE_MAP",
        "generated_at": generated.isoformat(),
        "min_clusters": no_edge_map.MIN_CLUSTERS,
        "counts": {
            "edge": 0,
            "no_demonstrated_edge": 0,
            "significantly_negative": len(negative),
            "insufficient_evidence": 0,
        },
        "edge": [],
        "no_demonstrated_edge": [],
        "significantly_negative": negative,
        "insufficient_evidence_scopes": [],
    }


def test_load_negative_scopes_fresh_stale_missing_and_malformed(tmp_path):
    path = tmp_path / "no_edge_map.json"
    path.write_text(json.dumps(_map_payload(["a|b|c|d"])), encoding="utf-8")
    fresh = load_negative_scopes(path)
    assert fresh == frozenset({"a|b|c|d"})
    assert fresh.trusted is True
    assert fresh.status == "fresh"

    path.write_text(
        json.dumps(_map_payload(["a|b|c|d"], age_hours=24 * 8)), encoding="utf-8")
    stale = load_negative_scopes(path)
    assert stale == frozenset()
    assert stale.trusted is False
    assert stale.status == "stale"

    missing = load_negative_scopes(tmp_path / "absent.json")
    assert missing == frozenset()
    assert missing.trusted is False
    assert missing.status == "missing"

    path.write_text("{not-json", encoding="utf-8")
    malformed_json = load_negative_scopes(path)
    assert malformed_json == frozenset()
    assert malformed_json.trusted is False
    assert malformed_json.status == "malformed_json"

    malformed_payload = _map_payload(["a|b|c|d"])
    malformed_payload["significantly_negative"][0]["ci_upper"] = 0.001
    path.write_text(json.dumps(malformed_payload), encoding="utf-8")
    malformed_schema = load_negative_scopes(path)
    assert malformed_schema == frozenset()
    assert malformed_schema.trusted is False
    assert malformed_schema.status == "malformed_schema"


def _market(ticker="KXBTCD-26JUL1817-T118000.01"):
    return MarketView(
        ticker=ticker, title="BTC?", vertical=Vertical.CRYPTO, status="open",
        close_time="2026-07-18T17:00:00+00:00", yes_bid=44, yes_ask=46,
        no_bid=54, no_ask=56, volume=10, liquidity=10, raw={})


def _signal(source, p=0.6, challenger=False, **features):
    return Signal(source=source, market_ticker="KXBTCD-26JUL1817-T118000.01",
                  probability_yes=p, uncertainty=0.1, rationale="r",
                  features={"challenger_only": challenger, **features})


class _Ledger:
    def get_weight(self, source, default=1.0):
        return 1.0


class _NoPromotion:
    def is_promoted_signal(self, source, ticker, features):
        return False

    def weight_multiplier_for_signal(self, source, ticker, features):
        return 1.0


@pytest.mark.parametrize(
    ("artifact_kind", "expected_status"),
    (
        ("missing", "missing"),
        ("stale", "stale"),
        ("malformed", "malformed_json"),
    ),
)
def test_untrusted_no_edge_evidence_disables_independent_fusion(
    tmp_path,
    monkeypatch,
    artifact_kind,
    expected_status,
):
    from autonomy.allocator import MAX_UNCERTAINTY, Allocator
    from autonomy.forecaster import EnsembleForecaster
    from autonomy.ontology import DecisionAction
    from autonomy.risk_brain import RiskBrain

    path = tmp_path / "no_edge_map.json"
    if artifact_kind == "stale":
        path.write_text(
            json.dumps(_map_payload([], age_hours=24 * 8)),
            encoding="utf-8",
        )
    elif artifact_kind == "malformed":
        path.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(no_edge_map, "MAP_PATH", path)

    market = _market()
    predictive = _signal("crypto_spot_vol", p=0.9)
    prior = _signal("market_prior", p=0.55)
    forecaster = EnsembleForecaster(_Ledger(), promotion=_NoPromotion())

    anchor = forecaster.fuse(market, [predictive, prior])
    assert anchor is not None
    assert anchor.sources_used == {"market_prior": 1.0}
    assert anchor.uncertainty == 0.5
    assert anchor.uncertainty > MAX_UNCERTAINTY
    assert anchor.edge_yes == 0.0
    assert anchor.model_probability_yes is None
    assert predictive.source not in anchor.sources_used
    assert f"NO_EDGE_MAP_UNTRUSTED:{expected_status}" in anchor.rationale
    assert forecaster._negative_scope_evidence_trusted is False
    assert forecaster._negative_scope_evidence_status == expected_status

    risk_brain = RiskBrain(state_path=tmp_path / "risk.json")
    decision = Allocator(risk_brain).decide(
        market,
        anchor,
        risk_brain.load_state(100_000),
    )
    assert decision.action is DecisionAction.ABSTAIN
    assert decision.abstain_reason == "uncertainty 0.50 too high"

    # Without even a market anchor, an untrusted map yields no forecast.
    assert forecaster.fuse(market, [predictive]) is None


def test_fresh_no_edge_evidence_excludes_only_negative_scope(
    tmp_path,
    monkeypatch,
):
    from autonomy.forecaster import EnsembleForecaster
    from autonomy.taxonomy import grading_scope

    market = _market()
    bad = _signal("crypto_spot_vol", p=0.9)
    good = _signal("crypto_macro_regime", p=0.65)
    prior = _signal("market_prior", p=0.55)
    bad_scope = grading_scope(bad.source, market.ticker, bad.features)
    path = tmp_path / "no_edge_map.json"
    path.write_text(json.dumps(_map_payload([bad_scope])), encoding="utf-8")
    monkeypatch.setattr(no_edge_map, "MAP_PATH", path)

    forecaster = EnsembleForecaster(_Ledger(), promotion=_NoPromotion())
    forecast = forecaster.fuse(market, [bad, good, prior])

    assert forecast is not None
    assert bad.source not in forecast.sources_used
    assert good.source in forecast.sources_used
    assert prior.source in forecast.sources_used
    assert forecast.uncertainty < 0.5
    assert forecaster._negative_scope_evidence_trusted is True
    assert forecaster._negative_scope_evidence_status == "fresh"


def test_fusion_floor_excludes_significantly_negative_scope():
    from autonomy.forecaster import EnsembleForecaster
    from autonomy.taxonomy import grading_scope

    market = _market()
    bad = _signal("crypto_spot_vol", p=0.9)
    prior = _signal("market_prior", p=0.55)
    bad_scope = grading_scope("crypto_spot_vol", market.ticker, bad.features)

    floored = EnsembleForecaster(
        _Ledger(), promotion=_NoPromotion(),
        negative_scopes=frozenset({bad_scope}))
    forecast = floored.fuse(market, [bad, prior])
    assert forecast is not None
    assert "crypto_spot_vol" not in forecast.sources_used
    assert "market_prior" in forecast.sources_used

    open_floor = EnsembleForecaster(
        _Ledger(), promotion=_NoPromotion(), negative_scopes=frozenset())
    forecast_open = open_floor.fuse(market, [bad, prior])
    assert "crypto_spot_vol" in forecast_open.sources_used


def test_fusion_floor_never_suppresses_the_market_prior():
    from autonomy.forecaster import EnsembleForecaster
    from autonomy.taxonomy import grading_scope

    market = _market()
    prior = _signal("market_prior", p=0.55)
    prior_scope = grading_scope("market_prior", market.ticker, prior.features)
    floored = EnsembleForecaster(
        _Ledger(), promotion=_NoPromotion(),
        negative_scopes=frozenset({prior_scope}))
    forecast = floored.fuse(market, [prior])
    assert forecast is not None
    assert "market_prior" in forecast.sources_used


def test_declined_scopes_carry_dossiers():
    from autonomy.auto_promotion import (
        AutoPromotionEngine,
        DEFAULT_CONFIG,
        RailsVerdict,
    )

    # One eligible scope with plenty of clusters but a beat rate below the
    # bar: previously silently skipped, now a DECLINED decision with the
    # full dossier and the failing criteria named.
    class _Row:
        def __init__(self, i):
            self.source = "crypto_equities_flow"
            self.ticker = f"KXSOLD-26JUL18{i:02d}-T160.01"
            self.event_cluster = f"C{i}"
            self.created_at = f"2026-07-{(i % 17) + 1:02d}T12:00:00+00:00"
            self.probability_yes = 0.62
            self.market_probability = 0.5
            self.result_yes = i % 2 == 0        # 50% -> beat rate ~coin flip
            self.features = {}
            self.scope = "crypto_equities_flow|sol|15m_direction|15m"

    scope = "crypto_equities_flow|sol|15m_direction|15m"
    rows = [_Row(i) for i in range(400)]
    engine = AutoPromotionEngine(DEFAULT_CONFIG)
    result = engine.decide(
        scope_rows={scope: rows},
        promoted={},
        now_ts=datetime(2026, 7, 18, tzinfo=timezone.utc).timestamp(),
        now_iso="2026-07-18T12:00:00+00:00",
        rails=RailsVerdict(abort=False, reasons=[]),
        eligible_scopes={scope},
    )
    assert result.promotions == []
    assert len(result.declined) == 1
    declined = result.declined[0]
    assert declined.scope == scope
    assert declined.action == "DECLINED"
    assert declined.reason.startswith("failed: ")
    assert isinstance(declined.dossier, dict) and declined.dossier
    assert "declined" in result.to_dict()


def test_wnba_total_sigma_is_tunable():
    from autonomy.tuner import TUNABLES

    names = {t["name"] for t in TUNABLES}
    assert "wnba_total_sigma" in names
