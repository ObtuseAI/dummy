"""WS-18 reliability calibration: PAV isotonic + challenger wrapper."""
from __future__ import annotations

from dataclasses import dataclass, field

import json

import pytest

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.reliability import (
    CalibratedSignal,
    ReliabilityMaps,
    _pav_isotonic,
    apply_reliability,
    fit_maps_from_rows,
    fit_reliability_map,
)


def _brier(p, outcome):
    return (p - outcome) ** 2


# -- PAV isotonic --------------------------------------------------------------

def test_pav_makes_monotone_and_preserves_when_already_sorted():
    already = _pav_isotonic([0.1, 0.4, 0.9], [1, 1, 1])
    assert already == pytest.approx([0.1, 0.4, 0.9])
    # A violator (middle too high) gets pooled with its neighbor.
    pooled = _pav_isotonic([0.2, 0.9, 0.3], [1, 1, 1])
    assert pooled[0] <= pooled[1] <= pooled[2]
    assert pooled[1] == pytest.approx((0.9 + 0.3) / 2)


# -- fit + apply ---------------------------------------------------------------

def _overconfident_pairs(n_clusters=300, predicted=0.9, win_rate=0.75):
    # One cluster each: source always predicts `predicted`, wins at win_rate.
    pairs = []
    for i in range(n_clusters):
        outcome = 1.0 if (i % 100) < int(win_rate * 100) else 0.0
        pairs.append((predicted, outcome, f"E{i}"))
    return pairs


def test_fit_maps_overconfident_source_toward_realized_rate():
    # Two prediction levels so the curve has spread: 0.9->0.75 and 0.6->0.55.
    pairs = _overconfident_pairs(300, 0.9, 0.75) + [
        (0.6, 1.0 if i % 20 < 11 else 0.0, f"F{i}") for i in range(300)
    ]
    knots = fit_reliability_map(pairs)
    assert knots is not None
    # The high-confidence knot is pulled down toward the realized ~0.75.
    high = [c for p, c in knots if p > 0.8][0]
    assert 0.70 < high < 0.80
    # Applying the map to 0.9 lowers it; the corrected Brier beats the raw one
    # on a held-out sample from the same distribution.
    corrected = apply_reliability(knots, 0.9)
    assert corrected < 0.9
    raw_brier = sum(_brier(0.9, o) for _p, o, _c in _overconfident_pairs(200, 0.9, 0.75))
    cal_brier = sum(_brier(corrected, o) for _p, o, _c in _overconfident_pairs(200, 0.9, 0.75))
    assert cal_brier < raw_brier


def test_undersampled_scope_yields_no_map():
    assert fit_reliability_map(_overconfident_pairs(50)) is None  # < 200 clusters


def test_apply_reliability_identity_and_clamp():
    assert apply_reliability(None, 0.42) == 0.42
    assert apply_reliability([], 0.42) == 0.42
    knots = [(0.2, 0.25), (0.8, 0.7)]
    # Interpolates within range.
    mid = apply_reliability(knots, 0.5)
    assert 0.25 < mid < 0.7
    # Flat + clamped outside range.
    assert apply_reliability(knots, 0.99) == pytest.approx(0.7)
    assert apply_reliability([(0.5, 0.0)], 0.5) == 0.005  # clamped floor


# -- maps artifact + wrapper ---------------------------------------------------

@dataclass
class _Row:
    source: str
    ticker: str
    event_cluster: str
    probability_yes: float
    result_yes: bool
    scope: str
    features: dict = field(default_factory=dict)


def test_fit_maps_from_rows_only_curated_sources(tmp_path):
    rows = []
    # Two prediction levels give the curve the spread it needs to fit.
    for i in range(300):
        pred = 0.9 if i % 2 else 0.6
        rows.append(_Row("crypto_spot_vol", f"KXBTCD-{i}-T70000", f"E{i}",
                         pred, (i % 4) != 0, "crypto_spot_vol|ladder|daily+"))
        rows.append(_Row("some_other_source", f"KXBTCD-{i}-T70000", f"E{i}",
                         pred, (i % 4) != 0, "some_other_source|ladder|daily+"))
    maps = fit_maps_from_rows(rows)
    assert "crypto_spot_vol|ladder|daily+" in maps
    assert not any("some_other_source" in k for k in maps)  # not curated


def _market():
    return MarketView(
        ticker="KXBTCD-26JUL0917-T70000", title="BTC?", vertical=Vertical.CRYPTO,
        status="open", close_time="2026-07-10T00:00:00+00:00",
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56, volume=1, liquidity=1, raw={})


class _Parent:
    name = "crypto_spot_vol"

    def __init__(self, signal):
        self._signal = signal

    def applicable(self, market):
        return True

    def generate(self, market):
        return self._signal


def _maps_file(tmp_path, mapping):
    path = tmp_path / "reliability_maps.json"
    path.write_text(json.dumps({"maps": mapping}), encoding="utf-8")
    return ReliabilityMaps(path)


def test_wrapper_recalibrates_and_preserves_features(tmp_path):
    market = _market()
    raw = Signal(source="crypto_spot_vol", market_ticker=market.ticker,
                 probability_yes=0.9, uncertainty=0.1, rationale="",
                 features={"challenger_only": False, "hours_to_close": 26.0, "foo": "bar"})
    maps = _maps_file(
        tmp_path,
        {"crypto_spot_vol|btc|ladder|daily+": [[0.6, 0.55], [0.9, 0.75]]},
    )
    wrapper = CalibratedSignal(_Parent(raw), maps=maps)
    out = wrapper.generate(market)
    assert out is not None
    assert out.source == "crypto_spot_vol::cal"
    assert out.probability_yes == pytest.approx(0.75)  # 0.9 -> 0.75 via the map
    assert out.features["challenger_only"] is True     # wrapper is always a challenger
    assert out.features["calibrated_from"] == "crypto_spot_vol"
    assert out.features["raw_probability_yes"] == 0.9
    assert out.features["foo"] == "bar"                # parent features preserved


def test_wrapper_abstains_without_a_map_or_uncurated_source(tmp_path):
    market = _market()
    raw = Signal(source="crypto_spot_vol", market_ticker=market.ticker,
                 probability_yes=0.9, uncertainty=0.1, rationale="",
                 features={"hours_to_close": 26.0})
    empty = _maps_file(tmp_path, {})  # no map for this scope
    assert CalibratedSignal(_Parent(raw), maps=empty).generate(market) is None
    # Uncurated source -> abstain even with a map present.
    uncurated = Signal(source="weather_openmeteo", market_ticker=market.ticker,
                       probability_yes=0.9, uncertainty=0.1, rationale="", features={})

    class _WeatherParent(_Parent):
        name = "weather_openmeteo"

    maps = _maps_file(tmp_path, {"weather_openmeteo|na|pre": [[0.6, 0.55], [0.9, 0.75]]})
    assert CalibratedSignal(_WeatherParent(uncurated), maps=maps).generate(market) is None


def test_wrapper_fails_closed_on_parent_error_and_opens_circuit(tmp_path):
    class _Boom:
        name = "crypto_spot_vol"
        calls = 0

        def applicable(self, m):
            return True

        def generate(self, m):
            _Boom.calls += 1
            raise RuntimeError("parent down")

    parent = _Boom()
    maps = _maps_file(
        tmp_path,
        {"crypto_spot_vol|btc|ladder|daily+": [[0.9, 0.75]]},
    )
    wrapper = CalibratedSignal(parent, maps=maps)
    # First market call trips the breaker; subsequent calls skip the parent.
    assert wrapper.generate(_market()) is None
    assert wrapper.generate(_market()) is None
    assert wrapper.generate(_market()) is None
    assert parent.calls == 1  # breaker prevents the per-market fetch storm
    # A fresh cycle resets the breaker.
    wrapper.on_cycle_start()
    assert wrapper.generate(_market()) is None
    assert parent.calls == 2


def test_wrapper_abstains_when_parent_returns_none(tmp_path):
    class _NoneParent(_Parent):
        def generate(self, market):
            return None

    maps = _maps_file(
        tmp_path,
        {"crypto_spot_vol|btc|ladder|daily+": [[0.9, 0.75]]},
    )
    assert CalibratedSignal(_NoneParent(None), maps=maps).generate(_market()) is None


def test_pav_pools_with_unequal_weights():
    # A high-weight low value pools a low-weight high value below it.
    fitted = _pav_isotonic([0.2, 0.8, 0.3], [1.0, 1.0, 10.0])
    assert fitted[0] <= fitted[1] <= fitted[2]
    # The pooled 0.8/0.3 mean is weighted toward the heavier 0.3.
    pooled_mean = (0.8 * 1.0 + 0.3 * 10.0) / 11.0
    assert fitted[1] == pytest.approx(pooled_mean)


def test_calibrated_source_shares_parent_family_in_fuser():
    from autonomy.forecaster import SOURCE_FAMILIES

    # The fuser strips ::cal so a promoted calibrated challenger cannot form a
    # second family alongside the parent it recalibrates.
    base = "crypto_spot_vol::cal"[:-5]
    assert base == "crypto_spot_vol"
    assert SOURCE_FAMILIES.get(base) == SOURCE_FAMILIES.get("crypto_spot_vol")
