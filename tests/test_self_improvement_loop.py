"""Wave-20: tuner auto-promote overrides + the improvement planner."""
from __future__ import annotations

import json

from autonomy.improvement_planner import assemble_plan, write_plan
from autonomy.tuned_params import (
    CONSUMED_PARAMS,
    load_overrides,
    promote_from_report,
    value_in_force,
)


def _report(name="wnba_total_sigma", verdict="candidate", current=13.0, best=16.0):
    return {"proposals": [{
        "name": name, "verdict": verdict, "current": current, "best": best,
        "test_delta": 0.004, "test_delta_ci": {"lower": 0.001, "upper": 0.007},
        "n_clusters": 220,
    }]}


def test_promotion_is_step_capped_and_audited(tmp_path):
    path = tmp_path / "tuned_params.json"
    log = tmp_path / "log.jsonl"
    outcome = promote_from_report(
        _report(), now_iso="2026-07-18T07:00:00+00:00", path=path, log_path=log)
    assert len(outcome["applied"]) == 1
    move = outcome["applied"][0]
    # 13.0 -> capped at +20% = 15.6, NOT the full jump to 16.0.
    assert move["from"] == 13.0 and move["to"] == 15.6
    assert load_overrides(path)["wnba_total_sigma"] == 15.6
    assert value_in_force("wnba_total_sigma", 13.0, path) == 15.6
    assert len(log.read_text().strip().splitlines()) == 1

    # Second night walks the remaining distance (15.6 -> 16.0, inside cap).
    outcome2 = promote_from_report(
        _report(), now_iso="2026-07-19T07:00:00+00:00", path=path, log_path=log)
    assert outcome2["applied"][0]["to"] == 16.0
    # Third night: already in force -> no move, no log growth.
    outcome3 = promote_from_report(
        _report(), now_iso="2026-07-20T07:00:00+00:00", path=path, log_path=log)
    assert outcome3["applied"] == []
    assert len(log.read_text().strip().splitlines()) == 2


def test_only_candidate_verdicts_and_consumed_params_move(tmp_path):
    path = tmp_path / "tuned_params.json"
    keep = promote_from_report(
        _report(verdict="keep"), now_iso="t", path=path, log_path=tmp_path / "l")
    assert keep["applied"] == [] and not path.exists()

    unconsumed = promote_from_report(
        _report(name="nba_total_sigma_base"), now_iso="t",
        path=path, log_path=tmp_path / "l")
    assert unconsumed["applied"] == []
    assert unconsumed["skipped"][0]["reason"] == "no consumption point wired"
    assert "nba_total_sigma_base" not in CONSUMED_PARAMS


def test_value_in_force_fails_open(tmp_path):
    absent = tmp_path / "absent.json"
    assert value_in_force("wnba_total_sigma", 13.0, absent) == 13.0
    assert value_in_force("not_a_consumed_param", 7.0, absent) == 7.0


def test_team_score_model_consumes_override(tmp_path, monkeypatch):
    import autonomy.tuned_params as tuned_params
    from autonomy.sports.team_scores import LEAGUE_SCORE_CONFIGS, TeamScoreModel

    override_path = tmp_path / "tuned_params.json"
    override_path.write_text(json.dumps({
        "overrides": {"wnba_total_sigma": {"value": 15.6}}}), encoding="utf-8")
    monkeypatch.setattr(tuned_params, "OVERRIDES_PATH", override_path)
    model = TeamScoreModel("wnba")
    assert model.config.total_sigma == 15.6
    assert LEAGUE_SCORE_CONFIGS["wnba"].total_sigma == 13.0   # default untouched
    assert TeamScoreModel("nba").config.total_sigma == LEAGUE_SCORE_CONFIGS["nba"].total_sigma


def test_planner_ranks_and_annotates(tmp_path):
    (tmp_path / "loss_attribution.json").write_text(json.dumps({
        "scopes": [{"scope": "s_bleed", "verdict": "bleeding",
                    "cluster_edge": -0.02, "n_clusters": 40}]}), encoding="utf-8")
    (tmp_path / "negative_control_report.json").write_text(json.dumps({
        "flagged_sources": ["bad_source"]}), encoding="utf-8")
    (tmp_path / "promotion_declines.json").write_text(json.dumps({
        "declined": [{"scope": "s_decl", "reason": "failed: contested_beat_rate"}]
    }), encoding="utf-8")
    (tmp_path / "tuning_proposals.json").write_text(json.dumps({
        "proposals": [
            {"name": "wnba_total_sigma", "verdict": "candidate",
             "test_delta": 0.004, "best": 16.0},
            {"name": "nhl_home_edge", "verdict": "candidate",
             "test_delta": 0.002, "best": 0.2},
        ]}), encoding="utf-8")
    plan = assemble_plan(tmp_path)
    kinds = [item["kind"] for item in plan["items"]]
    # Measurement-integrity alarm outranks everything.
    assert kinds[0] == "negative_control_flag"
    assert plan["items"][0]["owner"] == "operator"
    assert "bleeding_scope" in kinds
    assert "promotion_declined" in kinds
    assert "tuning_pending" in kinds          # consumed param, not yet in force
    assert "tuning_unconsumed" in kinds       # nhl_home_edge has no consumer
    assert plan["counts"]["negative_control_flag"] == 1
    assert any("fusion_floor" in item["closed_loops"]
               for item in plan["items"] if item["kind"] == "bleeding_scope")

    path = write_plan(plan, tmp_path / "plan.json")
    assert json.loads(path.read_text())["report_name"] == "SELF_IMPROVEMENT_PLAN"


def test_planner_fails_open_on_empty_runtime(tmp_path):
    plan = assemble_plan(tmp_path)
    assert plan["items"] == []
    assert plan["closed_loops_active"]
