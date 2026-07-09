from __future__ import annotations

from predator_mesh.v10.build_factory import BuildEdgeFactory
from predator_mesh.v10.queue import BuildAccelerationQueue, QueueDispatchDecision


def test_build_acceleration_queue_dispatches_high_value_packet() -> None:
    queue = BuildAccelerationQueue()
    packet = BuildEdgeFactory().generate_packets()[0]
    item = queue.enqueue(packet)
    decision = queue.dispatch(item)

    assert decision.decision in {"DISPATCH_NOW", "DEFER", "REQUIRE_MORE_EVIDENCE"}
    assert isinstance(decision, QueueDispatchDecision)
    assert item.score.total > 0


def test_queue_report_contains_backpressure_and_staleness() -> None:
    queue = BuildAccelerationQueue()
    for packet in BuildEdgeFactory().generate_packets():
        queue.enqueue(packet)
    report = queue.to_report()
    assert report["verdict"] == "PASS"
    assert report["item_count"] > 0
    assert "backpressure" in report
    assert "staleness" in report
