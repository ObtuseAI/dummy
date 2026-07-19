"""Wave-33: self-heal / reconnect loop -- pure decision logic with injected
probes and task control."""
from __future__ import annotations

from autonomy.healer import assess, check_connectivity, plan_heals


def test_plan_heals_restarts_only_dead_persistent_tasks():
    states = {
        "DummyDashboard": "Ready",         # the persistent server is down -> restart
        "DummyLivePoller": "Ready",        # fire-and-exit, Ready is healthy -> ignore
        "DummyCryptoPaperTwin": "Ready",   # fire-and-exit -> ignore
    }
    assert plan_heals(states) == ["DummyDashboard"]
    assert plan_heals({"DummyDashboard": "Running"}) == []   # alive -> leave


def test_plan_heals_never_touches_disabled_or_absent():
    assert plan_heals({"DummyDashboard": "Disabled"}) == []  # operator-disabled stays down
    assert plan_heals({}) == []                              # absent tasks left alone
    # A custom persistent set still follows the same rule.
    assert plan_heals({"X": "Ready", "Y": "Running"}, persistent=("X", "Y")) == ["X"]


def test_check_connectivity_reports_reachable_split():
    def probe(host, port, timeout):
        return host.startswith("api.the-odds")   # only one venue up
    ok, up, down = check_connectivity(probe=probe)
    assert ok and up == ["api.the-odds-api.com"] and len(down) == 2


def test_check_connectivity_all_down_is_outage():
    ok, up, down = check_connectivity(probe=lambda *a: False)
    assert not ok and up == [] and len(down) == 3


def test_assess_restarts_dead_task_and_records_outage():
    restarted = []
    report = assess(
        now_iso="2026-07-19T00:00:00+00:00",
        query_states=lambda: {"DummyDashboard": "Ready", "DummyCryptoPaperTwin": "Running"},
        restart=lambda name: restarted.append(name) or True,
        probe=lambda *a: False,            # internet down
    )
    assert report.connectivity_ok is False
    assert report.restarted == ["DummyDashboard"] and restarted == ["DummyDashboard"]
    assert report.errors == []


def test_assess_fail_open_on_query_error():
    def boom():
        raise OSError("scheduler unavailable")
    report = assess(
        now_iso="2026-07-19T00:00:00+00:00",
        query_states=boom, restart=lambda n: True, probe=lambda *a: True)
    assert report.connectivity_ok is True          # probe still ran
    assert any(e.startswith("query:") for e in report.errors)
    assert report.restarted == []                  # degraded, never raised


def test_assess_records_restart_failure():
    report = assess(
        now_iso="2026-07-19T00:00:00+00:00",
        query_states=lambda: {"DummyDashboard": "Ready"},
        restart=lambda name: False,        # restart didn't take
        probe=lambda *a: True)
    assert report.restarted == [] and any("restart_failed" in e for e in report.errors)
