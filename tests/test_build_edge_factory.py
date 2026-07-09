from __future__ import annotations

from predator_mesh.v10.build_factory import (
    BuildEdgeFactory,
    BuildPacketPriority,
    BuildPacketType,
)


def test_build_edge_factory_generates_bounded_packets() -> None:
    factory = BuildEdgeFactory()
    packets = factory.generate_packets()

    assert packets
    assert {p.packet_type for p in packets} >= {
        BuildPacketType.SOURCE_ADAPTER_CANDIDATE,
        BuildPacketType.TEST_COVERAGE_UPGRADE,
    }
    assert all(p.budget.timeout_s <= 30 for p in packets)
    assert all("configs/caps.json" in p.scope_limits.forbidden_paths for p in packets)
    assert all("configs/live_submit.json" in p.scope_limits.forbidden_paths for p in packets)
    assert all("core/inherited_blunder" in p.scope_limits.forbidden_paths for p in packets)
    assert all(p.priority in BuildPacketPriority for p in packets)


def test_build_edge_factory_report_shape() -> None:
    report = BuildEdgeFactory().to_report()
    assert report["verdict"] == "PASS"
    assert report["packet_count"] > 0
    assert report["live_submit_disabled_required"] is True
    assert report["caps_read_only_required"] is True
    assert report["no_direct_order_endpoint_required"] is True
