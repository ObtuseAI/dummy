from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from archive.report_scripts.generate_v8_reports import main as orchestrator_main


@pytest.mark.asyncio
async def test_orchestrator_unit_test_does_not_invoke_subprocess_pytest(tmp_path, monkeypatch, isolated_report_artifacts):
    """The orchestrator unit test must never run a recursive pytest subprocess."""
    import archive.report_scripts.generate_v8_reports as orchestrator

    # isolated_report_artifacts also redirects the sub-generators the
    # orchestrator imports inside main(); patching only the orchestrator left
    # them writing into the REAL artifacts/dummy governance tree.
    artifacts = isolated_report_artifacts
    monkeypatch.setattr(orchestrator, "ARTIFACTS", artifacts)
    monkeypatch.setattr(orchestrator, "run_pytest_summary", MagicMock(
        return_value={
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "pytest_returncode": 0,
            "note": "pytest skipped by unit-test mock",
        }
    ))

    with patch("subprocess.run") as subprocess_run_mock:
        result = await orchestrator_main(run_tests=False)

    subprocess_run_mock.assert_not_called()
    assert result["tests_summary"]["note"].startswith("pytest skipped")
    assert (artifacts / "tests_summary.json").exists()
    assert (artifacts / "final_report.json").exists()


@pytest.mark.asyncio
async def test_orchestrator_run_pytest_summary_uses_subprocess_when_enabled(tmp_path, monkeypatch):
    """``run_pytest_summary`` is allowed to invoke pytest only when explicitly enabled."""
    import archive.report_scripts.generate_v8_reports as orchestrator

    class _FakeProc:
        returncode = 0
        stdout = "3 passed"
        stderr = ""

    with patch("subprocess.run", return_value=_FakeProc()) as subprocess_run_mock:
        summary = orchestrator.run_pytest_summary()

    subprocess_run_mock.assert_called_once()
    assert summary["pytest_returncode"] == 0
    assert summary["passed"] == 3
