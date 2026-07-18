"""Wave-21: the ROI proof-of-profit door -- a second, independent promotion route."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from autonomy.auto_promotion import (
    DEFAULT_CONFIG,
    AutoPromotionEngine,
    RailsVerdict,
    roi_door_evidence,
)

SCOPE = "crypto_equities_flow|sol|15m_direction|15m"


class _Row:
    """Contested rows entered cheap (market 0.30, model 0.40) that win often:
    entry cost 0.30, payoff 1 on a win -> fee-adjusted ROI far above +5%."""

    def __init__(self, i, win, day=None):
        self.source = "crypto_equities_flow"
        self.ticker = f"KXSOLD-26JUL{(i % 15) + 1:02d}-T{160 + i}"
        self.event_cluster = f"C{i}"
        self.created_at = f"2026-07-{(day if day is not None else (i % 15) + 1):02d}T12:00:00+00:00"
        self.probability_yes = 0.40
        self.market_probability = 0.30
        self.result_yes = win
        self.features = {}
        self.scope = SCOPE


def _rows(n=240, win_rate=0.45):
    # i % 20 cycles exactly (n divisible by 20), so the realized win rate is
    # EXACTLY win_rate and spread evenly across clusters/days.
    return [_Row(i, win=(i % 20) < int(win_rate * 20)) for i in range(n)]


# Evidence door slammed shut so only the ROI door can admit the scope.
_ROI_ONLY = replace(DEFAULT_CONFIG, min_beat_rate=1.01)


def test_roi_door_evidence_passes_on_profit():
    door = roi_door_evidence(SCOPE, _rows(), config=_ROI_ONLY)
    assert door["pass"] is True
    # 45% wins at 0.30 entries: ROI ~ (0.45 - 0.30 - fees) / 0.30 >> 5%.
    assert door["roi_on_entry_cost"] > 0.05
    assert door["roi_ci95"]["lower"] > 0.0
    assert door["n_clusters"] == 240
    assert door["span_days"] >= DEFAULT_CONFIG.roi_path_min_span_days


def test_roi_door_fails_on_thin_profit_volume_or_span():
    # Wins exactly at the market-implied rate: ROI 0 (fees are zero on this
    # series), squarely under the +5% bar.
    breakeven = roi_door_evidence(
        SCOPE, _rows(win_rate=0.30), config=_ROI_ONLY)
    assert breakeven["pass"] is False
    assert abs(breakeven["roi_on_entry_cost"]) < 0.01

    # Profitable but under the cluster bar.
    thin = roi_door_evidence(SCOPE, _rows(n=100), config=_ROI_ONLY)
    assert thin["pass"] is False and thin["n_clusters"] == 100

    # Profitable but squeezed into one day.
    one_day = [_Row(i, win=(i % 20) < 9, day=9) for i in range(240)]
    squeezed = roi_door_evidence(SCOPE, one_day, config=_ROI_ONLY)
    assert squeezed["pass"] is False and squeezed["span_days"] == 0.0


def _decide(rows, config):
    engine = AutoPromotionEngine(config)
    return engine.decide(
        scope_rows={SCOPE: rows},
        promoted={},
        now_ts=datetime(2026, 7, 18, tzinfo=timezone.utc).timestamp(),
        now_iso="2026-07-18T12:00:00+00:00",
        rails=RailsVerdict(abort=False, reasons=[]),
        eligible_scopes={SCOPE},
    )


def test_engine_promotes_through_the_roi_door():
    result = _decide(_rows(), _ROI_ONLY)
    assert len(result.promotions) == 1
    decision = result.promotions[0]
    assert decision.scope == SCOPE and decision.stage == 1
    assert decision.dossier["promotion_path"] == "roi_proof_of_profit"
    assert decision.dossier["roi_door"]["pass"] is True
    assert decision.weight_fraction == DEFAULT_CONFIG.stage1_weight_fraction
    assert result.declined == []


def test_engine_declines_carry_the_roi_door_verdict():
    result = _decide(_rows(win_rate=0.30), _ROI_ONLY)   # break-even record
    assert result.promotions == []
    assert len(result.declined) == 1
    declined = result.declined[0]
    assert declined.dossier["roi_door"]["pass"] is False
    assert "roi door" in declined.reason


def test_roi_thresholds_ride_the_config_dict():
    as_dict = DEFAULT_CONFIG.as_dict()
    assert as_dict["roi_path_min_roi"] == 0.05
    assert as_dict["roi_path_min_clusters"] == 200
    assert as_dict["roi_path_min_span_days"] == 7.0
