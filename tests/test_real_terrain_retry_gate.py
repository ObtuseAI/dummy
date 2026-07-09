from __future__ import annotations

from predator_mesh.v14.retry_gate import RealTerrainRetryDecision, RealTerrainRetryGate
from tests.v14_test_helpers import fake_invalid_forensics_report


def test_real_terrain_retry_gate_blocks_invalid_credentials_without_spamming_endpoints() -> None:
    report = RealTerrainRetryGate(forensics_report=fake_invalid_forensics_report()).to_report()

    assert report["decision"] == RealTerrainRetryDecision.BLOCKED_CREDENTIALS_INVALID.value
    assert report["retry_count"] == 0
    assert report["write_endpoints_called"] == []
    assert report["verdict"] == "PARTIAL"
