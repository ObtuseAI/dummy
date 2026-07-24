"""Regression coverage for the executable-value betting-guide tiers."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Decision, DecisionAction, Forecast
from autonomy.picks import build_fused_signal
from autonomy.tier_policy import (
    TIER_POLICY_SPEC,
    TIER_POLICY_VERSION,
    assess_market_tier,
    assign_cycle_tiers,
    tier_snapshot_is_valid,
)


TICKER = "KXMLBGAME-26JUL18NYYBOS-NYY"
ASSESS_AT = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
_DEFAULT = object()


def _market(
    ticker: str = TICKER,
    *,
    yes_ask: object = 50,
    no_ask: object = 50,
    yes_bid: object = 49,
    no_bid: object = 49,
    liquidity: object = 500,
    raw: dict[str, object] | None = None,
    fetched_at: object = _DEFAULT,
    close_time: object = _DEFAULT,
    status: object = "open",
) -> SimpleNamespace:
    if fetched_at is _DEFAULT:
        fetched_at = (ASSESS_AT - timedelta(seconds=30)).isoformat()
    if close_time is _DEFAULT:
        close_time = (ASSESS_AT + timedelta(days=1)).isoformat()
    return SimpleNamespace(
        ticker=ticker,
        yes_ask=yes_ask,
        no_ask=no_ask,
        yes_bid=yes_bid,
        no_bid=no_bid,
        liquidity=liquidity,
        raw=raw or {},
        fetched_at=fetched_at,
        close_time=close_time,
        status=status,
    )


def _forecast(
    probability: float,
    *,
    uncertainty: float = 0.10,
    ticker: str = TICKER,
    market_probability: float = 0.50,
) -> Forecast:
    return Forecast(
        market_ticker=ticker,
        probability_yes=probability,
        uncertainty=uncertainty,
        sources_used={"unit": 1.0},
        market_implied_yes=market_probability,
        edge_yes=probability - market_probability,
        rationale="tier regression",
    )


@pytest.mark.parametrize(
    ("probability", "expected_tier", "expected_after_fee_edge"),
    (
        (0.560, "A", 0.040),
        (0.540, "B", 0.020),
        (0.530, "C", 0.010),
        (0.529, None, 0.009),
    ),
)
def test_tiers_use_executable_ask_and_taker_fee_thresholds(
    probability: float,
    expected_tier: str | None,
    expected_after_fee_edge: float,
) -> None:
    assessment = assess_market_tier(
        _market(no_ask=99),
        _forecast(probability),
        now=ASSESS_AT,
    )

    assert assessment.tier == expected_tier
    assert assessment.side == "yes"
    assert assessment.entry_price_cents == 50
    assert assessment.modeled_fee_cents == 2
    assert assessment.gross_executable_edge == pytest.approx(probability - 0.50)
    assert assessment.after_fee_edge == pytest.approx(expected_after_fee_edge)


@pytest.mark.parametrize(
    ("yes_ask", "no_ask"),
    (
        (None, None),
        (0, 100),
        (50.5, "bad"),
        (float("nan"), None),
    ),
)
def test_missing_or_invalid_asks_fail_closed_to_watch(
    yes_ask: object,
    no_ask: object,
) -> None:
    assessment = assess_market_tier(
        _market(yes_ask=yes_ask, no_ask=no_ask),
        _forecast(0.90),
        now=ASSESS_AT,
    )

    assert assessment.tier is None
    assert assessment.side is None
    assert assessment.entry_price_cents is None
    assert assessment.after_fee_edge is None
    assert assessment.reason == "no_executable_depth"


@pytest.mark.parametrize(
    "market",
    (
        _market(liquidity=0),
        _market(liquidity=None),
        _market(yes_bid=None, no_bid=None),
    ),
)
def test_zero_unknown_or_one_sided_depth_cannot_receive_a_letter(
    market: SimpleNamespace,
) -> None:
    assessment = assess_market_tier(
        market,
        _forecast(0.90),
        now=ASSESS_AT,
    )

    assert assessment.tier is None
    assert assessment.reason == "no_executable_depth"


def test_current_kalshi_quote_sizes_supply_depth_when_legacy_liquidity_is_zero(
) -> None:
    assessment = assess_market_tier(
        _market(
            no_ask=99,
            liquidity=0,
            raw={
                "yes_bid_size_fp": "145999.74",
                "yes_ask_size_fp": "471822.17",
            },
        ),
        _forecast(0.56),
        now=ASSESS_AT,
    )

    assert TIER_POLICY_VERSION == "executable_value_v5"
    assert TIER_POLICY_SPEC["snapshot_schema_version"] == 4
    assert assessment.tier == "A"
    assert assessment.side == "yes"
    assert assessment.liquidity == 0
    assert assessment.selected_bid_size_fp == pytest.approx(145999.74)
    assert assessment.selected_ask_size_fp == pytest.approx(471822.17)
    assert assessment.effective_depth == pytest.approx(145999.74)
    assert assessment.depth_source == "quote_sizes_fp"
    assert tier_snapshot_is_valid(assessment.feature_fields(), ticker=TICKER)


def test_no_side_depth_is_bound_to_the_inverse_yes_queues() -> None:
    assessment = assess_market_tier(
        _market(
            liquidity=0,
            raw={
                "yes_bid_size_fp": "11.25",
                "yes_ask_size_fp": "23.50",
            },
        ),
        _forecast(0.44),
        now=ASSESS_AT,
    )

    assert assessment.tier == "A"
    assert assessment.side == "no"
    assert assessment.selected_bid_size_fp == pytest.approx(23.50)
    assert assessment.selected_ask_size_fp == pytest.approx(11.25)
    assert assessment.effective_depth == pytest.approx(11.25)
    assert assessment.depth_source == "quote_sizes_fp"


@pytest.mark.parametrize(
    "raw",
    (
        {"yes_bid_size_fp": "10.0"},
        {"yes_bid_size_fp": "10.0", "yes_ask_size_fp": "0"},
        {"yes_bid_size_fp": "nan", "yes_ask_size_fp": "10.0"},
        {"yes_bid_size_fp": "10.0", "yes_ask_size_fp": "inf"},
        {
            "yes_bid_size_fp": "10.0",
            "no_ask_size_fp": "11.0",
            "yes_ask_size_fp": "10.0",
        },
    ),
)
def test_quote_size_depth_requires_two_positive_consistent_queues(
    raw: dict[str, object],
) -> None:
    assessment = assess_market_tier(
        _market(liquidity=0, raw=raw),
        _forecast(0.90),
        now=ASSESS_AT,
    )

    assert assessment.tier is None
    assert assessment.reason == "no_executable_depth"


def test_self_hashed_quote_size_tampering_fails_semantic_replay_validation() -> None:
    assessment = assess_market_tier(
        _market(
            no_ask=99,
            liquidity=0,
            raw={"yes_bid_size_fp": "10.0", "yes_ask_size_fp": "20.0"},
        ),
        _forecast(0.56),
        now=ASSESS_AT,
    )
    forged = replace(assessment, selected_bid_size_fp=11.0).feature_fields()

    # ``feature_fields`` recomputes the digest; semantic validation still
    # rejects a selected size that no longer reproduces effective depth.
    assert tier_snapshot_is_valid(forged, ticker=TICKER) is False


def test_no_quote_can_be_the_value_side() -> None:
    assessment = assess_market_tier(
        _market(yes_ask=50, no_ask=50),
        _forecast(0.44),
        now=ASSESS_AT,
    )

    assert assessment.tier == "A"
    assert assessment.side == "no"
    assert assessment.gross_executable_edge == pytest.approx(0.06)
    assert assessment.after_fee_edge == pytest.approx(0.04)


@pytest.mark.parametrize(
    ("uncertainty", "expected_tier"),
    (
        (0.1200, "A"),
        (0.1201, "B"),
        (0.1801, "C"),
        (0.2501, None),
    ),
)
def test_uncertainty_gates_downgrade_instead_of_overstating_quality(
    uncertainty: float,
    expected_tier: str | None,
) -> None:
    assessment = assess_market_tier(
        _market(no_ask=99),
        _forecast(0.56, uncertainty=uncertainty),
        now=ASSESS_AT,
    )

    assert assessment.tier == expected_tier
    if expected_tier is None:
        assert assessment.reason == "uncertainty_above_tier_gate"


def test_a_scarcity_is_deterministic_per_event_and_scope() -> None:
    same_event = [
        (
            _market("KXMLBGAME-26JUL18NYYBOS-NYY", no_ask=99),
            _forecast(0.64, ticker="KXMLBGAME-26JUL18NYYBOS-NYY"),
        ),
        (
            _market("KXMLBTOTAL-26JUL18NYYBOS-T9", no_ask=99),
            _forecast(0.61, ticker="KXMLBTOTAL-26JUL18NYYBOS-T9"),
        ),
    ]
    forward = assign_cycle_tiers(same_event, now=ASSESS_AT)
    reverse = assign_cycle_tiers(reversed(same_event), now=ASSESS_AT)

    assert forward["KXMLBGAME-26JUL18NYYBOS-NYY"].tier == "A"
    demoted = forward["KXMLBTOTAL-26JUL18NYYBOS-T9"]
    assert demoted.tier == "B"
    assert demoted.base_tier == "A"
    assert demoted.scarcity_demoted is True
    assert {
        ticker: (row.tier, row.scarcity_demoted)
        for ticker, row in forward.items()
    } == {
        ticker: (row.tier, row.scarcity_demoted)
        for ticker, row in reverse.items()
    }

    distinct_events = []
    for index in range(6):
        ticker = f"KXMLBGAME-26JUL{10 + index:02d}AAABBB-AAA"
        distinct_events.append(
            (_market(ticker, no_ask=99), _forecast(0.61 + index / 100, ticker=ticker))
        )
    scoped = assign_cycle_tiers(distinct_events, now=ASSESS_AT)
    scoped_reversed = assign_cycle_tiers(reversed(distinct_events), now=ASSESS_AT)

    assert sum(row.tier == "A" for row in scoped.values()) == 5
    weakest = "KXMLBGAME-26JUL10AAABBB-AAA"
    assert scoped[weakest].tier == "B"
    assert scoped[weakest].scarcity_demoted is True
    assert {
        ticker: row.tier for ticker, row in scoped.items()
    } == {
        ticker: row.tier for ticker, row in scoped_reversed.items()
    }


def test_fused_signal_persists_the_complete_frozen_tier_snapshot(tmp_path) -> None:
    market = _market(no_ask=99)
    forecast = _forecast(0.56)
    assessment = assess_market_tier(market, forecast, now=ASSESS_AT)
    signal = build_fused_signal(TICKER, forecast, assessment)

    assert signal.features["tier_policy_version"] == TIER_POLICY_VERSION
    assert signal.features["tier"] == "A"
    assert signal.features["tier_side"] == "yes"
    assert signal.features["tier_entry_price_cents"] == 50
    assert signal.features["tier_modeled_fee_cents"] == 2
    assert signal.features["tier_after_fee_edge"] == pytest.approx(0.04)
    assert signal.features["tier_depth_source"] == "legacy_liquidity"
    assert signal.features["tier_effective_depth"] == pytest.approx(500.0)
    assert signal.features["tier_selected_bid_size_fp"] is None
    assert signal.features["tier_selected_ask_size_fp"] is None
    assert signal.features["tier_ticker"] == TICKER
    assert signal.features["tier_uncertainty"] == pytest.approx(0.10)
    assert tier_snapshot_is_valid(signal.features) is True
    assert tier_snapshot_is_valid(signal.features, ticker=TICKER) is True
    assert tier_snapshot_is_valid(signal.features, ticker="KXOTHER") is False

    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        assert ledger.record_signal(signal) is True
        stored = ledger._conn.execute(
            "SELECT features FROM signals WHERE market_ticker=?",
            (TICKER,),
        ).fetchone()[0]
        import json

        assert json.loads(stored) == signal.features
    finally:
        ledger.close()


def test_self_hashed_but_semantically_false_a_tier_is_rejected() -> None:
    assessment = assess_market_tier(
        _market(no_ask=99), _forecast(0.56), now=ASSESS_AT
    )
    forged = replace(
        assessment,
        tier="A",
        base_tier="A",
        gross_executable_edge=-0.48,
        after_fee_edge=-0.50,
        uncertainty=0.50,
        market_status="closed",
        reason="meets_a_edge_and_uncertainty",
    ).feature_fields()

    # feature_fields recomputes a perfectly matching digest; semantic
    # validation must still reject the impossible claim.
    assert tier_snapshot_is_valid(forged, ticker=TICKER) is False


@pytest.mark.parametrize(
    ("close_time", "status", "expected_reason"),
    (
        (None, "open", "missing_close_time"),
        (_DEFAULT, "", "missing_market_status"),
    ),
)
def test_missing_close_or_affirmative_open_status_cannot_receive_a_tier(
    close_time: object,
    status: object,
    expected_reason: str,
) -> None:
    assessment = assess_market_tier(
        _market(no_ask=99, close_time=close_time, status=status),
        _forecast(0.90),
        now=ASSESS_AT,
    )

    assert assessment.tier is None
    assert assessment.reason == expected_reason
    assert tier_snapshot_is_valid(assessment.feature_fields(), ticker=TICKER) is False


def test_decision_tier_attribution_is_immutable(tmp_path) -> None:
    assessment = assess_market_tier(
        _market(no_ask=99), _forecast(0.56), now=ASSESS_AT
    )
    decision = Decision(
        decision_id="tier-decision-1",
        market_ticker=TICKER,
        action=DecisionAction.BUY_YES,
        side="yes",
        price_cents=50,
        count=1,
        ev_cents_per_contract=4.0,
        kelly_fraction=0.01,
        notional_cents=50,
        forecast=_forecast(0.56),
        risk_snapshot={},
        created_at="2026-07-22T10:00:00+00:00",
        tier_label=assessment.tier,
        tier_policy_version=assessment.policy_version,
        tier_score=assessment.score,
        tier_reason=assessment.reason,
        tier_snapshot=assessment.feature_fields(),
    )
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        ledger.record_decision(decision)
        ledger.record_decision(decision)  # idempotent replay is permitted

        with pytest.raises(ValueError, match="tier attribution"):
            ledger.record_decision(replace(decision, tier_label="B"))
        with pytest.raises(ValueError, match="tier attribution"):
            ledger.record_decision(
                replace(decision, tier_snapshot={**decision.tier_snapshot, "tampered": True})
            )

        attribution = ledger._conn.execute(
            "SELECT policy_version,tier_label,tier_score,snapshot_json "
            "FROM decision_tier_attribution WHERE decision_id=?",
            (decision.decision_id,),
        ).fetchone()
        assert attribution[:3] == (
            TIER_POLICY_VERSION,
            "A",
            pytest.approx(0.04),
        )
        assert '"tampered"' not in attribution[3]
        assert ledger._conn.execute(
            "SELECT tier_label FROM decisions WHERE decision_id=?",
            (decision.decision_id,),
        ).fetchone()[0] == "A"
    finally:
        ledger.close()


@pytest.mark.parametrize(
    ("fetched_at", "expected_reason"),
    (
        (None, "missing_quote_timestamp"),
        (
            (ASSESS_AT - timedelta(seconds=901)).isoformat(),
            "stale_quote",
        ),
        (
            (ASSESS_AT + timedelta(seconds=6)).isoformat(),
            "future_quote_timestamp",
        ),
    ),
)
def test_missing_stale_and_future_quotes_cannot_receive_a_letter_tier(
    fetched_at: object,
    expected_reason: str,
) -> None:
    assessment = assess_market_tier(
        _market(no_ask=99, fetched_at=fetched_at),
        _forecast(0.90),
        now=ASSESS_AT,
    )

    assert assessment.tier is None
    assert assessment.side is None
    assert assessment.after_fee_edge is None
    assert assessment.reason == expected_reason


@pytest.mark.parametrize(
    ("hours_to_close", "expected_horizon"),
    ((1.0, "hourly"), (24.0, "daily"), (7 * 24.0, "weekly")),
)
def test_ordinary_crypto_tickers_derive_horizon_from_quote_to_close(
    hours_to_close: float,
    expected_horizon: str,
) -> None:
    fetched_at = ASSESS_AT - timedelta(seconds=30)
    assessment = assess_market_tier(
        _market(
            "KXBTC-26JUL22-B100000",
            no_ask=99,
            fetched_at=fetched_at.isoformat(),
            close_time=(fetched_at + timedelta(hours=hours_to_close)).isoformat(),
        ),
        _forecast(0.56, ticker="KXBTC-26JUL22-B100000"),
        now=ASSESS_AT,
    )

    assert assessment.horizon_phase == expected_horizon
    assert assessment.tier == "A"


def test_decision_tier_attribution_cannot_be_removed_or_added_later(
    tmp_path,
) -> None:
    assessment = assess_market_tier(
        _market(no_ask=99), _forecast(0.56), now=ASSESS_AT
    )
    attributed = Decision(
        decision_id="tier-removal",
        market_ticker=TICKER,
        action=DecisionAction.BUY_YES,
        side="yes",
        price_cents=50,
        count=1,
        ev_cents_per_contract=4.0,
        kelly_fraction=0.01,
        notional_cents=50,
        forecast=_forecast(0.56),
        risk_snapshot={},
        created_at="2026-07-22T12:00:00+00:00",
        tier_label=assessment.tier,
        tier_policy_version=assessment.policy_version,
        tier_score=assessment.score,
        tier_reason=assessment.reason,
        tier_snapshot=assessment.feature_fields(),
    )
    unattributed = replace(
        attributed,
        decision_id="tier-retroactive",
        tier_label=None,
        tier_policy_version=None,
        tier_score=None,
        tier_reason=None,
        tier_snapshot={},
    )
    ledger = AutonomyLedger(tmp_path / "immutability.db")
    try:
        ledger.record_decision(attributed)
        with pytest.raises(ValueError, match="cannot be removed"):
            ledger.record_decision(
                replace(
                    attributed,
                    tier_label=None,
                    tier_policy_version=None,
                    tier_score=None,
                    tier_reason=None,
                    tier_snapshot={},
                )
            )

        ledger.record_decision(unattributed)
        with pytest.raises(ValueError, match="cannot be added retroactively"):
            ledger.record_decision(
                replace(
                    unattributed,
                    tier_label=assessment.tier,
                    tier_policy_version=assessment.policy_version,
                    tier_score=assessment.score,
                    tier_reason=assessment.reason,
                    tier_snapshot=assessment.feature_fields(),
                )
            )
    finally:
        ledger.close()


def test_actionable_decision_opposite_the_tier_value_side_is_unattributed(
    tmp_path,
    monkeypatch,
) -> None:
    import asyncio
    from datetime import datetime, timedelta, timezone

    from autonomy.allocator import Allocator
    from autonomy.brain import PredatorBrain
    from autonomy.executor import Executor
    from autonomy.learner import Learner
    from autonomy.ontology import SessionMode
    from autonomy.reconciler import Reconciler
    from autonomy.risk_brain import RiskBrain
    from autonomy.scanner import MarketScanner
    from autonomy.signals.base import SourceRegistry
    from autonomy.signals.crypto_spot import CryptoSpotVolSignal
    from autonomy.signals.market_prior import MarketPriorSignal
    from autonomy.switches import Switches
    from autonomy.tier_policy import TierAssessment

    ticker = "KXBTCD-26JUL22-T100000.00"
    monkeypatch.delenv("DUMMY_MAIN_ENABLED", raising=False)
    monkeypatch.delenv("DUMMY_CRYPTO_ENABLED", raising=False)
    monkeypatch.setattr(
        Switches,
        "load",
        classmethod(lambda cls, path=None: cls({"main": True, "crypto": True})),
    )
    monkeypatch.setattr(
        "autonomy.no_edge_map.load_negative_scopes", lambda *args, **kwargs: frozenset()
    )

    def fixed_tiers(scored, **_kwargs):
        return {
            market.ticker: TierAssessment(
                ticker=market.ticker,
                tier="A",
                base_tier="A",
                side="yes",
                entry_price_cents=40,
                modeled_fee_cents=2,
                gross_executable_edge=0.10,
                after_fee_edge=0.08,
                uncertainty=forecast.uncertainty,
                scope="BTC",
                horizon_phase="hourly",
                assessed_at=datetime.now(timezone.utc).isoformat(),
                quote_fetched_at=market.fetched_at,
                event_key=market.ticker,
                reason="fixture_yes_value",
            )
            for market, forecast in scored
        }

    def force_opposite_side(
        _self,
        market,
        forecast,
        *_args,
        **_kwargs,
    ):
        return Decision(
            decision_id="opposite-side",
            market_ticker=market.ticker,
            action=DecisionAction.BUY_NO,
            side="no",
            price_cents=60,
            count=1,
            ev_cents_per_contract=5.0,
            kelly_fraction=0.01,
            notional_cents=60,
            forecast=forecast,
            risk_snapshot={},
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    monkeypatch.setattr("autonomy.tier_policy.assign_cycle_tiers", fixed_tiers)
    monkeypatch.setattr(
        "autonomy.tier_policy.tier_snapshot_is_valid",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(Allocator, "decide", force_opposite_side)

    registry = SourceRegistry()
    registry.register(MarketPriorSignal())
    registry.register(
        CryptoSpotVolSignal(fetch_spot_and_vol=lambda _asset: (100_000.0, 0.5))
    )

    def fetch_series(series):
        if series != "KXBTCD":
            return {"markets": []}
        return {"markets": [{
            "ticker": ticker,
            "title": "BTC above $100k",
            "status": "active",
            "close_time": (
                datetime.now(timezone.utc) + timedelta(hours=2)
            ).isoformat(),
            "yes_bid": 30,
            "yes_ask": 40,
            "no_bid": 60,
            "no_ask": 70,
            "volume": 500,
            "liquidity": 1_000,
            "strike_type": "greater",
            "floor_strike": 100_000.0,
        }]}

    ledger = AutonomyLedger(tmp_path / "side-binding.db")
    brain = PredatorBrain(
        mode=SessionMode.SHADOW,
        ledger=ledger,
        registry=registry,
        scanner=MarketScanner(fetch_series=fetch_series, watchlist=["KXBTCD"]),
        risk_brain=RiskBrain(tmp_path / "risk.json"),
        executor=Executor(
            SessionMode.SHADOW,
            session_path=tmp_path / "session.json",
            kill_path=tmp_path / "KILL",
        ),
        reconciler=Reconciler(ledger, fetch_market_result=lambda _ticker: {}),
        learner=Learner(ledger),
        board_path=tmp_path / "bet_board.json",
    )
    try:
        report = asyncio.run(brain.run_cycle())
        stored = ledger._conn.execute(
            "SELECT side,tier_label,tier_policy_version,tier_reason "
            "FROM decisions WHERE decision_id='opposite-side'"
        ).fetchone()
        attribution_count = ledger._conn.execute(
            "SELECT COUNT(*) FROM decision_tier_attribution"
        ).fetchone()[0]

        assert report.decisions_made == 1
        assert stored == (
            "no",
            None,
            None,
            "unattributed_decision_side_mismatch",
        )
        assert attribution_count == 0
    finally:
        ledger.close()


def test_scoreless_tier_assessment_survives_the_decide_loop(
    tmp_path,
    monkeypatch,
) -> None:
    """Regression: tier_assessment.score=None crashed run_cycle with
    ``TypeError: float() argument ... not 'NoneType'`` at the tier_score
    attribution. A scoreless assessment must persist tier_score=None."""
    import asyncio

    from autonomy.brain import PredatorBrain
    from autonomy.executor import Executor
    from autonomy.learner import Learner
    from autonomy.ontology import SessionMode
    from autonomy.reconciler import Reconciler
    from autonomy.risk_brain import RiskBrain
    from autonomy.scanner import MarketScanner
    from autonomy.signals.base import SourceRegistry
    from autonomy.signals.crypto_spot import CryptoSpotVolSignal
    from autonomy.signals.market_prior import MarketPriorSignal
    from autonomy.switches import Switches
    from autonomy.tier_policy import TierAssessment
    from autonomy.allocator import Allocator

    ticker = "KXBTCD-26JUL22-T100000.00"
    monkeypatch.delenv("DUMMY_MAIN_ENABLED", raising=False)
    monkeypatch.delenv("DUMMY_CRYPTO_ENABLED", raising=False)
    monkeypatch.setattr(
        Switches,
        "load",
        classmethod(lambda cls, path=None: cls({"main": True, "crypto": True})),
    )
    monkeypatch.setattr(
        "autonomy.no_edge_map.load_negative_scopes", lambda *args, **kwargs: frozenset()
    )

    def scoreless_tiers(scored, **_kwargs):
        return {
            market.ticker: TierAssessment(
                ticker=market.ticker,
                tier="A",
                base_tier="A",
                side="yes",
                entry_price_cents=40,
                modeled_fee_cents=2,
                gross_executable_edge=forecast.probability_yes - 0.40,
                after_fee_edge=None,  # score property -> None (the crash input)
                uncertainty=forecast.uncertainty,
                scope="BTC",
                horizon_phase="hourly",
                assessed_at=datetime.now(timezone.utc).isoformat(),
                quote_fetched_at=market.fetched_at,
                event_key=market.ticker,
                reason="fixture_scoreless",
            )
            for market, forecast in scored
        }

    def force_yes_side(_self, market, forecast, *_args, **_kwargs):
        return Decision(
            decision_id="scoreless-tier",
            market_ticker=market.ticker,
            action=DecisionAction.BUY_YES,
            side="yes",
            price_cents=40,
            count=1,
            ev_cents_per_contract=5.0,
            kelly_fraction=0.01,
            notional_cents=40,
            forecast=forecast,
            risk_snapshot={},
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    monkeypatch.setattr("autonomy.tier_policy.assign_cycle_tiers", scoreless_tiers)
    monkeypatch.setattr(
        "autonomy.tier_policy.tier_snapshot_is_valid",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(Allocator, "decide", force_yes_side)

    registry = SourceRegistry()
    registry.register(MarketPriorSignal())
    registry.register(
        CryptoSpotVolSignal(fetch_spot_and_vol=lambda _asset: (100_000.0, 0.5))
    )

    def fetch_series(series):
        if series != "KXBTCD":
            return {"markets": []}
        return {"markets": [{
            "ticker": ticker,
            "title": "BTC above $100k",
            "status": "active",
            "close_time": (
                datetime.now(timezone.utc) + timedelta(hours=2)
            ).isoformat(),
            "yes_bid": 30,
            "yes_ask": 40,
            "no_bid": 60,
            "no_ask": 70,
            "volume": 500,
            "liquidity": 1_000,
            "strike_type": "greater",
            "floor_strike": 100_000.0,
        }]}

    ledger = AutonomyLedger(tmp_path / "scoreless-tier.db")
    brain = PredatorBrain(
        mode=SessionMode.SHADOW,
        ledger=ledger,
        registry=registry,
        scanner=MarketScanner(fetch_series=fetch_series, watchlist=["KXBTCD"]),
        risk_brain=RiskBrain(tmp_path / "risk.json"),
        executor=Executor(
            SessionMode.SHADOW,
            session_path=tmp_path / "session.json",
            kill_path=tmp_path / "KILL",
        ),
        reconciler=Reconciler(ledger, fetch_market_result=lambda _ticker: {}),
        learner=Learner(ledger),
        board_path=tmp_path / "bet_board.json",
    )
    try:
        report = asyncio.run(brain.run_cycle())
        assert report.status == "CYCLE_OK"
        stored = ledger._conn.execute(
            "SELECT tier_label,tier_score,tier_reason "
            "FROM decisions WHERE decision_id='scoreless-tier'"
        ).fetchone()
        assert report.decisions_made == 1
        assert stored == ("A", None, "fixture_scoreless")
    finally:
        ledger.close()
