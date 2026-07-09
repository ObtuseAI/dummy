"""Operator-facing credential repair packet for V14."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from predator_mesh.v14.credential_forensics import KalshiCredentialForensics


@dataclass(frozen=True)
class KalshiRepairStep:
    step_id: str
    title: str
    operator_action: str
    secret_safe: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "title": self.title,
            "operator_action": self.operator_action,
            "secret_safe": self.secret_safe,
        }


@dataclass(frozen=True)
class KalshiRepairValidationCommand:
    label: str
    command: str
    prints_secret_values: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "command": self.command,
            "prints_secret_values": self.prints_secret_values,
        }


@dataclass(frozen=True)
class KalshiCredentialChecklist:
    items: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"items": self.items, "secret_safe": True}


class KalshiOperatorRepairWizard:
    def __init__(self, *, forensics_report: dict[str, Any] | None = None) -> None:
        self.forensics_report = forensics_report

    def _forensics(self) -> dict[str, Any]:
        return self.forensics_report or KalshiCredentialForensics().to_report()

    def _validation_commands(self) -> list[KalshiRepairValidationCommand]:
        return [
            KalshiRepairValidationCommand(
                "key id present",
                "powershell -NoProfile -Command \"[Environment]::GetEnvironmentVariable('KALSHI_API_KEY_ID') -ne $null\"",
            ),
            KalshiRepairValidationCommand(
                "private key path present",
                "powershell -NoProfile -Command \"[Environment]::GetEnvironmentVariable('KALSHI_API_PRIVATE_KEY_PEM_PATH') -ne $null\"",
            ),
            KalshiRepairValidationCommand(
                "v14 read only retest",
                "python scripts/generate_v14_reports.py",
            ),
        ]

    def to_report(self) -> dict[str, Any]:
        forensics = self._forensics()
        steps = [
            KalshiRepairStep("step-1", "Identify selected local source", "Use the selected_source field only; do not print key values."),
            KalshiRepairStep("step-2", "Repair private-key reference", "Prefer KALSHI_API_PRIVATE_KEY_PEM_PATH pointing at a local PEM file."),
            KalshiRepairStep("step-3", "Retest READ_ONLY terrain", "Run the V14 report generator and inspect PASS/PARTIAL outcome."),
        ]
        checklist = KalshiCredentialChecklist(
            [
                "Key id present in approved local source.",
                "Private key file path present and readable by the operator runtime.",
                "No raw private key copied into prompts, dashboards, reports, or logs.",
                "Only bounded Kalshi READ_ONLY endpoints are used during retest.",
            ]
        )
        verdict = "PASS" if forensics.get("credentials_valid_for_retry") else "OPERATOR_ACTION_REQUIRED"
        return {
            "workstream": "V14: Kalshi Operator Repair Wizard",
            "selected_source": forensics.get("selected_source", "missing"),
            "failure_reason": forensics.get("failure_reason", "CREDENTIALS_MISSING"),
            "steps": [step.to_dict() for step in steps],
            "checklist": checklist.to_dict(),
            "validation_commands": [command.to_dict() for command in self._validation_commands()],
            "secret_values_exposed": False,
            "verdict": verdict,
        }


class KalshiReadOnlyRetestPlan:
    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V14: Kalshi READ_ONLY Retest Plan",
            "safe_retest_commands": [
                "python scripts/generate_v14_reports.py",
                "python -m pytest tests/test_kalshi_credential_forensics.py tests/test_real_terrain_retry_gate.py -q --tb=short --timeout=60",
            ],
            "expected_outcomes": ["PASS", "PARTIAL"],
            "write_endpoints_allowed": [],
            "live_submit_required": False,
            "verdict": "PASS",
        }
