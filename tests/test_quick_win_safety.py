"""Regression coverage for debate truth and local fee freshness guards."""

from __future__ import annotations

import asyncio
import types
from datetime import date, datetime, timedelta, timezone

import pytest

from autonomy.brain import CycleReport, PredatorBrain
from autonomy.debate import DebateResult, PanelOpinion
from autonomy.fees import (
    FeeScheduleRefreshWarning,
    fee_schedule_freshness,
    fee_schedule_refresh_warning,
    kalshi_maker_fee_cents,
)
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import MarketView, Vertical


def test_fee_schedule_warns_before_last_fresh_date_without_refreshing():
    comfortably_fresh = fee_schedule_freshness(date(2026, 7, 30))
    assert comfortably_fresh.status == "FRESH"
    assert comfortably_fresh.warning is None

    refresh_due = fee_schedule_freshness(date(2026, 7, 31))
    assert refresh_due.status == "REFRESH_DUE"
    assert refresh_due.last_fresh_date == date(2026, 8, 7)
    assert refresh_due.fail_closed_from == date(2026, 8, 8)
    assert refresh_due.days_until_last_fresh_date == 7
    assert refresh_due.days_until_fail_closed == 8
    assert refresh_due.refresh_recommended is True
    assert fee_schedule_refresh_warning(date(2026, 7, 31)) == refresh_due.warning

    with pytest.warns(FeeScheduleRefreshWarning, match="last fresh date"):
        fee = kalshi_maker_fee_cents(
            50,
            10,
            "KXMLBGAME-26JUL10-ABC",
            as_of=date(2026, 7, 31),
        )
    assert fee == 5


def test_fee_schedule_stale_status_keeps_conservative_fallback():
    stale = fee_schedule_freshness(date(2026, 8, 8))
    assert stale.status == "STALE"
    assert stale.fresh is False
    assert stale.refresh_recommended is True
    assert stale.warning is not None
    assert "failing closed to taker" in stale.warning
    assert (
        kalshi_maker_fee_cents(
            50,
            10,
            "KXMLBGAME-26JUL10-ABC",
            as_of=date(2026, 8, 8),
        )
        == 18
    )


def test_debate_records_observations_without_dead_refusion(monkeypatch, tmp_path):
    monkeypatch.setenv("DUMMY_DEBATE_TOP_K", "1")
    monkeypatch.setenv("DUMMY_DEBATE_CLI_TOP_K", "0")
    monkeypatch.setenv("DUMMY_DEBATE_MAX_LOGICAL_CALLS_PER_CYCLE", "8")

    providers = (
        "gpt_5_6_terra",
        "gpt_5_6_luna",
        "claude_sonnet_5",
        "glm_5_2",
    )
    result = DebateResult(
        probability_yes=0.6,
        uncertainty=0.18,
        opinions=[
            PanelOpinion(provider, provider, 0.6, 0.6, 0.7, "test")
            for provider in providers
        ],
        complete_hybrid=True,
    )

    async def fake_run_debate(*_args, **_kwargs):
        return result

    monkeypatch.setattr("autonomy.debate.run_debate", fake_run_debate)

    market = MarketView(
        ticker="KXTEST-DEBATE",
        title="Test market",
        vertical=Vertical.OTHER,
        status="active",
        close_time=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        yes_bid=40,
        yes_ask=50,
        no_bid=50,
        no_ask=60,
        volume=100,
        liquidity=100,
        raw={"rules_primary": "resolves yes if X"},
    )
    forecast = types.SimpleNamespace(probability_yes=0.55)
    scored = [(market, forecast, [])]

    ledger = AutonomyLedger(db_path=tmp_path / "ledger.db")
    try:
        brain = types.SimpleNamespace(router=object(), ledger=ledger)
        report = CycleReport(
            status="",
            mode="shadow",
            stage=1,
            bankroll_cents=0,
        )
        asyncio.run(
            PredatorBrain._adjudicate_top_k(
                brain,
                scored,
                report,
            )
        )
    finally:
        ledger.close()

    assert scored == [(market, forecast, [])]
    assert any(note.startswith("debate:recorded_only:") for note in report.notes)
