from __future__ import annotations

from predator_mesh.v14.micro_order_dry_run import MicroOrderDryRunPacketV2
from tests.v14_test_helpers import fake_invalid_forensics_report


def test_micro_order_dry_run_packet_v2_is_rehearsal_only_when_credentials_invalid() -> None:
    report = MicroOrderDryRunPacketV2(forensics_report=fake_invalid_forensics_report()).to_report()

    assert report["would_submit"] is False
    assert report["limit_only"] is True
    assert report["tiny_size_only"] is True
    assert report["live_submit_enabled"] is False
    assert report["allowed_submit_path"] == "LiveBrokerFirewall.submit"
    assert "MARKET" in report["forbidden_order_types"]
    assert report["verdict"] == "PARTIAL"
