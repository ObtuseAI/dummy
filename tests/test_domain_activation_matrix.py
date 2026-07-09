from __future__ import annotations


def test_domain_activation_matrix_reports_real_fixture_and_blocked_counts() -> None:
    from predator_mesh.v19.scoreboard import DomainScoreboardV2

    report = DomainScoreboardV2().activation_matrix_report()
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert "real_evidence_count" in report
    assert "fixture_evidence_count" in report
    assert "blocked_source_count" in report
