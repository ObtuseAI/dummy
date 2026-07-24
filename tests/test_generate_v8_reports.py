import json
from unittest.mock import MagicMock

import pytest

from archive.report_scripts.generate_v8_reports import main


@pytest.mark.asyncio
async def test_v8_orchestrator_writes_artifacts(tmp_path, monkeypatch, isolated_report_artifacts):
    """The V8 orchestrator writes the required summary reports.

    The real full-suite pytest must never run from inside a unit test.  We
    disable it explicitly and also inject a fake ``run_pytest_summary`` as
    defense in depth.
    """
    # Patch artifact directory so the orchestrator writes into a temp location.
    # isolated_report_artifacts also redirects the sub-generators the
    # orchestrator imports inside main(); patching only the orchestrator left
    # them writing into the REAL artifacts/dummy governance tree.
    import archive.report_scripts.generate_v8_reports as orchestrator

    artifacts = isolated_report_artifacts
    monkeypatch.setattr(orchestrator, "ARTIFACTS", artifacts)
    # Unit tests must never reach a live market endpoint merely because the
    # operator shell happens to contain credentials.
    for name in (
        "KALSHI_API_KEY_ID",
        "KALSHI_API_PRIVATE_KEY_PEM",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH",
        "KALSHI_API_PRIVATE_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    # Guarantee the orchestrator cannot recursively invoke pytest inside pytest.
    fake_run_pytest = MagicMock(
        return_value={
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "pytest_returncode": 0,
            "note": "pytest skipped by unit-test mock",
        }
    )
    monkeypatch.setattr(orchestrator, "run_pytest_summary", fake_run_pytest)

    result = await main(run_tests=False)

    assert result["verdict"] in ("PASS", "PARTIAL", "FAIL")
    assert "tests_summary" in result
    assert "report_verdicts" in result
    assert (artifacts / "tests_summary.json").exists()
    assert (artifacts / "final_report.json").exists()

    tests_summary = json.loads((artifacts / "tests_summary.json").read_text())
    assert tests_summary["failed"] == 0
    assert tests_summary["pytest_returncode"] == 0
    assert tests_summary.get("note", "").startswith("pytest skipped")

    final_report = json.loads((artifacts / "final_report.json").read_text())
    assert final_report["milestone"] == "DUMMY_V8_MODEL_ROUTING_FIREWALL_GOVERNOR_REHEARSAL_V1"
    assert "live_model_credentials_present" in final_report
    assert "kalshi_credentials_present" in final_report
    assert "dashboard_built" in final_report
