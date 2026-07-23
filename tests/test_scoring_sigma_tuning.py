"""Sigma tuning: likelihood objective, tuned override, PBP disclosure."""
from __future__ import annotations

import json

from autonomy.sports.walk_forward import sigma_log_likelihood
from autonomy.sports.tuner import tune_scoring_sigmas, TUNED_PATH  # noqa: F401
from autonomy.sports.scoring_model import LakeScoringModel
from autonomy.sports.history_store import SportsHistoryStore


def test_sigma_loglik_prefers_the_true_spread():
    import random

    rng = random.Random(7)
    residuals = [rng.gauss(0.0, 10.0) for _ in range(500)]
    ll_true = sigma_log_likelihood(residuals, 10.0)
    assert ll_true is not None
    for wrong in (5.0, 20.0):
        assert sigma_log_likelihood(residuals, wrong) < ll_true
    assert sigma_log_likelihood([], 10.0) is None
    assert sigma_log_likelihood(residuals, 0.0) is None


def test_tune_scoring_sigmas_selects_near_empirical(tmp_path, monkeypatch):
    import random

    rng = random.Random(11)

    def fake_residuals(store, league, *, min_games=5):
        # True sigma ~ 0.9x the NBA prior of 12 => grid should pick 0.9.
        return [(rng.gauss(0.0, 10.8), rng.gauss(0.0, 15.0)) for _ in range(400)]

    monkeypatch.setattr(
        "autonomy.sports.walk_forward.collect_scoring_residuals", fake_residuals,
    )
    out = tune_scoring_sigmas(SportsHistoryStore(tmp_path / "lake.db"), "nba")
    assert out["scoring_sigma_margin"]["value"] == 10.8  # 12.0 * 0.9
    assert out["scoring_sigma_margin"]["objective"] == "mean_normal_loglik"
    assert out["scoring_sigma_total"]["n"] == 400


def test_scoring_model_prefers_tuned_sigma(tmp_path, monkeypatch):
    tuned = tmp_path / "sports_tuned_params.json"
    tuned.write_text(json.dumps({
        "generated_at": "2026-07-22T00:00:00+00:00",
        "leagues": {"nba": {
            "scoring_sigma_margin": {"param": "sigma_margin", "value": 11.1},
            "scoring_sigma_total": {"param": "sigma_total", "value": 16.2},
        }},
    }), encoding="utf-8")
    monkeypatch.setattr("autonomy.sports.tuner.TUNED_PATH", tuned)
    model = LakeScoringModel(SportsHistoryStore(tmp_path / "lake.db"), "nba")
    assert model.sigma_margin == 11.1
    assert model.sigma_total == 16.2
    # Explicit constructor values (the tuner's own grid) win last.
    override = LakeScoringModel(
        SportsHistoryStore(tmp_path / "lake2.db"), "nba", sigma_margin=9.9,
    )
    assert override.sigma_margin == 9.9
