"""Adversarial automatic-promotion truth gates."""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from autonomy.auto_promotion import (
    AutoPromotionEngine,
    PromotionConfig,
    RailsVerdict,
)
from autonomy.strategy_miner import MinedRow


SCOPE = "candidate_source|btc|15m_direction|15m"
BASE = datetime(2026, 7, 1, tzinfo=timezone.utc)
CONFIG = PromotionConfig(
    min_clusters=8,
    min_clusters_no_clv=8,
    min_span_days=1.0,
    min_beat_rate=0.6,
    stage1_min_forward_trades=8,
    stage1_min_forward_clusters=5,
    stage1_min_forward_span_days=1.0,
    roi_path_min_clusters=8,
    roi_path_min_span_days=1.0,
)


def _rows() -> list[MinedRow]:
    return [
        MinedRow(
            source="candidate_source",
            ticker=f"KXBTC15M-C{i:03d}-T100000",
            event_cluster=f"KXBTC15M-C{i:03d}",
            created_at=(BASE + timedelta(hours=4 * i)).isoformat(),
            probability_yes=0.80,
            market_probability=0.55,
            result_yes=True,
            features={"challenger_only": True, "promotion_eligible": True},
            scope=SCOPE,
        )
        for i in range(12)
    ]


def _forward_evidence(*, clusters: int = 8) -> dict:
    fingerprint = hashlib.sha256(SCOPE.encode("utf-8")).hexdigest()
    values = {f"forward-{i}": [] for i in range(clusters)}
    timestamps: list[str] = []
    for index in range(8):
        values[f"forward-{index % clusters}"].append(0.50)
        timestamps.append((BASE + timedelta(hours=4 * index)).isoformat())
    return {
        "n_trades": 8,
        "pnl_by_cluster": values,
        "evidence_origin": "ledger_verified",
        "receipt_bounded": True,
        "witnessed_fill_net_pnl": True,
        "forward_evidence": {
            "evidence_version": "promotion_forward_fill_v1",
            "evidence_origin": "ledger_verified",
            "receipt_bounded": True,
            "witnessed_fill_net_pnl": True,
            "out_of_sample_after_registration": True,
            "isolated_candidate_decisions": True,
            "registered_at": (BASE - timedelta(days=1)).isoformat(),
            "candidate_fingerprint": fingerprint,
            "n_trades": 8,
            "pnl_by_cluster": values,
            "trade_timestamps": timestamps,
        },
    }


def _decide(*, rows=None, realized=None, config: PromotionConfig = CONFIG):
    return AutoPromotionEngine(config).decide(
        scope_rows={SCOPE: list(rows or _rows())},
        promoted={},
        now_ts=(BASE + timedelta(days=10)).timestamp(),
        now_iso=(BASE + timedelta(days=10)).isoformat(),
        rails=RailsVerdict(abort=False),
        clv_by_scope={SCOPE: {"lower": 1.0, "mean": 2.0, "upper": 3.0}},
        realized_by_scope=({SCOPE: realized} if realized is not None else {}),
        eligible_scopes={SCOPE},
    )


def test_fill_free_positive_counterfactual_is_human_review_only():
    result = _decide()
    assert result.promotions == []
    assert len(result.human_review_candidates) == 1
    dossier = result.human_review_candidates[0].dossier
    assert dossier["counterfactual_pnl_ci95_lower"]["pass"] is True
    assert dossier["counterfactual_pnl_ci95_lower"]["witnessed_fill_evidence"] is False
    assert dossier["counterfactual_pnl_ci95_lower"]["automatic_promotion_authority"] is False
    assert dossier["forward_witnessed_fill_evidence"]["pass"] is False


def test_in_sample_roi_diagnostic_never_auto_promotes():
    config = replace(CONFIG, min_beat_rate=1.01)
    result = _decide(config=config)
    assert result.promotions == []
    assert len(result.human_review_candidates) == 1
    diagnostic = result.human_review_candidates[0].dossier[
        "counterfactual_roi_diagnostic"
    ]
    assert diagnostic["pass"] is True
    assert diagnostic["research_only"] is True
    assert diagnostic["automatic_promotion_authority"] is False


def test_insufficient_independent_forward_clusters_fail_closed():
    result = _decide(realized=_forward_evidence(clusters=2))
    assert result.promotions == []
    forward = result.human_review_candidates[0].dossier[
        "forward_witnessed_fill_evidence"
    ]
    assert forward["n_trades"] == 8
    assert forward["event_clusters"] == 2
    assert forward["gates"]["minimum_event_clusters"] is False


def test_valid_forward_witnessed_fill_evidence_can_reach_probation():
    result = _decide(realized=_forward_evidence())
    assert len(result.promotions) == 1
    assert result.human_review_candidates == []
    decision = result.promotions[0]
    assert decision.stage == 1
    assert decision.weight_fraction == CONFIG.stage1_weight_fraction
    assert decision.dossier["promotion_path"] == "forward_witnessed_fill_v1"
    assert decision.dossier["forward_witnessed_fill_evidence"]["pass"] is True


def test_runner_derives_forward_lane_from_registered_isolated_witnessed_fill(tmp_path):
    from autonomy.auto_promotion_runner import realized_attribution
    from autonomy.ledger import AutonomyLedger
    from autonomy.ontology import (
        Decision,
        DecisionAction,
        Forecast,
        OutcomeKind,
        Signal,
        TradeOutcome,
    )

    fingerprint = hashlib.sha256(SCOPE.encode("utf-8")).hexdigest()
    registered_at = "2026-07-01T00:00:00+00:00"
    ticker = "KXBTC15M-26JUL02-T100000"
    ledger = AutonomyLedger(db_path=tmp_path / "ledger.db")
    try:
        assert ledger.record_signal(Signal(
            source="candidate_source",
            market_ticker=ticker,
            probability_yes=0.80,
            uncertainty=0.10,
            rationale="sealed candidate",
            features={
                "challenger_only": True,
                "promotion_eligible": True,
                "promotion_candidate_fingerprint": fingerprint,
                "vertical": "CRYPTO",
                "market_type": "15m_direction",
                "hours_to_close": 0.2,
            },
            created_at="2026-07-02T01:00:00+00:00",
        ), mode="live")
        ledger._conn.execute(  # noqa: SLF001
            "UPDATE signals SET ingested_at=? WHERE source=? AND market_ticker=?",
            ("2026-07-02T01:01:00+00:00", "candidate_source", ticker),
        )
        ledger._conn.commit()  # noqa: SLF001
        forecast = Forecast(
            market_ticker=ticker,
            probability_yes=0.80,
            uncertainty=0.10,
            sources_used={"candidate_source": 1.0},
            market_implied_yes=0.55,
            edge_yes=0.25,
            rationale="isolated forward cohort",
        )
        ledger.record_decision(Decision(
            decision_id="forward-1",
            market_ticker=ticker,
            action=DecisionAction.BUY_YES,
            side="yes",
            price_cents=55,
            count=1,
            ev_cents_per_contract=25.0,
            kelly_fraction=0.01,
            notional_cents=55,
            forecast=forecast,
            risk_snapshot={},
            created_at="2026-07-02T01:02:00+00:00",
        ))
        ledger.record_outcome(TradeOutcome(
            decision_id="forward-1",
            market_ticker=ticker,
            kind=OutcomeKind.FILLED,
            order_id="shadow-1",
            fill_count=1,
            fill_price_cents=55,
            pnl_cents=None,
            broker_contacted=False,
            created_at="2026-07-02T01:03:00+00:00",
        ))
        ledger.record_settlement(ticker, True)
        ledger._conn.execute(  # noqa: SLF001
            "UPDATE settlements SET settled_at=? WHERE market_ticker=?",
            ("2026-07-02T02:00:00+00:00", ticker),
        )
        ledger._conn.commit()  # noqa: SLF001
        ledger.record_outcome(TradeOutcome(
            decision_id="forward-1",
            market_ticker=ticker,
            kind=OutcomeKind.SETTLED_WIN,
            order_id="shadow-1",
            fill_count=1,
            fill_price_cents=55,
            pnl_cents=45,
            broker_contacted=False,
            created_at="2026-07-02T02:01:00+00:00",
        ))
    finally:
        ledger.close()

    connection = sqlite3.connect(tmp_path / "ledger.db")
    try:
        result = realized_attribution(connection, forward_registrations={
            SCOPE: {
                "scope": SCOPE,
                "registered_at": registered_at,
                "candidate_fingerprint": fingerprint,
            },
        })
    finally:
        connection.close()
    forward = result[SCOPE]["forward_evidence"]
    assert forward["n_trades"] == 1
    assert forward["receipt_bounded"] is True
    assert forward["witnessed_fill_net_pnl"] is True
    assert forward["out_of_sample_after_registration"] is True
    assert forward["isolated_candidate_decisions"] is True
