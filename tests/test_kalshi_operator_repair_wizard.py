from __future__ import annotations

import json

from predator_mesh.v14.repair_wizard import KalshiOperatorRepairWizard


def test_kalshi_operator_repair_wizard_reports_safe_steps_without_secrets() -> None:
    report = KalshiOperatorRepairWizard().to_report()
    text = json.dumps(report)

    assert report["verdict"] in {"PASS", "OPERATOR_ACTION_REQUIRED"}
    assert report["selected_source"] in {"process_env", "dummy_env_file", "local_secret_file_reference", "missing"}
    assert report["validation_commands"]
    assert "Get-Content" not in text
    assert "BEGIN PRIVATE KEY" not in text
