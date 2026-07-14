from __future__ import annotations

from dataclasses import dataclass as _dc

from autonomy.sports.mlb_validation import HeadVerdict, MlbEngineScorecard, SettledDecision, settled_decisions_for, beat_close_head, calibration_head, paper_pnl_head, score_engine, scorecard_to_dict


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


def test_beat_close_head_rejects_single_cluster_even_above_min_n():
    # 40 contested decisions all in ONE event cluster: the bootstrap CI collapses,
    # so a positive mean must NOT pass without cluster diversity.
    decisions = [_dec("only_game", 0.85, 0.55, True) for _ in range(40)]
    verdict = beat_close_head(decisions)
    assert verdict.detail["contested_n"] == 40
    assert verdict.detail["event_clusters"] == 1
    assert verdict.passed is False


def test_calibration_head_full_surface_edge():
    # Model consistently closer to the outcome than the market across 30 games.
    decisions = [_dec(f"g{i}", 0.90, 0.60, True) for i in range(30)]
    verdict = calibration_head(decisions)
    assert verdict.name == "calibration"
    assert verdict.n == 30
    assert verdict.metric is not None and verdict.metric > 0
    assert verdict.passed is True


def test_calibration_head_empty_is_unproven():
    verdict = calibration_head([])
    assert verdict.passed is False and verdict.n == 0


def test_paper_pnl_head_sums_realized():
    decisions = [
        _dec("g1", 0.6, 0.5, True, pnl=40),
        _dec("g2", 0.4, 0.5, False, pnl=-15),
        _dec("g3", 0.6, 0.5, True, pnl=None),  # no realized P&L -> excluded
    ]
    verdict = paper_pnl_head(decisions)
    assert verdict.name == "paper_pnl"
    assert verdict.metric == 25.0  # 40 - 15
    assert verdict.n == 2
    assert verdict.passed is True


def test_paper_pnl_head_negative_fails():
    decisions = [_dec("g1", 0.6, 0.5, False, pnl=-52)]
    verdict = paper_pnl_head(decisions)
    assert verdict.passed is False


def test_score_engine_assembles_all_three_heads():
    from autonomy.sports.mlb_validation import score_engine
    rows = []
    pnl = {}
    for i in range(20):
        rows.append(_Row(f"w{i}", "mlb_pa_sim", "winner", f"win{i}", 0.85, 0.55, True))
        rows.append(_Row(f"l{i}", "mlb_pa_sim", "winner", f"loss{i}", 0.15, 0.45, False))
        pnl[f"w{i}"] = 30
        pnl[f"l{i}"] = 20
    # Noise from another source must be ignored.
    rows.append(_Row("x", "mlb_gbm", "winner", "g1", 0.5, 0.5, True))
    card = score_engine(rows, pnl, "mlb_pa_sim")
    assert card.source == "mlb_pa_sim"
    assert card.settled == 40
    assert card.beat_close.name == "beat_close"
    assert card.calibration.name == "calibration"
    assert card.paper_pnl.name == "paper_pnl"
    assert card.beat_close.passed is True
    assert card.is_champion_ready is True


def test_score_engine_no_decisions_is_unproven():
    from autonomy.sports.mlb_validation import score_engine
    card = score_engine([], {}, "mlb_pa_sim")
    assert card.settled == 0
    assert card.is_champion_ready is False
    assert card.beat_close.n == 0


def test_scorecard_to_dict_is_json_safe():
    import json
    card = score_engine(
        [_Row("a", "s", "winner", "g1", 0.6, 0.52, True)], {"a": 10}, "s",
    )
    payload = scorecard_to_dict(card)
    # Round-trips through JSON without error and preserves the primary verdict.
    text = json.dumps(payload)
    back = json.loads(text)
    assert back["source"] == "s"
    assert back["is_champion_ready"] == card.is_champion_ready
    assert back["heads"]["beat_close"]["name"] == "beat_close"
