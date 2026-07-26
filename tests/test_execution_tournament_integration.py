"""Integration of the execution tournament into the backtest, alerts, dashboard.

The tournament is an evaluation layer that rides the existing backtest pipeline
(no new schtask): ``run_backtest`` must carry the per-cohort report, the
authoritative summary must carry the compact view, the alert union must gate a
challenger cohort on the rising edge, and the dashboard status panel must expose
the compact tournament view.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import autonomy.alerts as alerts
from autonomy.backtest import run_backtest, summarize_backtest

_SPEC = importlib.util.spec_from_file_location(
    "_tournament_fixture",
    Path(__file__).with_name("test_execution_tournament.py"),
)
_FIXTURE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_FIXTURE)


def _wire_alert_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(alerts, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(alerts, "ALERTS_LOG", tmp_path / "alerts.jsonl")
    monkeypatch.setattr(alerts, "ALERTS_LATEST", tmp_path / "alerts_latest.json")
    monkeypatch.setattr(alerts, "ALERT_STATE", tmp_path / "alert_state.json")


def test_run_backtest_carries_tournament(tmp_path):
    ledger = _FIXTURE._tournament_ledger(tmp_path)
    try:
        report = run_backtest(ledger)
    finally:
        ledger.close()
    tournament = report["execution_tournament"]
    assert tournament["report_name"] == "EXECUTION_POLICY_TOURNAMENT"
    assert [c["policy"]["cohort"] for c in tournament["cohorts"]] == [
        "C0", "C1", "C2", "C3", "C4",
    ]


def test_summary_carries_compact_tournament(tmp_path):
    ledger = _FIXTURE._tournament_ledger(tmp_path)
    try:
        summary = summarize_backtest(run_backtest(ledger))
    finally:
        ledger.close()
    compact = summary["execution_tournament"]
    assert compact["report_name"] == "EXECUTION_POLICY_TOURNAMENT"
    assert len(compact["ranking"]) == 5
    assert compact["policy_switch_authority"]["auto_switch"] is False
    assert compact["headline"]["evidence_sufficient_for_promotion_review"] is False
    modeled = {
        row["cohort"]: row
        for row in compact["ranking"]
        if row["cohort"] in {"C1", "C2", "C4"}
    }
    assert all(
        row["evidence_class"] == "modeled_counterfactual"
        and row["counts_toward_promotion_readiness"] is False
        for row in modeled.values()
    )


def test_summary_tournament_empty_when_absent():
    # A report with no tournament section yields an empty compact view, not a crash.
    assert summarize_backtest({"report_name": "X"})["execution_tournament"] == {}


def test_modeled_or_unwitnessed_tournament_lanes_cannot_fire_promotion_alert(
    monkeypatch, tmp_path,
):
    _wire_alert_paths(monkeypatch, tmp_path)
    summary = {
        "ranking": [
            {
                "cohort": "C1",
                "gate_met": True,
                "evidence_class": "modeled_counterfactual",
                "promotion_review_eligible": False,
                "counts_toward_promotion_readiness": False,
                "counts_toward_policy_switch": False,
                "witnessed_broker_fill_backing": False,
            },
            {
                "cohort": "C3",
                "gate_met": True,
                "evidence_class": "observed_fill_censoring_counterfactual",
                "promotion_review_eligible": False,
                "counts_toward_promotion_readiness": False,
                "counts_toward_policy_switch": False,
                "witnessed_broker_fill_backing": False,
            },
        ],
        "headline": {"leading_cohort": None},
    }
    cycle = {"status": "OK"}
    fired = alerts.evaluate_alerts(cycle, None, False, tournament_summary=summary)
    assert "EXECUTION_TOURNAMENT_GATE" not in [a["kind"] for a in fired]


def test_witnessed_explicitly_eligible_lane_alerts_once(monkeypatch, tmp_path):
    _wire_alert_paths(monkeypatch, tmp_path)
    summary = {
        "ranking": [{
            "cohort": "FUTURE_WITNESSED_LANE",
            "gate_met": True,
            "evidence_class": "witnessed_broker_fill_campaign",
            "promotion_review_eligible": True,
            "counts_toward_promotion_readiness": True,
            "counts_toward_policy_switch": False,
            "witnessed_broker_fill_backing": True,
        }],
        "headline": {"leading_cohort": "FUTURE_WITNESSED_LANE"},
    }
    cycle = {"status": "OK"}
    fired = alerts.evaluate_alerts(cycle, None, False, tournament_summary=summary)
    gate = next(a for a in fired if a["kind"] == "EXECUTION_TOURNAMENT_GATE")
    assert gate["detail"]["newly_gated_cohorts"] == ["FUTURE_WITNESSED_LANE"]
    assert gate["severity"] == "info"
    # Standing eligibility does not re-fire.
    again = alerts.evaluate_alerts(cycle, None, False, tournament_summary=summary)
    assert "EXECUTION_TOURNAMENT_GATE" not in [a["kind"] for a in again]


def test_tournament_gate_alert_absent_without_summary(monkeypatch, tmp_path):
    _wire_alert_paths(monkeypatch, tmp_path)
    fired = alerts.evaluate_alerts({"status": "OK"}, None, False)
    assert "EXECUTION_TOURNAMENT_GATE" not in [a["kind"] for a in fired]


def test_dashboard_status_panel_exposes_tournament(tmp_path):
    from autonomy import dashboard
    from autonomy.execution_tournament import tournament_report, write_report

    ledger = _FIXTURE._tournament_ledger(tmp_path)
    try:
        report = tournament_report(ledger._conn)
    finally:
        ledger.close()
    runtime = tmp_path / "runtime"
    # The autouse isolated risk-state fixture may already have created this
    # directory; the tournament artifact writer shares the same runtime root.
    runtime.mkdir(exist_ok=True)
    write_report(report, runtime / "execution_tournament.json")
    snapshot = dashboard.assemble_status_snapshot(runtime_dir=runtime)
    panel = snapshot["execution_tournament"]
    assert panel["report_name"] == "EXECUTION_POLICY_TOURNAMENT"
    assert len(panel["ranking"]) == 5
    assert panel["headline"]["evidence_sufficient_for_promotion_review"] is False
    c1 = next(row for row in panel["ranking"] if row["cohort"] == "C1")
    assert c1["evidence_class"] == "modeled_counterfactual"
    assert c1["counts_toward_promotion_readiness"] is False
    assert "execution_tournament" in snapshot["data_ages"]
