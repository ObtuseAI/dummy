from __future__ import annotations

from predator_mesh.v10.build_factory import BuildEdgeFactory, BuildPacketPromotionDecision


def test_build_packet_promotion_requires_tests_and_reports() -> None:
    factory = BuildEdgeFactory()
    packet = factory.generate_packets()[0]

    blocked = factory.evaluate_promotion(packet, tests_passed=False, reports_written=True)
    promoted = factory.evaluate_promotion(packet, tests_passed=True, reports_written=True)

    assert blocked.decision == "REQUIRE_TESTS"
    assert promoted.decision == "PROMOTE"
    assert isinstance(promoted, BuildPacketPromotionDecision)


def test_build_packet_promotion_report() -> None:
    report = BuildEdgeFactory().promotion_report()
    assert report["verdict"] == "PASS"
    assert report["decisions"]
    assert all(d["decision"] in {"PROMOTE", "REQUIRE_TESTS", "REQUIRE_REPORTS"} for d in report["decisions"])
