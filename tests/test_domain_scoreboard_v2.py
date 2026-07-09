from __future__ import annotations

from v19_test_helpers import DOMAINS


def test_domain_scoreboard_v2_contains_activation_matrix_fields() -> None:
    from predator_mesh.v19.scoreboard import DomainScoreboardV2

    report = DomainScoreboardV2().to_report()
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert set(report["domains"]) == DOMAINS
    assert all("source_activation_mode" in item for item in report["scores"])
