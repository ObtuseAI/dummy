"""Wave-6 lean-in: per-vertical debias curves + honest-quote gate on emission."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.market_debias import (
    CURVE_SCHEMA_VERSION,
    MIN_VERTICAL_BUCKET_N,
    DebiasSample,
    MarketDebiasSignal,
    _exact_curve_scope,
    fit_curve,
    write_curve,
)

NOW = datetime(2026, 7, 17, tzinfo=timezone.utc)
_MLB = "KXMLBGAME-26JUL17NYYBOS-NYY"
_BTC = "KXBTC-26JUL17-B64000"


def _market(ticker, vertical, bid=43, ask=47, close_time=None):
    return MarketView(
        ticker=ticker,
        title="",
        vertical=vertical,
        status="active",
        close_time=close_time
        or (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        yes_bid=bid,
        yes_ask=ask,
        no_bid=(100 - ask) if ask else None,
        no_ask=(100 - bid) if bid else None,
        volume=500,
        liquidity=500,
    )


def _verified(ticker, index, result, horizon="near_terminal", probability=0.45):
    observed = NOW + timedelta(minutes=index)
    hours = {"near_terminal": 2, "short": 24, "long": 240}[horizon]
    close = observed + timedelta(hours=hours)
    exact_scope = _exact_curve_scope(ticker, horizon)
    assert exact_scope is not None
    return DebiasSample(
        probability_yes=probability,
        result_yes=result,
        ticker=ticker,
        horizon=horizon,
        exact_scope=exact_scope,
        observed_at=observed.isoformat(),
        received_at=(observed + timedelta(seconds=1)).isoformat(),
        close_time=close.isoformat(),
        settled_at=(close + timedelta(hours=1)).isoformat(),
        decision_at=None,
        signal_id=index,
        selection_policy="earliest_live_receipt_for_undecided_contract",
    )


def _mixed_samples():
    """Same 0.45 price level, radically different truths by vertical:
    sports 0.45-priced markets resolve YES 70%; crypto ones resolve 30%."""
    samples = []
    for i in range(100):
        samples.append(_verified(f"{_MLB}{i}", i, 1 if i < 70 else 0))
    for i in range(100):
        samples.append(
            _verified(f"KXBTC-26JUL17-B{64000 + i}", 1000 + i, 1 if i < 30 else 0)
        )
    return samples


def test_fit_curve_partitions_by_vertical():
    curve = fit_curve(_mixed_samples())
    assert curve["schema_version"] == CURVE_SCHEMA_VERSION
    verticals = curve["verticals"]
    assert "SPORTS" in verticals and "CRYPTO" in verticals
    sports_bucket = verticals["SPORTS"]["buckets"][4]  # [0.40, 0.50)
    crypto_bucket = verticals["CRYPTO"]["buckets"][4]
    assert sports_bucket["yes_rate"] == 0.7
    assert crypto_bucket["yes_rate"] == 0.3
    # Aggregate curves remain diagnostics; emission never consumes them.
    pooled = curve["buckets"][9]  # [0.45, 0.50) at 20 buckets
    assert pooled["yes_rate"] == 0.5


def test_fit_curve_quarantines_legacy_two_tuples():
    curve = fit_curve([(0.32, 1), (0.32, 0)] * 60)
    assert curve["n_total"] == 0
    assert curve["unverified_research_n"] == 120
    assert curve["verticals"] == {}
    assert curve["exact_scopes"] == {}


def test_debias_uses_time_to_expiry_bucket():
    ticker = _BTC
    samples = []
    samples += [
        _verified(f"KXBTC-26JUL17-B{64000 + i}", i, 1 if i < 80 else 0)
        for i in range(100)
    ]
    samples += [
        _verified(f"KXBTC-26JUL30-B{74000 + i}", 1000 + i, 1 if i < 20 else 0, "long")
        for i in range(100)
    ]
    source = MarketDebiasSignal(curve=fit_curve(samples))
    now = datetime.now(timezone.utc)
    near = source.generate(
        _market(
            ticker, Vertical.CRYPTO, close_time=(now + timedelta(hours=1)).isoformat()
        )
    )
    long = source.generate(
        _market(
            ticker, Vertical.CRYPTO, close_time=(now + timedelta(days=10)).isoformat()
        )
    )
    assert near is not None and long is not None
    assert near.probability_yes == 0.8
    assert long.probability_yes == 0.2
    assert near.features["curve_scope"].endswith("|near_terminal")
    assert long.features["curve_scope"].endswith("|long")


def test_signal_uses_exact_subject_market_type_horizon_scope(tmp_path):
    path = write_curve(fit_curve(_mixed_samples()), tmp_path / "c.json")
    source = MarketDebiasSignal(curve_path=path)
    sports = source.generate(_market(_MLB, Vertical.SPORTS))
    crypto = source.generate(_market(_BTC, Vertical.CRYPTO))
    assert sports is not None and crypto is not None
    assert sports.probability_yes == 0.7
    assert sports.features["curve_scope"] == "SPORTS|mlb|winner|near_terminal"
    assert crypto.probability_yes == 0.3
    assert crypto.features["curve_scope"] == "CRYPTO|btc|ladder|near_terminal"


def test_signal_never_falls_back_to_global_when_exact_scope_missing(tmp_path):
    samples = _mixed_samples()
    path = write_curve(fit_curve(samples), tmp_path / "c.json")
    source = MarketDebiasSignal(curve_path=path)
    weather = source.generate(_market("KXHIGHNY-26JUL17-B90", Vertical.WEATHER))
    assert weather is None


def test_thin_market_type_scope_abstains_not_borrow_vertical(tmp_path):
    # A sports market type with its OWN (thin) history must ABSTAIN rather than
    # borrow the cross-type sports/global curve -- this is the YRFI fix: YRFI at
    # 0.60 resolves ~coin, but the pooled sports curve at 0.60 is favorite-heavy,
    # so borrowing it over-predicted YRFI by +0.15. Here a thin winner scope
    # coexists with a dense pooled curve, and the signal declines to guess.
    _YRFI = "KXMLBRFI-26JUL17NYYBOS"
    samples = [_verified(f"{_YRFI}{i}", i, 1) for i in range(MIN_VERTICAL_BUCKET_N - 1)]
    samples += _mixed_samples()
    path = write_curve(fit_curve(samples), tmp_path / "c.json")
    source = MarketDebiasSignal(curve_path=path)
    assert source.generate(_market(_YRFI, Vertical.SPORTS)) is None  # abstains


def test_data_only_target_never_emits(tmp_path):
    samples = _mixed_samples()
    path = write_curve(fit_curve(samples), tmp_path / "c.json")
    source = MarketDebiasSignal(curve_path=path)
    weather = source.generate(_market("KXHIGHNY-26JUL17-B90", Vertical.WEATHER))
    assert weather is None


def test_emission_gated_on_honest_quote(tmp_path):
    path = write_curve(fit_curve(_mixed_samples()), tmp_path / "c.json")
    source = MarketDebiasSignal(curve_path=path)
    dead = _market(_BTC, Vertical.CRYPTO, bid=1, ask=99)  # phantom 50c mid
    assert source.applicable(dead) is False
    assert source.generate(dead) is None


def test_ledger_samples_carries_ticker(tmp_path):
    from autonomy.ledger import AutonomyLedger
    from autonomy.ontology import Signal
    from autonomy.signals.market_debias import ledger_samples

    ledger = AutonomyLedger(tmp_path / "l.db")
    try:
        ledger.record_signal(
            Signal(
                source="market_prior",
                market_ticker=_BTC,
                probability_yes=0.45,
                uncertainty=0.1,
                rationale="",
                features={
                    "close_time": (
                        datetime.now(timezone.utc) + timedelta(hours=1)
                    ).isoformat(),
                    "market_status": "active",
                },
            )
        )
        ledger.record_settlement(_BTC, True)
        samples = ledger_samples(ledger)
        assert len(samples) == 1
        assert samples[0].probability_yes == 0.45
        assert samples[0].result_yes == 1
        assert samples[0].ticker == _BTC
        assert samples[0].exact_scope.startswith("CRYPTO|btc|ladder|")
    finally:
        ledger.close()
