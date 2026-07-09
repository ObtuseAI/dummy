from __future__ import annotations

from predator_mesh.v14.retry_gate import RealTerrainReadinessState, RealTerrainRetryGate
from tests.v14_test_helpers import fake_invalid_forensics_report


def test_real_terrain_readiness_state_reports_invalid_credential_blocker() -> None:
    state = RealTerrainRetryGate(forensics_report=fake_invalid_forensics_report()).readiness_state()

    assert state.state is RealTerrainReadinessState.BLOCKED_CREDENTIALS_INVALID
    assert state.real_terrain_ready is False
    assert state.to_report()["verdict"] == "PARTIAL"
