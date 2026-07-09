from __future__ import annotations

from v18_test_helpers import assert_pass_report


def test_v18_research_packets_become_outcome_ledger_records() -> None:
    from predator_mesh.v18.integration import V18OutcomeLedgerIntegration

    report = V18OutcomeLedgerIntegration().to_report()

    assert_pass_report(report)
    assert report["research_packet_records"] == 5
    assert report["fabricated_outcomes"] is False
