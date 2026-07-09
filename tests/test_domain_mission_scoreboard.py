from __future__ import annotations

from v18_test_helpers import DOMAINS, assert_pass_report


def test_domain_mission_scoreboard_shows_fixture_real_or_blocked_state_per_domain() -> None:
    from predator_mesh.v18.mission import DomainMissionScoreboard

    report = DomainMissionScoreboard().to_report()

    assert_pass_report(report)
    assert set(report["domains"]) == DOMAINS
    assert all(item["evidence_state"] in {"FIXTURE_STATIC", "REAL_READ_ONLY", "BLOCKED"} for item in report["scores"])
