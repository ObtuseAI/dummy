from __future__ import annotations

from predator_mesh.v33.run import SportsProbeExclusionGuardV4, build_default_v33_state
from tests.v33_test_helpers import assert_current_test_report


def test_sports_probe_exclusion_guard_keeps_sports_fixture_only() -> None:
    guard = SportsProbeExclusionGuardV4().evaluate(build_default_v33_state(enable_network=False))

    assert guard.sports_probe_exclusion_guard_status == "PASS"
    assert guard.sports_source_mode == "FIXTURE_REPLAY_ONLY"
    assert guard.sports_probe_included is False
    assert guard.wagering_activation_allowed is False
    assert guard.execution_bridge_present is False


def test_sports_probe_exclusion_guard_report_contract() -> None:
    report = assert_current_test_report(__file__)

    assert report["sports_probe_exclusion_guard_status"] == "PASS"
    assert report["sports_source_mode"] == "FIXTURE_REPLAY_ONLY"
