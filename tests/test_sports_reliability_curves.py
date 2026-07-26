"""Wave-3: empirical sports reliability curves (pre/live per-context split)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.reliability import (
    CALIBRATED_SOURCES,
    CRYPTO_CALIBRATED_SOURCES,
    SPORTS_CALIBRATED_SOURCES,
    CalibratedSignal,
    ReliabilityMaps,
    apply_reliability,
    fit_maps_from_rows,
    build_reliability_artifact,
)
from autonomy.taxonomy import grading_scope


@dataclass
class _Row:
    source: str
    ticker: str
    event_cluster: str
    probability_yes: float
    result_yes: bool
    scope: str
    features: dict = field(default_factory=dict)


def _rows(source, scope, n_clusters, *, win_rate, prefix="E"):
    """n_clusters independent clusters at two prediction levels (spread) so the
    curve can be fit; the high level realizes at ``win_rate``."""
    rows = []
    for i in range(n_clusters):
        pred = 0.9 if i % 2 else 0.6
        target = win_rate if i % 2 else 0.55
        outcome = (i % 100) < int(target * 100)
        rows.append(_Row(source, f"{source.upper()}-{i}", f"{prefix}{i}", pred, outcome, scope))
    return rows


# ---- rollout membership ------------------------------------------------------

def test_sports_sources_are_registered_and_curated():
    # Pre-game + live winners/totals across leagues are eligible...
    for s in ("nba_structural_winner", "nhl_game_total", "ncaaf_live_total",
              "mlb_live_winner", "mlb_pa_live_winner", "mlb_total_runs",
              "mlb_structural_winner"):
        assert s in SPORTS_CALIBRATED_SOURCES
        assert s in CALIBRATED_SOURCES
    # ...but the rollout stays curated: spreads and niche props are NOT auto-in.
    for s in ("mlb_run_spread", "nba_live_spread", "mlb_first_inning_run"):
        assert s not in CALIBRATED_SOURCES
    # Crypto rollout preserved and disjoint from sports.
    assert CRYPTO_CALIBRATED_SOURCES <= CALIBRATED_SOURCES
    assert not (CRYPTO_CALIBRATED_SOURCES & SPORTS_CALIBRATED_SOURCES)


# ---- empirical curve fit for a sports scope ----------------------------------

def test_fit_sports_scope_curve_is_monotone_and_corrects_overconfidence():
    scope = "nba_structural_winner|team|winner|pre"
    maps = fit_maps_from_rows(_rows("nba_structural_winner", scope, 300, win_rate=0.72))
    assert scope in maps
    knots = maps[scope]
    # Monotone non-decreasing (isotonic guarantee).
    assert all(c0 <= c1 + 1e-9 for (_p0, c0), (_p1, c1) in zip(knots, knots[1:]))
    # A 0.90 pre-game favorite is pulled down toward its realized ~0.72.
    corrected = apply_reliability(knots, 0.9)
    assert 0.66 < corrected < 0.80


def test_undersampled_sports_scope_abstains():
    scope = "ncaamb_structural_winner|team|winner|pre"
    # Only 50 clusters -> below MIN_CALIBRATION_CLUSTERS -> no map (fail-closed).
    maps = fit_maps_from_rows(_rows("ncaamb_structural_winner", scope, 50, win_rate=0.7))
    assert scope not in maps


def test_uncurated_sports_source_gets_no_map_even_when_well_sampled():
    scope = "mlb_run_spread|team|spread|pre"
    # Deliberately excluded from the curated rollout -> filtered out of fitting.
    maps = fit_maps_from_rows(_rows("mlb_run_spread", scope, 400, win_rate=0.7))
    assert not maps


# ---- per-context (pre-game vs live) split ------------------------------------

def test_pregame_and_live_scopes_get_independent_maps():
    pre_scope = "mlb_structural_winner|nyy|winner|pre"
    live_scope = "mlb_live_winner|nyy|winner|live"
    rows = (
        _rows("mlb_structural_winner", pre_scope, 300, win_rate=0.72, prefix="P")   # overconfident
        + _rows("mlb_live_winner", live_scope, 300, win_rate=0.95, prefix="L")      # well-calibrated/underconfident
    )
    maps = fit_maps_from_rows(rows)
    assert pre_scope in maps and live_scope in maps
    # The two contexts are NOT pooled: their 0.9 corrections differ materially.
    pre_corr = apply_reliability(maps[pre_scope], 0.9)
    live_corr = apply_reliability(maps[live_scope], 0.9)
    assert pre_corr < live_corr
    assert pre_corr < 0.80          # pre-game overconfidence corrected down
    assert live_corr > pre_corr + 0.10


# ---- challenger wrapper on a sports parent -----------------------------------

def _sports_market():
    return MarketView(
        ticker="KXMLBGAME-26JUL16NYYBOS-NYY", title="NYY win?", vertical=Vertical.SPORTS,
        status="open", close_time="2026-07-16T23:00:00+00:00",
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56, volume=1, liquidity=1, raw={})


class _Parent:
    def __init__(self, signal, name):
        self._signal = signal
        self.name = name

    def applicable(self, market):
        return True

    def generate(self, market):
        return self._signal


def _maps_file(tmp_path, mapping):
    path = tmp_path / "reliability_maps.json"
    path.write_text(
        json.dumps(
            build_reliability_artifact(
                mapping,
                generated_at="2026-07-26T00:00:00+00:00",
            )
        ),
        encoding="utf-8",
    )
    return ReliabilityMaps(path)


def test_wrapper_recalibrates_sports_source(tmp_path):
    market = _sports_market()
    features = {"market_type": "winner", "challenger_only": False}
    scope = grading_scope("nba_structural_winner", market.ticker, features)
    raw = Signal(source="nba_structural_winner", market_ticker=market.ticker,
                 probability_yes=0.9, uncertainty=0.12, rationale="", features=features)
    maps = _maps_file(tmp_path, {scope: [[0.6, 0.55], [0.9, 0.72]]})
    out = CalibratedSignal(_Parent(raw, "nba_structural_winner"), maps=maps).generate(market)
    assert out is not None
    assert out.source == "nba_structural_winner::cal"
    assert out.probability_yes == pytest.approx(0.72)
    assert out.features["challenger_only"] is True
    assert out.features["calibrated_from"] == "nba_structural_winner"


def test_wrapper_abstains_when_sports_scope_has_no_map(tmp_path):
    market = _sports_market()
    raw = Signal(source="nba_structural_winner", market_ticker=market.ticker,
                 probability_yes=0.9, uncertainty=0.12, rationale="", features={})
    empty = _maps_file(tmp_path, {})
    # No map for this scope -> abstain, parent's uncorrected view stands.
    assert CalibratedSignal(_Parent(raw, "nba_structural_winner"), maps=empty).generate(market) is None
