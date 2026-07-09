from __future__ import annotations

from predator_mesh.v10.build_factory import BuildEdgeFactory
from predator_mesh.v10.queue import BuildAccelerationQueue


def test_queue_priority_scores_penalize_duplicates_and_staleness() -> None:
    packet = BuildEdgeFactory().generate_packets()[0]
    queue = BuildAccelerationQueue()
    clean = queue.score_packet(packet)
    penalized = queue.score_packet(packet, duplicate=True, stale=True)

    assert clean.total > penalized.total
    assert penalized.duplicate_source_penalty > 0
    assert penalized.stale_source_penalty > 0


def test_build_queue_priority_report() -> None:
    queue = BuildAccelerationQueue()
    for packet in BuildEdgeFactory().generate_packets():
        queue.enqueue(packet)
    report = queue.priority_report()
    assert report["verdict"] == "PASS"
    assert report["scores"]
    assert all("total" in score for score in report["scores"])
