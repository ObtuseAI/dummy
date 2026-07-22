"""Adversarial PIT and authority tests for the market-debias challenger."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from autonomy.ledger import AutonomyLedger
from autonomy.ontology import (
    Decision,
    DecisionAction,
    Forecast,
    MarketView,
    Vertical,
)
from autonomy.signals.market_debias import (
    CURVE_SCHEMA_VERSION,
    LIVE_EVIDENCE_MODE,
    DebiasSample,
    MarketDebiasSignal,
    _exact_curve_scope,
    fit_curve,
    ledger_samples,
)
from autonomy.taxonomy import grading_scope


def _insert_prior(
    ledger: AutonomyLedger,
    ticker: str,
    probability: float,
    *,
    observed_at: str,
    received_at: str,
    close_time: str,
    mode: str = "live",
    market_status: str = "active",
) -> None:
    ledger._conn.execute(  # noqa: SLF001 - adversarial evidence fixture
        "INSERT INTO signals(source,market_ticker,probability_yes,uncertainty,"
        "rationale,created_at,mode,features,ingested_at,ingest_version) "
        "VALUES (?,?,?,?,?,?,?,?,?,2)",
        (
            "market_prior",
            ticker,
            probability,
            0.05,
            "fixture",
            observed_at,
            mode,
            json.dumps({"close_time": close_time, "market_status": market_status}),
            received_at,
        ),
    )


def _record_decision(ledger: AutonomyLedger, ticker: str, created_at: str) -> None:
    forecast = Forecast(
        market_ticker=ticker,
        probability_yes=0.5,
        uncertainty=0.1,
        sources_used={"market_prior": 1.0},
        market_implied_yes=0.5,
        edge_yes=0.0,
        rationale="fixture",
    )
    ledger.record_decision(
        Decision(
            decision_id=f"decision-{ticker}",
            market_ticker=ticker,
            action=DecisionAction.ABSTAIN,
            side="yes",
            price_cents=50,
            count=0,
            ev_cents_per_contract=0.0,
            kelly_fraction=0.0,
            notional_cents=0,
            forecast=forecast,
            risk_snapshot={},
            created_at=created_at,
        )
    )


def _settle(ledger: AutonomyLedger, ticker: str, result: int, settled_at: str) -> None:
    ledger._conn.execute(  # noqa: SLF001 - historical timestamp fixture
        "INSERT INTO settlements(market_ticker,result_yes,settled_at) VALUES (?,?,?)",
        (ticker, result, settled_at),
    )
    ledger._conn.commit()  # noqa: SLF001


def test_ledger_samples_excludes_retro_future_late_terminal_and_uses_latest_valid(
    tmp_path,
):
    ledger = AutonomyLedger(tmp_path / "pit.db")
    ticker = "KXBTC-26JUL22-B100000"
    close = "2026-07-22T12:00:00+00:00"
    try:
        _insert_prior(
            ledger,
            ticker,
            0.31,
            observed_at="2026-07-22T08:00:00+00:00",
            received_at="2026-07-22T08:00:01+00:00",
            close_time=close,
        )
        _insert_prior(
            ledger,
            ticker,
            0.33,
            observed_at="2026-07-22T09:00:00+00:00",
            received_at="2026-07-22T09:00:01+00:00",
            close_time=close,
        )
        # All of these have larger ids than the honest row. None may replace it.
        _insert_prior(
            ledger,
            ticker,
            0.99,
            observed_at="2026-07-22T09:30:00+00:00",
            received_at="2026-07-22T09:30:01+00:00",
            close_time=close,
            mode="retro",
        )
        _insert_prior(
            ledger,
            ticker,
            0.98,
            observed_at="2026-07-22T09:45:00+00:00",
            received_at="2026-07-22T10:00:01+00:00",
            close_time=close,
        )
        _insert_prior(
            ledger,
            ticker,
            0.97,
            observed_at="2026-07-22T10:00:01+00:00",
            received_at="2026-07-22T10:00:02+00:00",
            close_time=close,
        )
        _insert_prior(
            ledger,
            ticker,
            0.96,
            observed_at="2026-07-22T09:50:00+00:00",
            received_at="2026-07-22T09:50:01+00:00",
            close_time=close,
            market_status="finalized",
        )
        _insert_prior(
            ledger,
            ticker,
            0.95,
            observed_at=close,
            received_at=close,
            close_time=close,
        )
        _record_decision(ledger, ticker, "2026-07-22T10:00:00+00:00")
        _settle(ledger, ticker, 1, "2026-07-22T12:30:00+00:00")

        samples = ledger_samples(ledger)
        assert len(samples) == 1
        sample = samples[0]
        assert sample.probability_yes == 0.33
        assert sample.observed_at == "2026-07-22T09:00:00+00:00"
        assert sample.received_at == "2026-07-22T09:00:01+00:00"
        assert sample.decision_at == "2026-07-22T10:00:00+00:00"
        assert sample.exact_scope == "CRYPTO|btc|ladder|near_terminal"
    finally:
        ledger.close()


def test_ledger_samples_fails_closed_on_terminal_only_and_malformed_decision(tmp_path):
    ledger = AutonomyLedger(tmp_path / "terminal.db")
    close = "2026-07-22T12:00:00+00:00"
    terminal_ticker = "KXBTC-26JUL22-B100001"
    malformed_ticker = "KXBTC-26JUL22-B100002"
    try:
        _insert_prior(
            ledger,
            terminal_ticker,
            0.995,
            observed_at=close,
            received_at=close,
            close_time=close,
        )
        _settle(ledger, terminal_ticker, 1, "2026-07-22T12:01:00+00:00")
        _insert_prior(
            ledger,
            malformed_ticker,
            0.42,
            observed_at="2026-07-22T09:00:00+00:00",
            received_at="2026-07-22T09:00:01+00:00",
            close_time=close,
        )
        _record_decision(ledger, malformed_ticker, "2026-07-22T10:00:00")
        _settle(ledger, malformed_ticker, 0, "2026-07-22T12:01:00+00:00")
        assert ledger_samples(ledger) == []
    finally:
        ledger.close()


def test_undecided_contract_uses_first_live_receipt_not_hindsight_latest(tmp_path):
    ledger = AutonomyLedger(tmp_path / "undecided.db")
    ticker = "KXBTC-26JUL22-B100003"
    close = "2026-07-22T12:00:00+00:00"
    try:
        _insert_prior(
            ledger,
            ticker,
            0.28,
            observed_at="2026-07-22T08:00:00+00:00",
            received_at="2026-07-22T08:00:01+00:00",
            close_time=close,
        )
        _insert_prior(
            ledger,
            ticker,
            0.94,
            observed_at="2026-07-22T11:59:00+00:00",
            received_at="2026-07-22T11:59:01+00:00",
            close_time=close,
        )
        _settle(ledger, ticker, 1, "2026-07-22T12:01:00+00:00")

        samples = ledger_samples(ledger)

        assert len(samples) == 1
        assert samples[0].probability_yes == 0.28
        assert samples[0].selection_policy == (
            "earliest_live_receipt_for_undecided_contract"
        )
    finally:
        ledger.close()


def test_missing_or_unknown_market_status_is_not_verified_live_evidence(tmp_path):
    ledger = AutonomyLedger(tmp_path / "status.db")
    ticker = "KXBTC-26JUL22-B100004"
    close = "2026-07-22T12:00:00+00:00"
    try:
        _insert_prior(
            ledger,
            ticker,
            0.45,
            observed_at="2026-07-22T08:00:00+00:00",
            received_at="2026-07-22T08:00:01+00:00",
            close_time=close,
            market_status="unknown",
        )
        _settle(ledger, ticker, 0, "2026-07-22T12:01:00+00:00")
        assert ledger_samples(ledger) == []
    finally:
        ledger.close()


def _verified_sample(
    ticker: str,
    *,
    result: int,
    signal_id: int,
    probability: float = 0.45,
    horizon: str = "near_terminal",
) -> DebiasSample:
    observed = datetime(2026, 7, 1, tzinfo=timezone.utc) + timedelta(minutes=signal_id)
    hours = {"near_terminal": 2, "short": 24, "long": 240}[horizon]
    close = observed + timedelta(hours=hours)
    settled = close + timedelta(hours=1)
    scope = _exact_curve_scope(ticker, horizon)
    assert scope is not None
    return DebiasSample(
        probability_yes=probability,
        result_yes=result,
        ticker=ticker,
        horizon=horizon,
        exact_scope=scope,
        observed_at=observed.isoformat(),
        received_at=(observed + timedelta(seconds=1)).isoformat(),
        close_time=close.isoformat(),
        settled_at=settled.isoformat(),
        decision_at=None,
        signal_id=signal_id,
        selection_policy="earliest_live_receipt_for_undecided_contract",
    )


def _scope_samples(asset: str, yes_count: int) -> list[DebiasSample]:
    return [
        _verified_sample(
            f"KX{asset}-26JUL22-B{100000 + index}",
            result=1 if index < yes_count else 0,
            signal_id=index + (0 if asset == "BTC" else 1000),
        )
        for index in range(80)
    ]


def _market(asset: str) -> MarketView:
    return MarketView(
        ticker=f"KX{asset}-26JUL22-B100999",
        title="",
        vertical=Vertical.CRYPTO,
        status="active",
        close_time=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        yes_bid=43,
        yes_ask=47,
        no_bid=53,
        no_ask=57,
        volume=1000,
        liquidity=1000,
    )


class _NoPromotion:
    @staticmethod
    def is_promoted_signal(_source, _ticker, _features):
        return False


class _OnlyScopePromotion:
    def __init__(self, allowed: str):
        self.allowed = allowed

    def is_promoted_signal(self, source, ticker, features):
        return grading_scope(source, ticker, features) == self.allowed


def test_fit_curve_quarantines_legacy_and_spoofed_verified_inputs():
    honest = _scope_samples("BTC", 60)
    spoofed = honest[0].__class__(
        **{**honest[0].__dict__, "exact_scope": "CRYPTO|eth|ladder|near_terminal"}
    )
    curve = fit_curve([(0.45, 1)] * 200 + honest + [spoofed])
    assert curve["schema_version"] == CURVE_SCHEMA_VERSION
    assert curve["evidence_mode"] == LIVE_EVIDENCE_MODE
    assert curve["verified_live_n"] == 80
    assert curve["unverified_research_n"] == 200
    assert curve["invalid_verified_n"] == 1
    assert curve["prediction_authority"] is False
    assert curve["automatic_promotion"] is False


def test_fit_curve_rejects_spoofed_canonical_selection_policy():
    honest = _scope_samples("BTC", 60)
    spoofed = honest[0].__class__(
        **{
            **honest[0].__dict__,
            "selection_policy": "latest_receipt_at_or_before_earliest_decision",
        }
    )

    curve = fit_curve(honest[1:] + [spoofed])

    assert curve["verified_live_n"] == 79
    assert curve["invalid_verified_n"] == 1


def test_exact_scope_curve_never_falls_back_across_asset_or_data_only_target():
    curve = fit_curve(_scope_samples("BTC", 60))
    source = MarketDebiasSignal(curve=curve, promotion=_NoPromotion())
    btc = source.generate(_market("BTC"))
    assert btc is not None and btc.probability_yes == 0.75
    assert source.generate(_market("ETH")) is None

    weather = MarketView(
        ticker="KXHIGHNY-26JUL22-B90",
        title="",
        vertical=Vertical.WEATHER,
        status="active",
        close_time=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        yes_bid=43,
        yes_ask=47,
        no_bid=53,
        no_ask=57,
        volume=1000,
        liquidity=1000,
    )
    assert source.generate(weather) is None


def test_market_debias_is_report_only_until_explicit_exact_scope_promotion():
    curve = fit_curve(_scope_samples("BTC", 60) + _scope_samples("ETH", 20))
    btc_market = _market("BTC")
    base = MarketDebiasSignal(curve=curve, promotion=_NoPromotion()).generate(
        btc_market
    )
    assert base is not None
    assert base.features["challenger_only"] is True
    assert base.features["promotion_eligible"] is False
    assert base.features["report_only"] is True
    assert base.features["prediction_authority"] is False
    allowed = grading_scope(base.source, base.market_ticker, base.features)

    promotion = _OnlyScopePromotion(allowed)
    promoted = MarketDebiasSignal(curve=curve, promotion=promotion).generate(btc_market)
    assert promoted is not None
    assert promoted.features["challenger_only"] is True
    assert promoted.features["report_only"] is False
    assert promoted.features["prediction_authority"] is True
    assert promoted.features["promoted_exact_scope"] is True

    eth = MarketDebiasSignal(curve=curve, promotion=promotion).generate(_market("ETH"))
    assert eth is not None
    assert eth.features["report_only"] is True
    assert eth.features["prediction_authority"] is False


def test_real_registry_requires_the_exact_emitted_scope(tmp_path):
    from autonomy.promotion import PromotionRegistry

    curve = fit_curve(_scope_samples("BTC", 60) + _scope_samples("ETH", 20))
    market = _market("BTC")
    unpromoted = MarketDebiasSignal(curve=curve, promotion=_NoPromotion()).generate(
        market
    )
    assert unpromoted is not None
    scope = grading_scope(
        unpromoted.source,
        unpromoted.market_ticker,
        unpromoted.features,
    )
    source, subject, market_type, horizon = scope.split("|", 3)
    promotions = tmp_path / "promotions.json"
    demotions = tmp_path / "demotions.json"
    promotions.write_text(
        json.dumps(
            {
                "promotions": [
                    {
                        "source": source,
                        "subject": subject,
                        "market_type": market_type,
                        "horizon": horizon,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    demotions.write_text(json.dumps({"demotions": []}), encoding="utf-8")
    registry = PromotionRegistry(promotions, demotions)

    promoted = MarketDebiasSignal(curve=curve, promotion=registry).generate(market)
    other_asset = MarketDebiasSignal(curve=curve, promotion=registry).generate(
        _market("ETH")
    )

    assert promoted is not None
    assert promoted.features["prediction_authority"] is True
    assert promoted.features["report_only"] is False
    assert other_asset is not None
    assert other_asset.features["prediction_authority"] is False
    assert other_asset.features["report_only"] is True
