"""Wave-20: tuner auto-promote overrides + the improvement planner.

Wave-84 (2026-07-24 audit P1 item 11) adds the planner's own closed loop:
persisted plan history, a plan-vs-outcome diff with stable fingerprints,
explicit auto-closure of items whose evidence cleared, and dead measurement
loops (crashed report writers / failed chain steps) surfaced at top severity.
"""
from __future__ import annotations

import json

from autonomy.improvement_planner import (
    HISTORY_NAME,
    HISTORY_ROW_KEY,
    TOP_SEVERITY,
    append_history_row,
    assemble_plan,
    item_fingerprint,
    read_last_history_row,
    write_plan,
)
from autonomy.tuned_params import (
    CONSUMED_PARAMS,
    load_overrides,
    promote_from_report,
    value_in_force,
)


def _report(name="wnba_total_sigma", verdict="candidate", current=13.0, best=16.0):
    # "test_ci95" (a [lower, upper] list) is the key and shape the REAL tuner
    # writes on every proposal (autonomy/tuner.py::_fit_tunable) -- this
    # fixture previously used "test_delta_ci", masking a reader-side mismatch.
    return {"proposals": [{
        "name": name, "verdict": verdict, "current": current, "best": best,
        "test_delta": 0.004, "test_ci95": [0.001, 0.007],
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


def test_ci_key_contract_tuner_writer_to_promotion_reader(tmp_path):
    # Audit P1 item 9 (2026-07-24): the tuner writes "test_ci95" but the
    # promotion evidence snapshot read "test_delta_ci", so every override
    # ever applied logged a null CI. Pin the shared key on BOTH sides.
    from autonomy.tuner import _SPECS, _fit_tunable

    # Writer side: the real tuner emits "test_ci95" on every proposal, even
    # the insufficient-data base shape.
    base = _fit_tunable(_SPECS[0], [])
    assert "test_ci95" in base
    assert "test_delta_ci" not in base

    # Reader side: the applied override snapshots that SAME key, non-null.
    path = tmp_path / "tuned_params.json"
    outcome = promote_from_report(
        _report(), now_iso="2026-07-24T00:00:00+00:00", path=path,
        log_path=tmp_path / "log.jsonl")
    assert len(outcome["applied"]) == 1
    evidence = json.loads(path.read_text(encoding="utf-8"))[
        "overrides"]["wnba_total_sigma"]["evidence"]
    assert evidence["test_ci95"] == [0.001, 0.007]
    assert evidence["test_delta"] == 0.004
    assert evidence["n_clusters"] == 220


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


# ---------------------------------------------------------------------------
# Wave-84: plan history, the plan-vs-outcome diff, and auto-closure
# ---------------------------------------------------------------------------

def _bleeder(scope, edge=-0.02):
    return {"scope": scope, "verdict": "bleeding", "cluster_edge": edge,
            "n_clusters": 40}


def _write_loss(rd, *scopes):
    (rd / "loss_attribution.json").write_text(
        json.dumps({"scopes": list(scopes)}), encoding="utf-8")


def _run(rd):
    """One planner run: assemble + write, exactly as the nightly chain does."""
    plan = assemble_plan(rd)
    write_plan(plan, rd / "self_improvement_plan.json")
    return plan


def test_first_run_creates_history_and_stamps_identity(tmp_path):
    _write_loss(tmp_path, _bleeder("s_one"), _bleeder("s_two", -0.03))

    plan = _run(tmp_path)

    history_file = tmp_path / HISTORY_NAME
    assert history_file.exists()
    rows = history_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1
    row = json.loads(rows[0])
    assert row["run_index"] == 1
    assert row["item_count"] == 2
    assert set(row["tracked"]) == {item["fingerprint"] for item in plan["items"]}

    history = plan["history"]
    assert history["first_run"] is True
    assert history["previous_run_id"] is None
    assert history["counts"] == {"total": 2, "new": 2, "resolved": 0,
                                 "persisting": 0}
    for item in plan["items"]:
        assert item["status"] == "new"
        assert item["first_seen_at"] == plan["generated_at"]
        assert item["runs_seen"] == 1
        assert item["fingerprint"] == item_fingerprint(item)

    # The out-of-band transport key never reaches the artifact.
    written = json.loads(
        (tmp_path / "self_improvement_plan.json").read_text(encoding="utf-8"))
    assert HISTORY_ROW_KEY not in written
    assert written["schema_version"] == 2
    assert written["history"]["run_index"] == 1


def test_vanished_item_is_auto_closed_and_survivor_carries_first_seen(tmp_path):
    _write_loss(tmp_path, _bleeder("s_gone"), _bleeder("s_stays", -0.03))
    first = _run(tmp_path)
    first_run_id = first["generated_at"]
    gone_fp = next(item["fingerprint"] for item in first["items"]
                   if item["target"] == "s_gone")

    # Its evidence cleared: the loss engine no longer calls s_gone bleeding.
    _write_loss(tmp_path, _bleeder("s_stays", -0.03))
    second = _run(tmp_path)

    history = second["history"]
    assert history["run_index"] == 2
    assert history["first_run"] is False
    assert history["previous_run_id"] == first_run_id
    assert history["counts"] == {"total": 1, "new": 0, "resolved": 1,
                                 "persisting": 1}

    # 3) Auto-closure: recorded EXPLICITLY, with the run it resolved in --
    # not silently vanished the way the audit found.
    [resolved] = history["resolved_items"]
    assert resolved["fingerprint"] == gone_fp
    assert resolved["target"] == "s_gone"
    assert resolved["first_seen_at"] == first_run_id
    assert resolved["resolved_in_run"] == second["generated_at"]
    assert resolved["last_seen_at"] == first_run_id

    # 2) The survivor ages instead of looking brand new every night.
    [persisting] = history["persisting_items"]
    assert persisting["target"] == "s_stays"
    assert persisting["first_seen_at"] == first_run_id
    assert persisting["runs_seen"] == 2
    survivor = next(item for item in second["items"]
                    if item["target"] == "s_stays")
    assert survivor["status"] == "persisting"
    assert survivor["first_seen_at"] == first_run_id
    assert survivor["runs_seen"] == 2

    # The resolution is on the audit tape too, not only in the live plan.
    row = read_last_history_row(tmp_path / HISTORY_NAME)
    assert [entry["target"] for entry in row["resolved_items"]] == ["s_gone"]
    assert gone_fp not in row["tracked"]

    # A third run with the same evidence must not re-resolve it.
    third = _run(tmp_path)
    assert third["history"]["resolved_items"] == []
    assert third["history"]["counts"]["persisting"] == 1


def test_fingerprint_is_stable_across_severity_and_prose_churn(tmp_path):
    _write_loss(tmp_path, _bleeder("s_one", -0.02))
    first = _run(tmp_path)
    before = first["items"][0]["fingerprint"]

    # Same finding, different numbers: identity must not move.
    _write_loss(tmp_path, _bleeder("s_one", -0.44))
    second = _run(tmp_path)
    item = second["items"][0]
    assert item["fingerprint"] == before
    assert item["severity"] != first["items"][0]["severity"]
    assert item["status"] == "persisting"
    assert second["history"]["counts"]["new"] == 0
    assert second["history"]["resolved_items"] == []


def test_diff_covers_items_beyond_the_hundred_item_display_cut(tmp_path):
    _write_loss(tmp_path, *[_bleeder(f"s_{i:03d}", -0.01 - i / 1000)
                            for i in range(120)])
    plan = _run(tmp_path)
    # The artifact still shows the top 100 -- but the diff (and the history
    # row) covers all 120, so item 101 is never "resolved" by truncation.
    assert len(plan["items"]) == 100
    assert plan["items_total"] == 120
    assert plan["history"]["counts"]["total"] == 120
    assert len(read_last_history_row(tmp_path / HISTORY_NAME)["tracked"]) == 120

    second = _run(tmp_path)
    assert second["history"]["counts"] == {"total": 120, "new": 0,
                                           "resolved": 0, "persisting": 120}


# ---------------------------------------------------------------------------
# Wave-84: a dead measurement loop outranks every ordinary finding
# ---------------------------------------------------------------------------

def test_writer_failure_is_a_top_severity_item(tmp_path):
    _write_loss(tmp_path, _bleeder("s_bleed"))
    # Even the fabricated-benchmark alarm (severity 10.0) ranks below it.
    (tmp_path / "negative_control_report.json").write_text(
        json.dumps({"flagged_sources": ["bad_source"]}), encoding="utf-8")
    (tmp_path / "report_writer_failures.json").write_text(json.dumps({
        "generated_at": "2026-07-24T09:30:00+00:00",
        "ok_writers": ["picks"],
        "failures": [{
            "writer": "film_room",
            "error": "OperationalError('database is locked')",
            "at": "2026-07-24T09:31:00+00:00",
            "traceback": ["one", "two", "three", "four"],
        }],
    }), encoding="utf-8")

    plan = assemble_plan(tmp_path)

    top = plan["items"][0]
    assert top["kind"] == "report_writer_dead"
    assert top["target"] == "film_room"
    assert top["severity"] == TOP_SEVERITY == 100.0
    assert top["severity"] > plan["items"][1]["severity"]
    assert plan["items"][1]["kind"] == "negative_control_flag"
    assert "database is locked" in top["evidence"]["error"]
    assert top["evidence"]["traceback_tail"] == ["two", "three", "four"]
    assert top["owner"] == "operator"

    health = plan["measurement_health"]
    assert health["measurement_trusted"] is False
    assert health["failed_writers"] == ["film_room"]
    assert health["writer_failures_artifact_present"] is True
    # The declared closed-loop roster no longer reads as verified truth.
    assert plan["closed_loops_active"][0].startswith("!! MEASUREMENT DEGRADED")
    assert "film_room" in plan["closed_loops_active"][0]


def test_healthy_writer_artifact_produces_no_measurement_items(tmp_path):
    (tmp_path / "report_writer_failures.json").write_text(json.dumps({
        "generated_at": "2026-07-24T09:30:00+00:00",
        "failures": [], "ok_writers": ["picks", "film_room"],
    }), encoding="utf-8")
    plan = assemble_plan(tmp_path)
    assert plan["items"] == []
    assert plan["measurement_health"]["measurement_trusted"] is True
    assert plan["measurement_health"]["dead_loops"] == []
    assert not plan["closed_loops_active"][0].startswith("!!")


def test_chain_step_failure_is_top_severity_from_live_status(tmp_path):
    _write_loss(tmp_path, _bleeder("s_bleed"))
    chain = {
        "ran_at": "2026-07-24T09:00:00+00:00",
        "ok": False,
        "failed_steps": ["tuner"],
        "steps": {
            "loss_engine": {"exit": 0, "status": "OK", "last_line": "{}"},
            "tuner": {"exit": 1, "status": "FAILED", "stderr_last": "boom"},
        },
    }

    plan = assemble_plan(tmp_path, chain=chain)

    top = plan["items"][0]
    assert top["kind"] == "chain_step_dead"
    assert top["target"] == "tuner"
    assert top["severity"] == TOP_SEVERITY
    assert top["evidence"]["exit"] == 1
    assert top["evidence"]["stderr_last"] == "boom"
    assert top["evidence"]["status_source"] == "live"
    assert plan["measurement_health"]["failed_chain_steps"] == ["tuner"]
    assert plan["measurement_health"]["chain_ok"] is False
    assert plan["measurement_health"]["chain_status_source"] == "live"
    # The healthy step is not an item.
    assert [item["target"] for item in plan["items"]
            if item["kind"] == "chain_step_dead"] == ["tuner"]


def test_chain_step_failure_read_from_the_plan_artifact_on_disk(tmp_path):
    # The nightly chain attaches its per-step status to the plan artifact
    # AFTER assembling it, so on disk the freshest status is the last run's.
    (tmp_path / "self_improvement_plan.json").write_text(json.dumps({
        "chain": {"ran_at": "2026-07-23T09:00:00+00:00", "ok": False,
                  "failed_steps": ["loss_engine"],
                  "steps": {"loss_engine": {"exit": 1, "status": "FAILED"}}},
    }), encoding="utf-8")

    plan = assemble_plan(tmp_path)

    top = plan["items"][0]
    assert top["kind"] == "chain_step_dead"
    assert top["target"] == "loss_engine"
    assert top["evidence"]["status_source"] == "previous_run"
    assert top["evidence"]["chain_ran_at"] == "2026-07-23T09:00:00+00:00"
    assert "LAST recorded chain run" in top["next"]


def test_chain_outcome_is_recorded_on_the_history_row(tmp_path):
    _write_loss(tmp_path, _bleeder("s_bleed"))
    plan = assemble_plan(tmp_path)
    plan["chain"] = {"ran_at": "t", "ok": False, "failed_steps": ["tuner"],
                     "steps": {"tuner": {"exit": 1, "status": "FAILED"}}}
    write_plan(plan, tmp_path / "self_improvement_plan.json")

    row = read_last_history_row(tmp_path / HISTORY_NAME)
    assert row["chain_ok"] is False
    assert row["chain_failed_steps"] == ["tuner"]


# ---------------------------------------------------------------------------
# Wave-84: fail-soft everywhere, and the tape stays bounded
# ---------------------------------------------------------------------------

def test_corrupt_and_missing_artifacts_degrade_gracefully(tmp_path):
    (tmp_path / "report_writer_failures.json").write_text(
        "{not json at all", encoding="utf-8")
    (tmp_path / "self_improvement_plan.json").write_text(
        "\x00garbage", encoding="utf-8")
    (tmp_path / "loss_attribution.json").write_text(
        json.dumps({"scopes": "not-a-list"}), encoding="utf-8")
    (tmp_path / HISTORY_NAME).write_text(
        "not json\n{\"broken\": \n", encoding="utf-8")

    plan = assemble_plan(tmp_path)

    assert plan["report_name"] == "SELF_IMPROVEMENT_PLAN"
    assert plan["history"]["run_index"] == 1
    assert plan["history"]["first_run"] is True
    assert plan["measurement_health"]["measurement_trusted"] is True
    assert write_plan(plan, tmp_path / "self_improvement_plan.json").exists()


def test_corrupt_trailing_line_never_blinds_the_diff(tmp_path):
    _write_loss(tmp_path, _bleeder("s_stays"))
    first = _run(tmp_path)
    # A crash mid-append leaves a partial row; the reader must walk back past
    # it to the last good snapshot instead of restarting history.
    with (tmp_path / HISTORY_NAME).open("a", encoding="utf-8") as handle:
        handle.write('{"run_id": "partial", "trac\n')

    second = _run(tmp_path)

    assert second["history"]["run_index"] == 2
    assert second["history"]["first_run"] is False
    assert second["items"][0]["first_seen_at"] == first["generated_at"]
    assert second["items"][0]["runs_seen"] == 2


def test_shaped_but_wrong_history_row_does_not_crash(tmp_path):
    _write_loss(tmp_path, _bleeder("s_stays"))
    (tmp_path / HISTORY_NAME).write_text(json.dumps({
        "run_index": "not-a-number", "tracked": ["not", "a", "dict"],
    }) + "\n", encoding="utf-8")

    plan = assemble_plan(tmp_path)

    assert plan["history"]["run_index"] == 1
    assert plan["items"][0]["runs_seen"] == 1


def test_history_tape_is_line_capped_and_tail_preserved(tmp_path, monkeypatch):
    monkeypatch.setenv("DUMMY_PLAN_HISTORY_KEEP_ROWS", "2")
    path = tmp_path / HISTORY_NAME
    for index in range(6):
        append_history_row({"run_index": index, "tracked": {}}, path)

    rows = [json.loads(line) for line in
            path.read_text(encoding="utf-8").strip().splitlines()]
    # Cap 2 with 1.5x hysteresis: never more than 3 rows, newest always kept.
    assert len(rows) <= 3
    assert rows[-1]["run_index"] == 5
    assert read_last_history_row(path)["run_index"] == 5


def test_append_history_row_is_fail_soft(tmp_path):
    assert append_history_row(None, tmp_path / HISTORY_NAME) is None
    assert append_history_row("not-a-row", tmp_path / HISTORY_NAME) is None
    assert not (tmp_path / HISTORY_NAME).exists()
    # An unserializable row costs the tape one line, never an exception.
    assert append_history_row({"bad": object()}, tmp_path / HISTORY_NAME) is None
