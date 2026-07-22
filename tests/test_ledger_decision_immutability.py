from __future__ import annotations

from dataclasses import replace

import pytest

from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Decision, DecisionAction, Forecast
from autonomy.ontology import OutcomeKind, TradeOutcome


def _forecast() -> Forecast:
    return Forecast(
        market_ticker="KXIMMUTABLE-26JUL22-YES",
        probability_yes=0.61,
        uncertainty=0.08,
        sources_used={"model_b": 0.4, "model_a": 0.6},
        market_implied_yes=0.54,
        edge_yes=0.07,
        rationale="test forecast",
    )


def _decision(*, attributed: bool = True) -> Decision:
    return Decision(
        decision_id="immutable-decision-1",
        market_ticker="KXIMMUTABLE-26JUL22-YES",
        action=DecisionAction.BUY_YES,
        side="yes",
        price_cents=55,
        count=2,
        ev_cents_per_contract=6.0,
        kelly_fraction=0.02,
        notional_cents=110,
        forecast=_forecast(),
        risk_snapshot={"bankroll_cents": 100_000},
        created_at="2026-07-22T15:00:00+00:00",
        tier_label="B" if attributed else None,
        tier_policy_version="test-policy-v1" if attributed else None,
        tier_score=0.03 if attributed else None,
        tier_reason="quoted edge" if attributed else "",
        tier_snapshot={"tier": "B", "after_fee_edge": 0.03} if attributed else {},
    )


def test_exact_decision_replay_is_idempotent_without_replacing_row(tmp_path) -> None:
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    decision = _decision()
    try:
        ledger.record_decision(decision)
        before = ledger._conn.execute(
            "SELECT rowid,* FROM decisions WHERE decision_id=?",
            (decision.decision_id,),
        ).fetchone()
        attribution_before = ledger._conn.execute(
            "SELECT * FROM decision_tier_attribution WHERE decision_id=?",
            (decision.decision_id,),
        ).fetchone()

        ledger.record_decision(decision)

        after = ledger._conn.execute(
            "SELECT rowid,* FROM decisions WHERE decision_id=?",
            (decision.decision_id,),
        ).fetchone()
        attribution_after = ledger._conn.execute(
            "SELECT * FROM decision_tier_attribution WHERE decision_id=?",
            (decision.decision_id,),
        ).fetchone()
        assert after == before
        assert attribution_after == attribution_before
    finally:
        ledger.close()


def test_changed_attributed_decision_replay_is_rejected_and_original_survives(
    tmp_path,
) -> None:
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    decision = _decision()
    try:
        ledger.record_decision(decision)
        before = ledger._conn.execute(
            "SELECT rowid,* FROM decisions WHERE decision_id=?",
            (decision.decision_id,),
        ).fetchone()

        with pytest.raises(ValueError, match="decision record is immutable"):
            ledger.record_decision(replace(decision, price_cents=56))

        after = ledger._conn.execute(
            "SELECT rowid,* FROM decisions WHERE decision_id=?",
            (decision.decision_id,),
        ).fetchone()
        assert after == before
    finally:
        ledger.close()


def test_changed_unattributed_decision_replay_is_also_rejected(tmp_path) -> None:
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    decision = _decision(attributed=False)
    try:
        ledger.record_decision(decision)

        with pytest.raises(ValueError, match="decision record is immutable"):
            ledger.record_decision(
                replace(
                    decision,
                    forecast=replace(decision.forecast, probability_yes=0.62),
                )
            )

        stored_probability = ledger._conn.execute(
            "SELECT probability_yes FROM decisions WHERE decision_id=?",
            (decision.decision_id,),
        ).fetchone()[0]
        assert stored_probability == pytest.approx(0.61)
    finally:
        ledger.close()


def test_decision_rejects_forecast_for_a_different_market(tmp_path) -> None:
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    decision = _decision(attributed=False)
    try:
        with pytest.raises(ValueError, match="market identity must match"):
            ledger.record_decision(
                replace(
                    decision,
                    forecast=replace(
                        decision.forecast,
                        market_ticker="KXOTHER-26JUL22-YES",
                    ),
                )
            )
    finally:
        ledger.close()


def test_outcome_rejects_market_different_from_decision(tmp_path) -> None:
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    decision = _decision(attributed=False)
    try:
        ledger.record_decision(decision)
        outcome = TradeOutcome(
            decision_id=decision.decision_id,
            market_ticker="KXOTHER-26JUL22-YES",
            kind=OutcomeKind.FILLED,
            order_id="order-1",
            fill_count=1,
            fill_price_cents=50,
            pnl_cents=None,
            broker_contacted=False,
        )

        with pytest.raises(ValueError, match="market identity must match"):
            ledger.record_outcome(outcome)
    finally:
        ledger.close()
