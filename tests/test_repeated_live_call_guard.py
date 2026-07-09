from __future__ import annotations


def test_repeated_live_call_guard_blocks_dashboard_live_retries() -> None:
    from predator_mesh.v19.runtime import RepeatedLiveCallGuard

    report = RepeatedLiveCallGuard().to_report()
    assert report["verdict"] == "PASS"
    assert report["dashboard_repeated_live_calls"] is False
