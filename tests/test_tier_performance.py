"""Forward-only performance accounting for versioned betting-guide tiers."""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace

import pytest

from autonomy.ledger import AutonomyLedger
from autonomy.ontology import (
    Decision,
    DecisionAction,
    Forecast,
    OutcomeKind,
    TradeOutcome,
)
from autonomy.tier_performance import tier_performance_report
from autonomy.tier_policy import (
    TIER_POLICY_VERSION,
    assess_market_tier,
)


def _features(
    tier: str | None,
    *,
    ticker: str = "KXMLBGAME-26JUL22TESTAAA-AAA",
    probability: float = 0.70,
    side: str = "yes",
    version: str | None = TIER_POLICY_VERSION,
    assessed_at: str = "2026-07-22T08:59:30+00:00",
    quote_fetched_at: str = "2026-07-22T08:59:00+00:00",
    close_time: str = "2026-07-23T08:59:00+00:00",
) -> dict[str, object]:
    assessed = datetime.fromisoformat(assessed_at)
    forecast = _forecast(ticker, probability)
    assessment = None
    for ask in range(1, 100):
        market = SimpleNamespace(
            ticker=ticker,
            yes_ask=ask if side == "yes" else 99,
            no_ask=ask if side == "no" else 99,
            yes_bid=(max(1, ask - 1) if side == "yes" else 98),
            no_bid=(max(1, ask - 1) if side == "no" else 98),
            liquidity=500,
            fetched_at=quote_fetched_at,
            close_time=close_time,
            status="open",
        )
        candidate = assess_market_tier(market, forecast, now=assessed)
        if candidate.tier == tier and (
            candidate.side == side or tier is None
        ):
            assessment = candidate
            break
    if assessment is None:
        raise AssertionError(f"could not construct {tier=} {side=} for {ticker}")
    if version != TIER_POLICY_VERSION:
        assessment = replace(assessment, policy_version=version)  # type: ignore[arg-type]
    result: dict[str, object] = assessment.feature_fields()
    result.update({
        "challenger_only": False,
        "is_fused_output": True,
        "market_implied_yes": 0.55,
    })
    return result


def _insert_signal(
    ledger: AutonomyLedger,
    ticker: str,
    probability: float,
    created_at: str,
    ingested_at: str,
    *,
    tier: str | None = "B",
    side: str = "yes",
    version: str | None = TIER_POLICY_VERSION,
    mode: str = "live",
    close_time: str = "2026-07-23T08:59:00+00:00",
) -> None:
    ledger._conn.execute(
        "INSERT INTO signals(source,market_ticker,probability_yes,uncertainty,"
        "rationale,features,created_at,mode,ingested_at,ingest_version) "
        "VALUES (?,?,?,?,?,?,?,?,?,2)",
        (
            "fused_forecast",
            ticker,
            probability,
            0.10,
            "tier performance fixture",
            json.dumps(
                _features(
                    tier,
                    ticker=ticker,
                    probability=probability,
                    side=side,
                    version=version,
                    close_time=close_time,
                ),
                sort_keys=True,
                separators=(",", ":"),
            ),
            created_at,
            mode,
            ingested_at,
        ),
    )


def _forecast(ticker: str, probability: float = 0.70) -> Forecast:
    return Forecast(
        market_ticker=ticker,
        probability_yes=probability,
        uncertainty=0.10,
        sources_used={"unit": 1.0},
        market_implied_yes=0.55,
        edge_yes=probability - 0.55,
        rationale="tier performance fixture",
    )


def _decision(
    decision_id: str,
    ticker: str,
    *,
    tier: str | None = "A",
    version: str = TIER_POLICY_VERSION,
    price: int = 50,
    count: int = 1,
    created_at: str = "2026-07-22T11:00:00+00:00",
) -> Decision:
    snapshot = _features(
        tier,
        ticker=ticker,
        probability=0.70,
        version=version,
    )
    return Decision(
        decision_id=decision_id,
        market_ticker=ticker,
        action=DecisionAction.BUY_YES,
        side="yes",
        price_cents=price,
        count=count,
        ev_cents_per_contract=4.0,
        kelly_fraction=0.01,
        notional_cents=price * count,
        forecast=_forecast(ticker),
        risk_snapshot={},
        created_at=created_at,
        tier_label=tier,
        tier_policy_version=version,
        tier_score=snapshot["tier_score"],  # type: ignore[arg-type]
        tier_reason=str(snapshot["tier_reason"]),
        tier_snapshot=snapshot,
    )


def _settle_market(
    ledger: AutonomyLedger,
    ticker: str,
    result_yes: bool,
    settled_at: str,
) -> None:
    ledger._conn.execute(
        "INSERT INTO settlements(market_ticker,result_yes,settled_at) VALUES (?,?,?)",
        (ticker, int(result_yes), settled_at),
    )


def _outcome(
    decision_id: str,
    ticker: str,
    kind: OutcomeKind,
    created_at: str,
    *,
    fill_count: int = 0,
    fill_price: int | None = None,
    pnl: int | None = None,
    broker_contacted: bool = False,
    detail: dict[str, object] | None = None,
) -> TradeOutcome:
    return TradeOutcome(
        decision_id=decision_id,
        market_ticker=ticker,
        kind=kind,
        order_id=f"order-{decision_id}",
        fill_count=fill_count,
        fill_price_cents=fill_price,
        pnl_cents=pnl,
        broker_contacted=broker_contacted,
        detail=detail or {},
        created_at=created_at,
    )


def test_forecast_performance_is_versioned_forward_only_and_point_in_time(tmp_path) -> None:
    ledger = AutonomyLedger(tmp_path / "forecast.db")
    try:
        kept = "KXMLBGAME-26JUL22AAABBB-AAA"
        _insert_signal(
            ledger,
            kept,
            0.60,
            "2026-07-22T09:00:00+00:00",
            "2026-07-22T09:01:00+00:00",
        )
        _insert_signal(
            ledger,
            kept,
            0.70,
            "2026-07-22T10:00:00+00:00",
            "2026-07-22T10:01:00+00:00",
        )
        # Created before the decision but not witnessed until after it.
        _insert_signal(
            ledger,
            kept,
            0.05,
            "2026-07-22T10:30:00+00:00",
            "2026-07-22T11:01:00+00:00",
        )
        # Post-decision, retro, and other-policy rows must not become the pick
        # of record even when they were appended later.
        _insert_signal(
            ledger,
            kept,
            0.01,
            "2026-07-22T11:01:00+00:00",
            "2026-07-22T11:02:00+00:00",
            tier=None,
        )
        _insert_signal(
            ledger,
            kept,
            0.02,
            "2026-07-22T10:50:00+00:00",
            "2026-07-22T10:51:00+00:00",
            tier=None,
            mode="retro",
        )
        _insert_signal(
            ledger,
            kept,
            0.99,
            "2026-07-22T10:55:00+00:00",
            "2026-07-22T10:56:00+00:00",
            version="legacy_v1",
        )
        ledger.record_decision(_decision("cutoff", kept, tier="B"))
        _settle_market(ledger, kept, True, "2026-07-22T12:00:00+00:00")

        no_decision = "KXMLBGAME-26JUL22CCCDDD-CCC"
        _insert_signal(
            ledger,
            no_decision,
            0.30,
            "2026-07-22T09:30:00+00:00",
            "2026-07-22T09:31:00+00:00",
            tier="C",
            side="no",
        )
        _insert_signal(
            ledger,
            no_decision,
            0.95,
            "2026-07-22T12:01:00+00:00",
            "2026-07-22T12:02:00+00:00",
            tier="A",
        )
        _settle_market(ledger, no_decision, False, "2026-07-22T12:00:00+00:00")

        wrong_version = "KXMLBGAME-26JUL22EEEFFF-EEE"
        _insert_signal(
            ledger,
            wrong_version,
            0.90,
            "2026-07-22T09:00:00+00:00",
            "2026-07-22T09:01:00+00:00",
            version="legacy_v1",
        )
        _settle_market(ledger, wrong_version, True, "2026-07-22T12:00:00+00:00")

        before_effective = "KXMLBGAME-26JUL21GGGHHH-GGG"
        _insert_signal(
            ledger,
            before_effective,
            0.90,
            "2026-07-21T23:00:00+00:00",
            "2026-07-21T23:01:00+00:00",
            tier="A",
        )
        _settle_market(ledger, before_effective, True, "2026-07-22T01:00:00+00:00")
        ledger._conn.commit()

        report = tier_performance_report(ledger._conn)

        assert report["policy_version"] == TIER_POLICY_VERSION
        assert report["legacy_backfill"] is False
        assert report["status"] == "INSUFFICIENT_SAMPLE"
        assert report["forecast"]["overall"]["n"] == 2
        assert report["forecast"]["overall"]["value_side_hit_rate"] == 1.0
        b_metrics = report["forecast"]["by_tier"]["B"]
        c_metrics = report["forecast"]["by_tier"]["C"]
        assert b_metrics["n"] == 1
        assert b_metrics["mean_brier"] == pytest.approx(0.09)
        assert c_metrics["n"] == 1
        assert c_metrics["mean_brier"] == pytest.approx(0.09)
        assert report["forecast"]["by_tier"]["A"]["n"] == 0
    finally:
        ledger.close()


def test_realized_tier_performance_requires_prior_fill_and_uses_actual_cost(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "autonomy.ledger._now", lambda: "2026-07-22T11:01:00+00:00"
    )
    ledger = AutonomyLedger(tmp_path / "realized.db")
    try:
        exact_ticker = "KXMLBGAME-26JUL22AAABBB-AAA"
        ledger.record_decision(
            _decision("exact", exact_ticker, tier="A", price=60, count=2)
        )
        ledger.record_outcome(_outcome(
            "exact",
            exact_ticker,
            OutcomeKind.SHADOW,
            "2026-07-22T11:05:00+00:00",
            fill_count=2,
            fill_price=39,
            detail={"fill_cost_cents": 77, "execution_fee_cents": 3},
        ))
        _settle_market(
            ledger, exact_ticker, True, "2026-07-22T13:00:00+00:00"
        )
        ledger.record_outcome(_outcome(
            "exact",
            exact_ticker,
            OutcomeKind.SETTLED_WIN,
            "2026-07-22T13:00:00+00:00",
            pnl=120,
        ))

        fallback_ticker = "KXMLBGAME-26JUL22CCCDDD-CCC"
        ledger.record_decision(
            _decision("fallback", fallback_ticker, tier="B", price=60, count=2)
        )
        ledger.record_outcome(_outcome(
            "fallback",
            fallback_ticker,
            OutcomeKind.ACCEPTED,
            "2026-07-22T11:04:00+00:00",
            broker_contacted=True,
            detail={"state": "submitted"},
        ))
        ledger.record_outcome(_outcome(
            "fallback",
            fallback_ticker,
            OutcomeKind.FILLED,
            "2026-07-22T11:06:00+00:00",
            fill_count=2,
            fill_price=45,
            broker_contacted=True,
            detail={"execution_fee_cents": 1},
        ))
        _settle_market(
            ledger, fallback_ticker, False, "2026-07-22T13:01:00+00:00"
        )
        ledger.record_outcome(_outcome(
            "fallback",
            fallback_ticker,
            OutcomeKind.SETTLED_LOSS,
            "2026-07-22T13:01:00+00:00",
            pnl=-91,
            broker_contacted=True,
        ))

        no_fill_ticker = "KXMLBGAME-26JUL22EEEFFF-EEE"
        ledger.record_decision(_decision("no-fill", no_fill_ticker, tier="A"))
        _settle_market(
            ledger, no_fill_ticker, True, "2026-07-22T13:02:00+00:00"
        )
        ledger.record_outcome(_outcome(
            "no-fill",
            no_fill_ticker,
            OutcomeKind.SETTLED_WIN,
            "2026-07-22T13:02:00+00:00",
            pnl=999,
        ))

        legacy_ticker = "KXMLBGAME-26JUL22GGGHHH-GGG"
        ledger.record_decision(
            _decision("legacy", legacy_ticker, tier="A", version="legacy_v1")
        )
        ledger.record_outcome(_outcome(
            "legacy",
            legacy_ticker,
            OutcomeKind.FILLED,
            "2026-07-22T11:07:00+00:00",
            fill_count=1,
            fill_price=10,
        ))
        ledger.record_outcome(_outcome(
            "legacy",
            legacy_ticker,
            OutcomeKind.SETTLED_WIN,
            "2026-07-22T13:03:00+00:00",
            pnl=999,
        ))

        report = tier_performance_report(ledger._conn)

        overall = report["realized"]["overall"]
        assert overall["n"] == 2
        assert overall["net_pnl_cents"] == 29
        assert overall["entry_cost_plus_fees_cents"] == 171
        assert overall["exact_witnessed_cost_n"] == 1
        assert overall["roi"] == pytest.approx(29 / 171, abs=1e-6)

        a_metrics = report["realized"]["by_tier"]["A"]
        assert a_metrics["n"] == 1
        assert a_metrics["entry_cost_plus_fees_cents"] == 80
        assert a_metrics["net_pnl_cents"] == 120
        assert a_metrics["roi"] == pytest.approx(1.5)
        assert report["realized"]["by_tier"]["B"]["n"] == 1
        assert report["realized"]["by_book"]["shadow"]["overall"]["n"] == 1
        assert report["realized"]["by_book"]["live"]["overall"]["n"] == 1
    finally:
        ledger.close()


def test_tampered_tier_snapshot_hash_is_excluded_from_forecast_metrics(
    tmp_path,
) -> None:
    ledger = AutonomyLedger(tmp_path / "tampered.db")
    try:
        valid = "KXMLBGAME-26JUL22AAABBB-AAA"
        tampered = "KXMLBGAME-26JUL22CCCDDD-CCC"
        _insert_signal(
            ledger,
            valid,
            0.70,
            "2026-07-22T10:00:00+00:00",
            "2026-07-22T10:01:00+00:00",
        )
        _insert_signal(
            ledger,
            tampered,
            0.70,
            "2026-07-22T10:00:00+00:00",
            "2026-07-22T10:01:00+00:00",
        )
        raw = ledger._conn.execute(
            "SELECT features FROM signals WHERE market_ticker=?", (tampered,)
        ).fetchone()[0]
        features = json.loads(raw)
        features["tier_after_fee_edge"] = 0.99
        ledger._conn.execute(
            "UPDATE signals SET features=? WHERE market_ticker=?",
            (json.dumps(features, sort_keys=True, separators=(",", ":")), tampered),
        )
        _settle_market(ledger, valid, True, "2026-07-22T12:00:00+00:00")
        _settle_market(ledger, tampered, True, "2026-07-22T12:00:00+00:00")
        ledger._conn.commit()

        report = tier_performance_report(ledger._conn)

        assert report["forecast"]["overall"]["n"] == 1
        assert report["forecast"]["by_tier"]["B"]["n"] == 1
    finally:
        ledger.close()


def test_post_close_pre_settlement_forecast_is_excluded(tmp_path) -> None:
    ledger = AutonomyLedger(tmp_path / "post-close.db")
    try:
        ticker = "KXMLBGAME-26JUL22AAABBB-AAA"
        _insert_signal(
            ledger,
            ticker,
            0.70,
            "2026-07-22T10:30:00+00:00",
            "2026-07-22T10:31:00+00:00",
            tier="A",
            close_time="2026-07-22T10:00:00+00:00",
        )
        _settle_market(ledger, ticker, True, "2026-07-22T12:00:00+00:00")
        ledger._conn.commit()

        report = tier_performance_report(ledger._conn)

        assert report["forecast"]["overall"]["n"] == 0
    finally:
        ledger.close()


def test_realized_tier_evidence_rejects_cross_market_outcomes(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "autonomy.ledger._now", lambda: "2026-07-22T11:01:00+00:00"
    )
    ledger = AutonomyLedger(tmp_path / "cross-market.db")
    try:
        decision_ticker = "KXMLBGAME-26JUL22AAABBB-AAA"
        other_ticker = "KXMLBGAME-26JUL22CCCDDD-CCC"
        ledger.record_decision(_decision("cross-market", decision_ticker, tier="A"))
        ledger._conn.execute(
            "INSERT INTO outcomes(decision_id,market_ticker,kind,order_id,"
            "fill_count,fill_price_cents,pnl_cents,broker_contacted,detail,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                "cross-market", other_ticker, "SHADOW", "order-cross", 1, 40,
                None, 0,
                json.dumps({"fill_cost_cents": 40, "execution_fee_cents": 1}),
                "2026-07-22T11:05:00+00:00",
            ),
        )
        ledger._conn.execute(
            "INSERT INTO outcomes(decision_id,market_ticker,kind,order_id,"
            "fill_count,fill_price_cents,pnl_cents,broker_contacted,detail,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                "cross-market", other_ticker, "SETTLED_WIN", "order-cross", 0,
                None, 59, 0, "{}", "2026-07-22T13:00:00+00:00",
            ),
        )
        _settle_market(
            ledger, other_ticker, True, "2026-07-22T12:59:00+00:00"
        )
        ledger._conn.commit()

        report = tier_performance_report(ledger._conn)

        assert report["realized"]["overall"]["n"] == 0
    finally:
        ledger.close()


def test_realized_tier_evidence_rejects_impossible_witnessed_cost(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "autonomy.ledger._now", lambda: "2026-07-22T11:01:00+00:00"
    )
    ledger = AutonomyLedger(tmp_path / "impossible-cost.db")
    try:
        ticker = "KXMLBGAME-26JUL22AAABBB-AAA"
        ledger.record_decision(_decision("impossible-cost", ticker, tier="A"))
        ledger.record_outcome(_outcome(
            "impossible-cost",
            ticker,
            OutcomeKind.SHADOW,
            "2026-07-22T11:05:00+00:00",
            fill_count=1,
            fill_price=40,
            detail={"fill_cost_cents": 0, "execution_fee_cents": 0},
        ))
        _settle_market(
            ledger, ticker, True, "2026-07-22T13:00:00+00:00"
        )
        ledger.record_outcome(_outcome(
            "impossible-cost",
            ticker,
            OutcomeKind.SETTLED_WIN,
            "2026-07-22T13:00:00+00:00",
            pnl=100,
        ))

        report = tier_performance_report(ledger._conn)

        assert report["realized"]["overall"]["n"] == 0
    finally:
        ledger.close()


def test_attribution_recorded_after_fill_is_excluded_from_realized_metrics(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "autonomy.ledger._now", lambda: "2026-07-22T11:10:00+00:00"
    )
    ledger = AutonomyLedger(tmp_path / "late-receipt.db")
    try:
        ticker = "KXMLBGAME-26JUL22AAABBB-AAA"
        ledger.record_decision(_decision("late-receipt", ticker, tier="A"))
        ledger.record_outcome(
            _outcome(
                "late-receipt",
                ticker,
                OutcomeKind.SHADOW,
                "2026-07-22T11:05:00+00:00",
                fill_count=1,
                fill_price=40,
                detail={"fill_cost_cents": 40, "execution_fee_cents": 1},
            )
        )
        _settle_market(
            ledger, ticker, True, "2026-07-22T13:00:00+00:00"
        )
        ledger.record_outcome(
            _outcome(
                "late-receipt",
                ticker,
                OutcomeKind.SETTLED_WIN,
                "2026-07-22T13:00:00+00:00",
                pnl=50,
            )
        )

        report = tier_performance_report(ledger._conn)

        assert report["realized"]["overall"] == {
            "n": 0,
            "evidence_status": "COLLECTING_FORWARD_EVIDENCE",
        }
    finally:
        ledger.close()


def test_raw_tier_score_is_persisted_and_compared_at_snapshot_precision(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "autonomy.ledger._now", lambda: "2026-07-22T11:01:00+00:00"
    )
    ledger = AutonomyLedger(tmp_path / "score-rounding.db")
    try:
        ticker = "KXMLBGAME-26JUL22ROUNDING-YES"
        original = _decision("score-rounding", ticker, tier="A")
        snapshot_score = float(original.tier_snapshot["tier_score"])
        decision = replace(original, tier_score=snapshot_score + 0.0000004)
        ledger.record_decision(decision)
        stored_score = ledger._conn.execute(
            "SELECT tier_score FROM decisions WHERE decision_id=?",
            (decision.decision_id,),
        ).fetchone()[0]
        assert stored_score == snapshot_score

        ledger.record_outcome(_outcome(
            decision.decision_id,
            ticker,
            OutcomeKind.SHADOW,
            "2026-07-22T11:05:00+00:00",
            fill_count=1,
            fill_price=40,
            detail={"fill_cost_cents": 40, "execution_fee_cents": 1},
        ))
        _settle_market(ledger, ticker, True, "2026-07-22T13:00:00+00:00")
        ledger.record_outcome(_outcome(
            decision.decision_id,
            ticker,
            OutcomeKind.SETTLED_WIN,
            "2026-07-22T13:00:00+00:00",
            pnl=59,
        ))

        assert tier_performance_report(ledger._conn)["realized"]["overall"]["n"] == 1
    finally:
        ledger.close()


def test_realized_evidence_requires_matching_canonical_settlement(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "autonomy.ledger._now", lambda: "2026-07-22T11:01:00+00:00"
    )
    ledger = AutonomyLedger(tmp_path / "canonical-settlement.db")
    try:
        for suffix in ("MISSING", "OPPOSITE"):
            ticker = f"KXMLBGAME-26JUL22{suffix}-YES"
            decision_id = suffix.lower()
            ledger.record_decision(_decision(decision_id, ticker, tier="A"))
            ledger.record_outcome(_outcome(
                decision_id,
                ticker,
                OutcomeKind.SHADOW,
                "2026-07-22T11:05:00+00:00",
                fill_count=1,
                fill_price=40,
                detail={"fill_cost_cents": 40, "execution_fee_cents": 1},
            ))
            if suffix == "OPPOSITE":
                _settle_market(
                    ledger, ticker, False, "2026-07-22T13:00:00+00:00"
                )
            ledger.record_outcome(_outcome(
                decision_id,
                ticker,
                OutcomeKind.SETTLED_WIN,
                "2026-07-22T13:00:00+00:00",
                pnl=59,
            ))

        assert tier_performance_report(ledger._conn)["realized"]["overall"]["n"] == 0
    finally:
        ledger.close()


@pytest.mark.parametrize(
    ("decision_id", "fill_count", "fill_at", "settled_at"),
    [
        ("oversized", 2, "2026-07-22T11:05:00+00:00", "2026-07-22T13:00:00+00:00"),
        ("after-close", 1, "2026-07-23T09:00:00+00:00", "2026-07-23T10:00:00+00:00"),
        ("at-settlement", 1, "2026-07-22T13:00:00+00:00", "2026-07-22T13:00:00+00:00"),
    ],
)
def test_realized_evidence_rejects_invalid_fill_size_or_chronology(
    tmp_path,
    monkeypatch,
    decision_id: str,
    fill_count: int,
    fill_at: str,
    settled_at: str,
) -> None:
    monkeypatch.setattr(
        "autonomy.ledger._now", lambda: "2026-07-22T11:01:00+00:00"
    )
    ledger = AutonomyLedger(tmp_path / f"{decision_id}.db")
    try:
        ticker = f"KXMLBGAME-26JUL22{decision_id.upper()}-YES"
        ledger.record_decision(_decision(decision_id, ticker, tier="A", count=1))
        ledger.record_outcome(_outcome(
            decision_id,
            ticker,
            OutcomeKind.SHADOW,
            fill_at,
            fill_count=fill_count,
            fill_price=40,
            detail={
                "fill_cost_cents": 40 * fill_count,
                "execution_fee_cents": fill_count,
            },
        ))
        _settle_market(ledger, ticker, True, settled_at)
        ledger.record_outcome(_outcome(
            decision_id,
            ticker,
            OutcomeKind.SETTLED_WIN,
            settled_at,
            pnl=59 * fill_count,
        ))

        assert tier_performance_report(ledger._conn)["realized"]["overall"]["n"] == 0
    finally:
        ledger.close()


def test_non_shadow_fill_without_broker_contact_is_not_classified_live(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "autonomy.ledger._now", lambda: "2026-07-22T11:01:00+00:00"
    )
    ledger = AutonomyLedger(tmp_path / "unverified-book.db")
    try:
        ticker = "KXMLBGAME-26JUL22UNVERIFIED-YES"
        ledger.record_decision(_decision("unverified", ticker, tier="A"))
        ledger.record_outcome(_outcome(
            "unverified",
            ticker,
            OutcomeKind.FILLED,
            "2026-07-22T11:05:00+00:00",
            fill_count=1,
            fill_price=40,
            broker_contacted=False,
            detail={"fill_cost_cents": 40, "execution_fee_cents": 1},
        ))
        _settle_market(ledger, ticker, True, "2026-07-22T13:00:00+00:00")
        ledger.record_outcome(_outcome(
            "unverified",
            ticker,
            OutcomeKind.SETTLED_WIN,
            "2026-07-22T13:00:00+00:00",
            pnl=59,
        ))

        report = tier_performance_report(ledger._conn)
        assert report["realized"]["overall"]["n"] == 0
        assert report["realized"]["by_book"]["live"]["overall"]["n"] == 0
    finally:
        ledger.close()


def test_market_comparison_uses_only_digest_bound_executable_quote(tmp_path) -> None:
    ledger = AutonomyLedger(tmp_path / "market-baseline.db")
    try:
        ticker = "KXMLBGAME-26JUL22BASELINE-YES"
        _insert_signal(
            ledger,
            ticker,
            0.70,
            "2026-07-22T10:00:00+00:00",
            "2026-07-22T10:01:00+00:00",
            tier="B",
        )
        _settle_market(ledger, ticker, True, "2026-07-22T12:00:00+00:00")
        ledger._conn.commit()
        before = tier_performance_report(ledger._conn)["forecast"]["overall"]

        raw = ledger._conn.execute(
            "SELECT features FROM signals WHERE market_ticker=?", (ticker,)
        ).fetchone()[0]
        features = json.loads(raw)
        features["market_implied_yes"] = 0.0
        ledger._conn.execute(
            "UPDATE signals SET features=? WHERE market_ticker=?",
            (
                json.dumps(features, sort_keys=True, separators=(",", ":")),
                ticker,
            ),
        )
        ledger._conn.commit()

        after = tier_performance_report(ledger._conn)["forecast"]["overall"]
        assert after["n"] == 1
        assert after["market_comparison_baseline"] == (
            "selected_side_executable_ask_bound_to_tier_snapshot"
        )
        assert after["mean_market_brier"] == before["mean_market_brier"]
        assert after["brier_advantage_vs_market"] == before["brier_advantage_vs_market"]
    finally:
        ledger.close()


def test_thirty_rows_from_one_event_remain_insufficient_forward_evidence(
    tmp_path,
) -> None:
    ledger = AutonomyLedger(tmp_path / "clustered.db")
    try:
        for index in range(30):
            ticker = f"KXMLBTOTAL-26JUL22ONEEVENT-T{index}"
            _insert_signal(
                ledger,
                ticker,
                0.70,
                "2026-07-22T10:00:00+00:00",
                "2026-07-22T10:01:00+00:00",
            )
            _settle_market(
                ledger, ticker, index % 2 == 0, "2026-07-22T12:00:00+00:00"
            )
        ledger._conn.commit()

        overall = tier_performance_report(ledger._conn)["forecast"]["overall"]

        assert overall["n"] == 30
        assert overall["event_clusters"] == 1
        assert overall["evidence_status"] == "INSUFFICIENT_SAMPLE"
        assert overall["value_side_hit_rate_cluster_ci95"] is None
    finally:
        ledger.close()


def test_cluster_bootstrap_matches_row_weighted_hit_rate_with_imbalanced_events(
    tmp_path,
) -> None:
    ledger = AutonomyLedger(tmp_path / "imbalanced-clusters.db")
    try:
        # One large event contributes 100 wins; nine independent one-row events
        # contribute losses.  The displayed hit rate is therefore row-weighted
        # (100 / 109), not the equal-cluster-weighted rate (1 / 10).
        for index in range(100):
            ticker = f"KXMLBTOTAL-26JUL22BIGEVENT-T{index}"
            _insert_signal(
                ledger,
                ticker,
                0.70,
                "2026-07-22T10:00:00+00:00",
                "2026-07-22T10:01:00+00:00",
            )
            _settle_market(ledger, ticker, True, "2026-07-22T12:00:00+00:00")
        for index in range(9):
            ticker = f"KXMLBGAME-26JUL22SMALL{index:02d}-AAA"
            _insert_signal(
                ledger,
                ticker,
                0.70,
                "2026-07-22T10:00:00+00:00",
                "2026-07-22T10:01:00+00:00",
            )
            _settle_market(ledger, ticker, False, "2026-07-22T12:00:00+00:00")
        ledger._conn.commit()

        overall = tier_performance_report(ledger._conn)["forecast"]["overall"]
        point_estimate = overall["value_side_hit_rate"]
        interval = overall["value_side_hit_rate_cluster_ci95"]

        assert overall["n"] == 109
        assert overall["event_clusters"] == 10
        assert point_estimate == pytest.approx(100 / 109, abs=1e-4)
        assert interval["event_clusters"] == 10
        assert interval["low"] <= point_estimate <= interval["high"]
    finally:
        ledger.close()


def test_tier_performance_endpoint_is_snapshot_and_board_backed(
    tmp_path, monkeypatch,
) -> None:
    from datetime import datetime, timedelta, timezone

    from fastapi.testclient import TestClient

    from autonomy import dashboard
    from autonomy.bet_board import write_board_artifact

    snapshot = {
        "generated_at": "2026-07-22T14:00:00+00:00",
        "backtest_generated_at": "2026-07-22T13:00:00+00:00",
        "backtest": {},
    }
    (tmp_path / "latest_dashboard_snapshot.json").write_text(
        json.dumps(snapshot), encoding="utf-8",
    )
    board_now = datetime.now(timezone.utc)
    ticker = "KXMLBGAME-26JUL22AAABBB-AAA"
    market = SimpleNamespace(
        ticker=ticker,
        title="AAA vs BBB Winner?",
        yes_bid=39,
        yes_ask=40,
        no_bid=59,
        no_ask=60,
        liquidity=1000,
        fetched_at=(board_now - timedelta(seconds=5)).isoformat(),
        close_time=(board_now + timedelta(hours=4)).isoformat(),
        status="open",
    )
    write_board_artifact(
        [(market, _forecast(ticker))],
        path=tmp_path / "bet_board.json",
        now_iso=board_now.isoformat(),
    )
    monkeypatch.setattr(dashboard, "RUNTIME_DIR", tmp_path)

    response = TestClient(dashboard.build_app()).get("/api/tier-performance")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "UNAVAILABLE"
    assert payload["performance_artifact_status"] == "MISSING"
    assert payload["board_artifact_status"] == "FRESH"
    assert payload["board_stale"] is False
