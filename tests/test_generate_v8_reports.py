import json
from unittest.mock import MagicMock

import pytest

from archive.report_scripts.generate_v8_reports import main


@pytest.mark.asyncio
async def test_v8_orchestrator_writes_artifacts(tmp_path, monkeypatch):
    """The V8 orchestrator writes the required summary reports.

    The real full-suite pytest must never run from inside a unit test.  We
    disable it explicitly and also inject a fake ``run_pytest_summary`` as
    defense in depth.
    """
    artifacts = tmp_path / "dummy"
    artifacts.mkdir(parents=True, exist_ok=True)

    # Patch artifact directory so the orchestrator writes into a temp location.
    import archive.report_scripts.generate_v8_reports as orchestrator

    monkeypatch.setattr(orchestrator, "ARTIFACTS", artifacts)

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
