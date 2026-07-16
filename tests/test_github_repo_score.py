from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_github_repo_score_uses_security_and_legal_dimensions() -> None:
    report = assert_v20_report("github_repo_score_report_v1.json", "scores")
    first = report["scores"][0]["score"]
    assert "terms_legal_clarity" in first
    assert "security_risk" in first
