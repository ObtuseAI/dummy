from __future__ import annotations

import json

from predator_mesh.v13.credential_bridge import KalshiReadOnlyCredentialBridge
from predator_mesh.v13.repair_packet import KalshiReadOnlyOperatorRepairPacket


def test_kalshi_readonly_operator_repair_packet_is_redacted_and_actionable(tmp_path) -> None:
    bridge = KalshiReadOnlyCredentialBridge(
        env={},
        dummy_env_path=tmp_path / "missing_dummy.env",
        project_env_path=tmp_path / "missing_project.env",
    )
    packet = KalshiReadOnlyOperatorRepairPacket(credential_bridge=bridge).to_report()
    text = json.dumps(packet)

    assert packet["verdict"] == "OPERATOR_ACTION_REQUIRED"
    assert packet["credential_status"]["ready"] is False
    assert packet["repair_steps"]
    assert "BEGIN PRIVATE KEY" not in text
