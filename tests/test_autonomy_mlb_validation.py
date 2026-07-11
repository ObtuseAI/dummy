from __future__ import annotations

from dataclasses import dataclass as _dc

from autonomy.sports.mlb_validation import HeadVerdict, MlbEngineScorecard, SettledDecision, settled_decisions_for, beat_close_head


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


@_dc
class _Row:
    observation_id: str
    source: str
    market_type: str
    event_cluster: str
    model_probability: float
    market_probability: float
    result_yes: object  # bool | None


def test_settled_decisions_filters_source_and_unsettled():
    rows = [
        _Row("a", "mlb_pa_sim", "winner", "g1", 0.60, 0.52, True),
        _Row("b", "mlb_pa_sim", "winner", "g2", 0.40, 0.55, False),
        _Row("c", "mlb_gbm", "winner", "g1", 0.70, 0.52, True),   # other source
        _Row("d", "mlb_pa_sim", "total", "g3", 0.50, 0.50, None),  # unsettled
    ]
    out = settled_decisions_for(rows, {"a": 30, "b": -20}, "mlb_pa_sim")
    assert [d.event_cluster for d in out] == ["g1", "g2"]
    assert out[0].pnl_cents == 30 and out[1].pnl_cents == -20
    assert all(d.source == "mlb_pa_sim" for d in out)
    assert all(isinstance(d.result_yes, bool) for d in out)


def _dec(cluster, model, market, result, pnl=0):
    return SettledDecision("mlb_pa_sim", "winner", cluster, model, market, result, pnl)


def test_beat_close_head_needs_min_contested_n():
    # Two contested decisions the model nails, but below MIN_CONTESTED_N -> fail.
    decisions = [
        _dec("g1", 0.80, 0.55, True),
        _dec("g2", 0.20, 0.45, False),
    ]
    verdict = beat_close_head(decisions)
    assert verdict.name == "beat_close"
    assert verdict.passed is False  # contested_n below the minimum
    assert verdict.n == 2


def test_beat_close_head_passes_when_model_beats_market_on_contested():
    # 40 contested decisions across 20 clusters; the model is confidently right
    # and the market is closer to 0.5, so the model's Brier edge is positive
    # with a lower bound above zero.
    decisions = []
    for i in range(20):
        decisions.append(_dec(f"win{i}", 0.85, 0.55, True))
        decisions.append(_dec(f"loss{i}", 0.15, 0.45, False))
    verdict = beat_close_head(decisions)
    assert verdict.n == 40
    assert verdict.metric is not None and verdict.metric > 0
    assert verdict.passed is True
    assert verdict.detail["contested_n"] == 40


def test_beat_close_head_ignores_uncontested():
    # Model agrees with the market (<5c apart) -> not contested -> excluded.
    decisions = [_dec(f"g{i}", 0.52, 0.51, True) for i in range(30)]
    verdict = beat_close_head(decisions)
    assert verdict.detail["contested_n"] == 0
    assert verdict.passed is False
