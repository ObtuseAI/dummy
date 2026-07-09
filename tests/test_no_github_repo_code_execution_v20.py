from __future__ import annotations


def test_no_github_repo_code_execution_v20_report_passes() -> None:
    from scripts.generate_v20_reports import generate_no_github_repo_code_execution_report_v20

    report = generate_no_github_repo_code_execution_report_v20()

    assert report["verdict"] == "PASS"
    assert report["cloned_repos"] == []
    assert report["executed_repo_code"] is False

