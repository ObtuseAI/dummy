from __future__ import annotations

from predator_mesh.v10.edge_accelerator import EdgeDiscoveryAccelerator


def test_edge_triage_decision_report_has_allowed_decisions() -> None:
    report = EdgeDiscoveryAccelerator().triage_report()
    allowed = {
        "ESCALATE_TO_FORECAST",
        "ESCALATE_TO_MINIMAX_REVIEW",
        "ESCALATE_TO_STRATEGY_GOVERNOR",
        "WATCH",
        "STARVE_SIGNAL",
        "QUARANTINE_SOURCE",
        "NO_TRADE",
    }
    assert report["verdict"] == "PASS"
    assert report["decisions"]
    assert {d["decision"] for d in report["decisions"]} <= allowed
