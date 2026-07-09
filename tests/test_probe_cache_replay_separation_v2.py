from __future__ import annotations

from predator_mesh.v32.recovery import ProbeCacheReplaySeparationV2, build_default_v32_state
from tests.v32_test_helpers import assert_current_test_report


def test_probe_cache_replay_separation_prevents_cache_or_replay_live_scoring() -> None:
    result = ProbeCacheReplaySeparationV2().audit(build_default_v32_state(enable_network=False))

    assert result.probe_cache_replay_separation_status == "PASS"
    assert result.fixture_scored_live is False
    assert result.replay_scored_live is False
    assert result.stale_cached_evidence_scored_live is False
    assert result.execution_bridge_present is False


def test_probe_cache_replay_separation_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["probe_cache_replay_separation_status"] == "PASS"
    assert report["fixture_scored_live"] is False
