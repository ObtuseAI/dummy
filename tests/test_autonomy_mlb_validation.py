from __future__ import annotations

from autonomy.sports.mlb_validation import HeadVerdict, MlbEngineScorecard


def test_scorecard_champion_ready_tracks_primary_head_only():
    beat = HeadVerdict(name="beat_close", passed=True, metric=0.02, n=40, detail={})
    calib = HeadVerdict(name="calibration", passed=False, metric=-0.01, n=100, detail={})
    pnl = HeadVerdict(name="paper_pnl", passed=True, metric=150.0, n=100, detail={})
    card = MlbEngineScorecard(
        source="mlb_pa_sim", settled=100,
        beat_close=beat, calibration=calib, paper_pnl=pnl,
    )
    # Primary head (beat the close) alone gates champion readiness.
    assert card.is_champion_ready is True
    # A failed primary head blocks it regardless of the sanity heads.
    blocked = MlbEngineScorecard(
        source="x", settled=100,
        beat_close=HeadVerdict("beat_close", False, -0.01, 40, {}),
        calibration=calib, paper_pnl=pnl,
    )
    assert blocked.is_champion_ready is False
