"""Wave-6 lean-in: per-vertical debias curves + honest-quote gate on emission."""
from __future__ import annotations

from datetime import datetime, timezone

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.market_debias import (
    MIN_VERTICAL_BUCKET_N,
    MarketDebiasSignal,
    fit_curve,
    write_curve,
)

NOW = datetime(2026, 7, 17, tzinfo=timezone.utc)
_MLB = "KXMLBGAME-26JUL17NYYBOS-NYY"
_BTC = "KXBTC-26JUL17-B64000"


def _market(ticker, vertical, bid=43, ask=47):
    return MarketView(ticker=ticker, title="", vertical=vertical, status="active",
                      close_time=NOW.isoformat(), yes_bid=bid, yes_ask=ask,
                      no_bid=(100 - ask) if ask else None, no_ask=(100 - bid) if bid else None,
                      volume=500, liquidity=500)


def _mixed_samples():
    """Same 0.45 price level, radically different truths by vertical:
    sports 0.45-priced markets resolve YES 70%; crypto ones resolve 30%."""
    samples = []
    for i in range(200):
        samples.append((0.45, 1 if i < 140 else 0, _MLB))       # sports: 70% YES
    for i in range(2000):
        samples.append((0.45, 1 if i < 600 else 0, _BTC))       # crypto: 30% YES
    return samples


def test_fit_curve_partitions_by_vertical():
    curve = fit_curve(_mixed_samples())
    assert curve["schema_version"] == 2
    verticals = curve["verticals"]
    assert "SPORTS" in verticals and "CRYPTO" in verticals
    sports_bucket = verticals["SPORTS"]["buckets"][4]   # [0.40, 0.50)
    crypto_bucket = verticals["CRYPTO"]["buckets"][4]
    assert sports_bucket["yes_rate"] == 0.7
    assert crypto_bucket["yes_rate"] == 0.3
    # Global (pooled) curve is crypto-dominated -- the dilution the split fixes.
    pooled = curve["buckets"][9]                         # [0.45, 0.50) at 20 buckets
    assert pooled["yes_rate"] is not None and pooled["yes_rate"] < 0.45


def test_fit_curve_accepts_legacy_two_tuples():
    curve = fit_curve([(0.32, 1), (0.32, 0)] * 60)
    assert curve["n_total"] == 120
    assert curve["verticals"] == {}                      # no tickers -> global only


def test_signal_prefers_vertical_curve_and_discloses_scope(tmp_path):
    path = write_curve(fit_curve(_mixed_samples()), tmp_path / "c.json")
    source = MarketDebiasSignal(curve_path=path)
    sports = source.generate(_market(_MLB, Vertical.SPORTS))
    crypto = source.generate(_market(_BTC, Vertical.CRYPTO))
    assert sports is not None and crypto is not None
    assert sports.probability_yes == 0.7 and sports.features["curve_scope"] == "SPORTS"
    assert crypto.probability_yes == 0.3 and crypto.features["curve_scope"] == "CRYPTO"


def test_signal_falls_back_to_global_when_vertical_thin(tmp_path):
    samples = _mixed_samples()
    # A weather market: no WEATHER vertical samples at all -> global fallback.
    path = write_curve(fit_curve(samples), tmp_path / "c.json")
    source = MarketDebiasSignal(curve_path=path)
    weather = source.generate(_market("KXHIGHNY-26JUL17-B90", Vertical.WEATHER))
    assert weather is not None
    assert weather.features["curve_scope"] == "global"


def test_vertical_bucket_below_floor_falls_back(tmp_path):
    # Sports has samples, but fewer than the vertical floor at this level.
    samples = [(0.45, 1, _MLB)] * (MIN_VERTICAL_BUCKET_N - 1)
    samples += [(0.45, 1 if i < 60 else 0, _BTC) for i in range(200)]
    path = write_curve(fit_curve(samples), tmp_path / "c.json")
    source = MarketDebiasSignal(curve_path=path)
    sports = source.generate(_market(_MLB, Vertical.SPORTS))
    assert sports is not None
    assert sports.features["curve_scope"] == "global"    # thin vertical -> pooled


def test_emission_gated_on_honest_quote(tmp_path):
    path = write_curve(fit_curve(_mixed_samples()), tmp_path / "c.json")
    source = MarketDebiasSignal(curve_path=path)
    dead = _market(_BTC, Vertical.CRYPTO, bid=1, ask=99)     # phantom 50c mid
    assert source.applicable(dead) is False
    assert source.generate(dead) is None


def test_ledger_samples_carries_ticker(tmp_path):
    from autonomy.ledger import AutonomyLedger
    from autonomy.ontology import Signal
    from autonomy.signals.market_debias import ledger_samples

    ledger = AutonomyLedger(tmp_path / "l.db")
    try:
        ledger.record_signal(Signal(source="market_prior", market_ticker=_BTC,
                                    probability_yes=0.45, uncertainty=0.1, rationale=""))
        ledger.record_settlement(_BTC, True)
        samples = ledger_samples(ledger)
        assert samples == [(0.45, 1, _BTC)]
    finally:
        ledger.close()
