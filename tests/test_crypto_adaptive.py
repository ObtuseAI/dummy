"""Wave-8 adaptive challengers: patience-with-confirmation + KAMA momentum."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.crypto_adaptive import (
    CryptoKamaMomentumSignal,
    CryptoPatienceSignal,
    efficiency_ratio,
    kama,
)


_DEFAULT_RAW = object()


def _market(minutes_left, *, ticker="KXSOL15M-26JUL172100-30", raw=_DEFAULT_RAW):
    close = datetime.now(timezone.utc) + timedelta(minutes=minutes_left)
    if raw is _DEFAULT_RAW:
        raw = {"floor_strike": 75.0}
    return MarketView(
        ticker=ticker, title="", vertical=Vertical.CRYPTO, status="active",
        close_time=close.isoformat(), yes_bid=40, yes_ask=44, no_bid=56, no_ask=60,
        volume=100, liquidity=1000, raw=raw,
    )


def _state(spot, closes):
    return {"spot": spot, "minute_closes": closes,
            "realized_vol_60m_annualized": 0.6}


class _Parent:
    """Deterministic champion double."""

    source = "crypto_blend_sigma"

    def __init__(self, p=0.80):
        self._p = p

    def generate(self, market):
        from autonomy.ontology import Signal

        return Signal(source=self.source, market_ticker=market.ticker,
                      probability_yes=self._p, uncertainty=0.15, rationale="",
                      features={"challenger_only": True})


def _patience(state, parent_p=0.80):
    return CryptoPatienceSignal(
        fetch_state=lambda asset: state, parent=_Parent(parent_p))


# ---- patience gates -----------------------------------------------------------

def test_patience_silent_early_in_window():
    # 12 of 15 minutes left (>40% of window) -> too early, no opinion.
    signal = _patience(_state(76.0, [75.0] * 60)).generate(_market(12))
    assert signal is None


def test_patience_emits_late_when_spot_through_reference():
    # 4 minutes left, model says YES(>=75), spot already 76 -> confirmed.
    signal = _patience(_state(76.0, [75.0] * 60)).generate(_market(4))
    assert signal is not None
    assert signal.source == "crypto_patience_confirm"
    assert signal.probability_yes == 0.80
    assert signal.features["confirmed_by"] == "spot_through_reference"
    assert signal.features["challenger_only"] is True
    assert signal.uncertainty < 0.15                    # confirmation tightens


def test_patience_refuses_unconfirmed_prediction():
    # Model says YES(>=75) but spot sits at 74.2 having drifted AWAY from the
    # reference since the window opened (74.8 -> 74.2): no confirmation.
    closes = [74.8] * 60
    signal = _patience(_state(74.2, closes)).generate(_market(4))
    assert signal is None


def test_patience_accepts_strong_drift_toward_reference():
    # Window opened at 74.0 (gap 1.0 to the 75 reference); spot now 74.6 has
    # covered 60% of the gap -> drift-confirmed even though not yet through.
    closes = [74.0] * 60
    signal = _patience(_state(74.6, closes)).generate(_market(4))
    assert signal is not None
    assert signal.features["confirmed_by"] == "drift_toward_reference"


def test_patience_hourly_ladder_in_scope_daily_out():
    state = _state(64100.0, [64000.0] * 90)
    hourly = _market(20, ticker="KXBTCD-26JUL1722-T64000",
                     raw={"strike_type": "greater", "floor_strike": 64000.0})
    assert _patience(state).generate(hourly) is not None
    daily = _market(60 * 9, ticker="KXBTCD-26JUL1817-T64000",
                    raw={"strike_type": "greater", "floor_strike": 64000.0})
    assert _patience(state).generate(daily) is None     # daily+ out of scope


def test_patience_fail_closed_without_reference_or_state():
    assert _patience(_state(76.0, [75.0] * 60)).generate(
        _market(4, raw={})) is None                      # no reference
    assert _patience({}).generate(_market(4)) is None    # no state


# ---- KAMA ---------------------------------------------------------------------

def _trend(n=90, start=100.0, step=0.05):
    return [start + step * i for i in range(n)]


def _chop(n=90, base=100.0):
    return [base + (0.4 if i % 2 else -0.4) for i in range(n)]


def test_kama_tracks_trend_and_er_separates_regimes():
    trend = _trend()
    assert efficiency_ratio(trend) > 0.9                # clean trend
    assert efficiency_ratio(_chop()) < 0.15             # chop
    anchor = kama(trend)
    assert anchor is not None and anchor < trend[-1]    # lags below rising price


def test_kama_momentum_leans_with_trend_and_flattens_in_chop():
    source = CryptoKamaMomentumSignal(fetch_state=lambda a: _state(104.5, _trend()))
    market = _market(6, raw={"floor_strike": 104.5})    # ref at spot: no-drift p ~= 0.5
    trending = source.generate(market)
    assert trending is not None
    assert trending.probability_yes > 0.55              # drift pushes above coin
    assert trending.features["challenger_only"] is True

    choppy_source = CryptoKamaMomentumSignal(fetch_state=lambda a: _state(100.0, _chop()))
    choppy = choppy_source.generate(_market(6, raw={"floor_strike": 100.0}))
    assert choppy is not None
    assert abs(choppy.probability_yes - 0.5) < 0.07     # converges to no-drift
    assert choppy.uncertainty > trending.uncertainty    # chop earns wide bands


def test_kama_momentum_fail_closed_paths():
    source = CryptoKamaMomentumSignal(fetch_state=lambda a: _state(100.0, [100.0] * 10))
    assert source.generate(_market(6)) is None           # too few closes
    source = CryptoKamaMomentumSignal(fetch_state=lambda a: {})
    assert source.generate(_market(6)) is None           # no state
    source = CryptoKamaMomentumSignal(fetch_state=lambda a: _state(100.0, _trend()))
    assert source.generate(_market(6, raw={})) is None   # no reference


def test_drift_is_bounded():
    # An absurdly steep trend must not out-shout its own noise: probability
    # stays inside the drift cap's reach rather than saturating at 0.995.
    steep = [100.0 + 2.0 * i for i in range(90)]
    source = CryptoKamaMomentumSignal(fetch_state=lambda a: _state(278.0, steep))
    signal = source.generate(_market(6, raw={"floor_strike": 278.0}))
    assert signal is not None
    assert signal.features["drift_sigmas"] <= 0.75 + 1e-9
