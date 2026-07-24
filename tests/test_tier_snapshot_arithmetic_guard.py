"""Wave-84 Bug 1: a tier snapshot with no executable side must never be
arithmetic-crashed on.

Live evidence (runtime/autonomy/cycles.jsonl, four CYCLE_ERROR:TypeError cycles
on 2026-07-24)::

    File "autonomy/brain.py", line 1035, in run_cycle
        self.ledger.record_decision(decision)
    File "autonomy/ledger.py", line 783, in record_decision
        - float(snapshot["tier_entry_price_cents"]) / 100.0
    TypeError: float() argument must be a string or a real number, not 'NoneType'

The snapshot was a *valid* ``no_executable_depth`` assessment: no two-sided
quote existed, so the contract requires its side and entry price to be None.
record_decision cross-checked it as if it were an executable one. An
observational classification must never be able to kill the decide/execute
path, and an unusable snapshot must be classified, never crashed on.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Decision, DecisionAction, Forecast
from autonomy.tier_policy import (
    _tier_snapshot_digest,
    assess_market_tier,
    tier_snapshot_is_executable,
    tier_snapshot_is_valid,
)

TICKER = "KXMLBGAME-26JUL18NYYBOS-NYY"
ASSESS_AT = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


def _market(*, liquidity: object = 500, raw: dict[str, object] | None = None):
    return SimpleNamespace(
        ticker=TICKER,
        yes_ask=50,
        no_ask=50,
        yes_bid=49,
        no_bid=49,
        liquidity=liquidity,
        raw=raw or {},
        fetched_at=(ASSESS_AT - timedelta(seconds=30)).isoformat(),
        close_time=(ASSESS_AT + timedelta(days=1)).isoformat(),
        status="open",
    )


def _forecast(probability: float = 0.56, *, uncertainty: float = 0.10) -> Forecast:
    return Forecast(
        market_ticker=TICKER,
        probability_yes=probability,
        uncertainty=uncertainty,
        sources_used={"unit": 1.0},
        market_implied_yes=0.50,
        edge_yes=probability - 0.50,
        rationale="tier snapshot guard",
    )


def _decision(
    assessment,
    forecast: Forecast,
    *,
    decision_id: str,
    action: DecisionAction = DecisionAction.ABSTAIN,
    snapshot: dict | None = None,
) -> Decision:
    executable = action is not DecisionAction.ABSTAIN
    return Decision(
        decision_id=decision_id,
        market_ticker=TICKER,
        action=action,
        side=(assessment.side or "") if executable else "",
        price_cents=(assessment.entry_price_cents or 0) if executable else 0,
        count=1 if executable else 0,
        ev_cents_per_contract=0.0,
        kelly_fraction=0.0,
        notional_cents=0,
        forecast=forecast,
        risk_snapshot={},
        created_at="2026-07-22T12:00:00+00:00",
        tier_label=assessment.tier,
        tier_policy_version=assessment.policy_version,
        tier_score=assessment.score,
        tier_reason=assessment.reason,
        tier_snapshot=assessment.feature_fields() if snapshot is None else snapshot,
    )


def _no_depth_assessment():
    # Zero legacy liquidity and no quote sizes -> no executable depth. This is
    # the exact shape the live cycles carried.
    assessment = assess_market_tier(
        _market(liquidity=0), _forecast(), now=ASSESS_AT,
    )
    assert assessment.reason == "no_executable_depth"
    return assessment


def _graded_assessment():
    assessment = assess_market_tier(_market(), _forecast(), now=ASSESS_AT)
    assert assessment.tier in {"A", "B", "C"}
    return assessment


def test_no_depth_snapshot_is_valid_evidence_but_not_executable() -> None:
    snapshot = _no_depth_assessment().feature_fields()

    # Both halves matter: the board displays this row honestly *because* it is
    # valid, and consumers must still know not to price-arithmetic it.
    assert tier_snapshot_is_valid(snapshot, ticker=TICKER) is True
    assert tier_snapshot_is_executable(snapshot) is False
    assert snapshot["tier_entry_price_cents"] is None
    assert snapshot["tier_side"] is None


def test_abstain_decision_carrying_a_no_depth_snapshot_records_without_raising(
    tmp_path,
) -> None:
    assessment = _no_depth_assessment()
    forecast = _forecast()
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        ledger.record_decision(
            _decision(assessment, forecast, decision_id="no-depth-1")
        )

        row = ledger._conn.execute(  # noqa: SLF001 - direct row assertion
            "SELECT tier_label,tier_policy_version,tier_score,tier_reason"
            " FROM decisions WHERE decision_id=?",
            ("no-depth-1",),
        ).fetchone()
        # Recorded, unlabelled, and honest about why -- not crashed, and no
        # letter tier laundered onto an unquotable market.
        assert row == (None, assessment.policy_version, None, "no_executable_depth")
    finally:
        ledger.close()


@pytest.mark.parametrize(
    "field",
    (
        "tier_entry_price_cents",
        "tier_modeled_fee_cents",
        "tier_gross_executable_edge",
        "tier_after_fee_edge",
        "tier_score",
        "tier_uncertainty",
    ),
)
@pytest.mark.parametrize("bad", (None, "missing", "not-a-number", float("nan")))
def test_snapshot_claiming_a_side_without_its_numerics_is_invalid(
    field: str, bad: object,
) -> None:
    snapshot = _graded_assessment().feature_fields()
    if bad == "missing":
        snapshot.pop(field)
    else:
        snapshot[field] = bad
    # Re-seal the digest: without this the snapshot would be rejected as
    # tampered, which would prove nothing about the numeric contract.
    snapshot["tier_snapshot_sha256"] = _tier_snapshot_digest(snapshot)

    assert snapshot.get("tier_side") in {"yes", "no"}
    assert tier_snapshot_is_executable(snapshot) is False
    assert tier_snapshot_is_valid(snapshot, ticker=TICKER) is False


@pytest.mark.parametrize("field", ("tier_entry_price_cents", "tier_gross_executable_edge"))
def test_decision_with_a_sided_but_numberless_snapshot_is_classified_not_crashed(
    tmp_path, field: str,
) -> None:
    assessment = _graded_assessment()
    snapshot = assessment.feature_fields()
    snapshot[field] = None
    snapshot["tier_snapshot_sha256"] = _tier_snapshot_digest(snapshot)
    decision = _decision(
        assessment,
        _forecast(),
        decision_id=f"numberless-{field}",
        action=DecisionAction.BUY_YES,
        snapshot=snapshot,
    )
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        # ValueError (a classification), never TypeError (an arithmetic crash).
        with pytest.raises(ValueError, match="not a valid current-policy"):
            ledger.record_decision(decision)
    finally:
        ledger.close()


def test_genuine_executable_snapshot_still_validates_and_attributes(tmp_path) -> None:
    assessment = _graded_assessment()
    forecast = _forecast()
    snapshot = assessment.feature_fields()
    assert tier_snapshot_is_valid(snapshot, ticker=TICKER) is True
    assert tier_snapshot_is_executable(snapshot) is True

    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        ledger.record_decision(
            _decision(
                assessment, forecast,
                decision_id="graded-1", action=DecisionAction.BUY_YES,
            )
        )

        row = ledger._conn.execute(  # noqa: SLF001 - direct row assertion
            "SELECT policy_version,tier_label,tier_reason"
            " FROM decision_tier_attribution WHERE decision_id=?",
            ("graded-1",),
        ).fetchone()
        assert row == (
            assessment.policy_version, assessment.tier, assessment.reason,
        )
    finally:
        ledger.close()


def test_valid_but_mismatched_snapshot_still_fails_closed(tmp_path) -> None:
    assessment = _graded_assessment()
    # Same market, different forecast than the one the snapshot froze: the
    # snapshot is internally valid, but it no longer describes this decision.
    decision = _decision(
        assessment,
        _forecast(0.75),
        decision_id="mismatched-1",
        action=DecisionAction.BUY_YES,
    )
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        with pytest.raises(ValueError, match="does not match its frozen tier snapshot"):
            ledger.record_decision(decision)

        assert ledger._conn.execute(  # noqa: SLF001 - nothing may be written
            "SELECT COUNT(*) FROM decisions"
        ).fetchone()[0] == 0
    finally:
        ledger.close()


def test_no_depth_snapshot_cannot_smuggle_a_letter_tier(tmp_path) -> None:
    assessment = _no_depth_assessment()
    decision = replace(
        _decision(assessment, _forecast(), decision_id="smuggle-1"),
        tier_label="A",
    )
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        with pytest.raises(ValueError, match="not a valid current-policy"):
            ledger.record_decision(decision)
    finally:
        ledger.close()
