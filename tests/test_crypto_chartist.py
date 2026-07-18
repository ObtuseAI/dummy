"""Wave-24: the chartist -- patterns, divergences, ladder, cross-examination."""
from __future__ import annotations

import math

from autonomy.crypto_chartist import (
    Candle,
    TimeframeView,
    aggregate_candles,
    cross_examine,
    detect_divergences,
    detect_patterns,
    rsi_series,
)
from autonomy.ontology import MarketView, Vertical
from autonomy.signals.crypto_chartist import CryptoChartistSignal


def _downtrend(n=30, start=100.0, step=1.0):
    candles = []
    price = start
    for _ in range(n):
        candles.append(Candle(price, price + 0.3, price - step - 0.3,
                              price - step, 10.0))
        price -= step
    return candles


def _uptrend(n=30, start=100.0, step=1.0):
    candles = []
    price = start
    for _ in range(n):
        candles.append(Candle(price, price + step + 0.3, price - 0.3,
                              price + step, 10.0))
        price += step
    return candles


# ------------------------------------------------------------------ patterns


def test_hammer_scores_after_a_downtrend_not_in_an_uptrend():
    down = _downtrend()[:-1]
    last = down[-1].close
    hammer = Candle(last, last + 0.1, last - 3.0, last + 0.4, 10.0)
    hits = {h.name for h in detect_patterns(down + [hammer])}
    assert "hammer" in hits

    up = _uptrend()[:-1]
    last_up = up[-1].close
    hammer_up = Candle(last_up, last_up + 0.1, last_up - 3.0, last_up + 0.4, 10.0)
    up_hits = [h for h in detect_patterns(up + [hammer_up]) if h.name == "hammer"]
    down_hit = next(h for h in detect_patterns(down + [hammer]) if h.name == "hammer")
    assert not up_hits or up_hits[0].strength < down_hit.strength


def test_engulfing_and_star_families():
    down = _downtrend()[:-2]
    last = down[-1].close
    bear = Candle(last, last + 0.2, last - 1.2, last - 1.0, 10.0)
    bull = Candle(last - 1.1, last + 0.6, last - 1.3, last + 0.5, 10.0)
    hits = {h.name: h for h in detect_patterns(down + [bear, bull])}
    assert "bullish_engulfing" in hits and hits["bullish_engulfing"].direction == 1

    down3 = _downtrend()[:-3]
    base = down3[-1].close
    a = Candle(base, base + 0.2, base - 2.2, base - 2.0, 10.0)      # big red
    b = Candle(base - 2.1, base - 1.8, base - 2.5, base - 2.3, 5.0)  # small
    c = Candle(base - 2.2, base + 0.2, base - 2.4, base - 0.4, 12.0)  # strong green past midpoint
    hits3 = {h.name for h in detect_patterns(down3 + [a, b, c])}
    assert "morning_star" in hits3


def test_doji_and_soldiers():
    up = _uptrend()[:-1]
    last = up[-1].close
    doji = Candle(last, last + 1.0, last - 1.0, last + 0.05, 10.0)
    assert any(h.name == "doji" for h in detect_patterns(up + [doji]))

    flat = [Candle(100, 100.6, 99.4, 100.1, 10.0) for _ in range(27)]
    p = 100.0
    soldiers = []
    for _ in range(3):
        soldiers.append(Candle(p, p + 1.1, p - 0.1, p + 1.0, 10.0))
        p += 1.0
    assert any(
        h.name == "three_white_soldiers"
        for h in detect_patterns(flat + soldiers))


# --------------------------------------------------------------- divergences


def _divergence_fixture(low2: float, osc_low1: float, osc_low2: float):
    """Two clean price swing lows with an INJECTED oscillator: the classifier
    is what's under test, so the oscillator relationship is exact."""
    closes = [100.0] * 5
    for _ in range(6):
        closes.append(closes[-1] - 1.0)      # swing low 1 at 94.0
    for _ in range(4):
        closes.append(closes[-1] + 1.0)
    step_down = (closes[-1] - low2) / 6.0
    for _ in range(6):
        closes.append(closes[-1] - step_down)  # swing low 2 at low2
    for _ in range(4):
        closes.append(closes[-1] + 0.8)
    candles = [Candle(c, c + 0.3, c - 0.3, c, 10.0) for c in closes]
    oscillator = [50.0] * len(closes)
    oscillator[10] = osc_low1                 # anchored on the swing bars
    oscillator[20] = osc_low2
    return candles, oscillator


def test_all_four_divergence_classes():
    # price lower low + oscillator higher low  -> regular bullish
    candles, osc = _divergence_fixture(low2=92.0, osc_low1=20.0, osc_low2=35.0)
    kinds = {d.kind for d in detect_divergences(candles, oscillator=osc)}
    assert "regular_bullish" in kinds

    # price higher low + oscillator lower low  -> hidden bullish
    candles, osc = _divergence_fixture(low2=96.0, osc_low1=35.0, osc_low2=20.0)
    kinds = {d.kind for d in detect_divergences(candles, oscillator=osc)}
    assert "hidden_bullish" in kinds

    # Bearish mirrors via inverted price series driving swing HIGHS.
    def invert(candles):
        return [Candle(200 - c.open, 200 - c.low, 200 - c.high,
                       200 - c.close, c.volume) for c in candles]

    candles, osc = _divergence_fixture(low2=92.0, osc_low1=80.0, osc_low2=65.0)
    kinds = {d.kind for d in detect_divergences(invert(candles), oscillator=osc)}
    assert "regular_bearish" in kinds

    candles, osc = _divergence_fixture(low2=96.0, osc_low1=65.0, osc_low2=80.0)
    kinds = {d.kind for d in detect_divergences(invert(candles), oscillator=osc)}
    assert "hidden_bearish" in kinds


def test_rsi_default_oscillator_smoke():
    down = _downtrend(60)
    assert isinstance(detect_divergences(down), list)


def test_rsi_series_bounds():
    closes = [100 + math.sin(i / 3.0) * 5 for i in range(60)]
    series = rsi_series(closes)
    assert series and all(0.0 <= v <= 100.0 for v in series)


# -------------------------------------------------------------- aggregation


def test_aggregation_is_ohlcv_correct_and_drops_partials():
    candles = [
        Candle(1, 5, 0.5, 2, 10),
        Candle(2, 6, 1.5, 3, 20),
        Candle(3, 7, 2.5, 4, 30),
        Candle(4, 8, 3.5, 5, 40),
        Candle(5, 9, 4.5, 6, 50),   # partial group of 1 at factor 2 -> dropped
    ]
    rolled = aggregate_candles(candles, 2)
    assert len(rolled) == 2
    assert rolled[0] == Candle(1, 6, 0.5, 3, 30)
    assert rolled[1] == Candle(3, 8, 2.5, 5, 70)


# ------------------------------------------------------------- cross-exam


def _view(tf, trend, patterns=(), divergences=()):
    return TimeframeView(tf, trend, None, tuple(patterns), tuple(divergences),
                         50.0, 100)


def test_cross_exam_weights_higher_timeframes_and_names_disagreements():
    from autonomy.crypto_chartist import DivergenceHit

    views = {
        "5m": _view("5m", -0.6),
        "1h": _view("1h", 0.5),
        "1d": _view("1d", 0.7),
    }
    exam = cross_examine(views)
    assert exam.score > 0                        # the daily outweighs the 5m
    assert any("5m" in d for d in exam.disagreements)

    vetoed = cross_examine({
        "1d": _view("1d", 0.7, divergences=[
            DivergenceHit("regular_bearish", -1, 0.9)]),
    })
    plain = cross_examine({"1d": _view("1d", 0.7)})
    assert vetoed.score < plain.score            # regular-against-trend cuts
    assert vetoed.vetoes

    boosted = cross_examine({
        "1d": _view("1d", 0.5, divergences=[
            DivergenceHit("hidden_bullish", 1, 0.8)]),
    })
    assert boosted.score > plain.score * 0.7 and boosted.boosts


# ------------------------------------------------------------------ signal


def _state(closes_up=True):
    n = 240
    step = 30.0 if closes_up else -30.0
    closes = [100000.0 + step * i for i in range(n)]
    ohlcv = {
        "at_s": list(range(n)),
        "open": [c - step for c in closes],
        "high": [c + 20 for c in closes],
        "low": [c - 20 for c in closes],
        "close": closes,
        "volume": [10.0] * n,
    }
    return {
        "spot": closes[-1],
        "minute_ohlcv": ohlcv,
        "hourly_ohlcv": ohlcv,
        "daily_ohlcv": ohlcv,
        "realized_vol_60m_annualized": 0.5,
    }


def _market():
    return MarketView(
        ticker="KXBTCD-26JUL1817-T118000.01", title="BTC?",
        vertical=Vertical.CRYPTO, status="open",
        close_time="2026-07-18T17:15:00+00:00", yes_bid=44, yes_ask=46,
        no_bid=54, no_ask=56, volume=10, liquidity=10,
        raw={"floor_strike": 107000.0, "strike_type": "greater"})


def test_signal_emits_trend_shaped_probability_and_full_audit():
    signal = CryptoChartistSignal(
        fetch_state=lambda asset: _state(True),
        hours_to_close=lambda market: 0.25)
    signal.on_cycle_start()
    market = _market()
    assert signal.applicable(market) is True
    out = signal.generate(market)
    assert out is not None
    assert out.source == "crypto_chartist"
    assert out.features["challenger_only"] is True
    assert out.features["chart_score"] > 0
    assert set(out.features["chart_votes"]) >= {"1h", "1d"}
    assert 0.10 <= out.uncertainty <= 0.35


def test_signal_abstains_without_conviction_or_state():
    flat = {**_state(True)}
    flat_closes = [100000.0] * 240
    flat["minute_ohlcv"] = {**flat["minute_ohlcv"], "close": flat_closes,
                            "open": flat_closes, "high": [c + 1 for c in flat_closes],
                            "low": [c - 1 for c in flat_closes]}
    flat["hourly_ohlcv"] = flat["minute_ohlcv"]
    flat["daily_ohlcv"] = flat["minute_ohlcv"]
    flat["spot"] = 100000.0
    quiet = CryptoChartistSignal(
        fetch_state=lambda asset: flat, hours_to_close=lambda market: 0.25)
    quiet.on_cycle_start()
    assert quiet.generate(_market()) is None     # no conviction in chop

    dead = CryptoChartistSignal(
        fetch_state=lambda asset: {}, hours_to_close=lambda market: 0.25)
    dead.on_cycle_start()
    assert dead.generate(_market()) is None
