"""Stable runtime for the retained staged-report contracts.

Historically every milestone had a near-identical package and script.  This
module owns the common build/write protocol for V106 and later report
factories while preserving every artifact name, schema, verdict and index
key.  Retained definitions load through the integrity-checked stable contract
registry; scheduled/operator entrypoints no longer depend on version packages
or the packaged archive.

This runtime never creates authority, changes caps/live-submit configuration,
contacts a broker, or submits an order.  The seven stages that can observe
operator-owned inputs reproduce their former read-only discovery rules and
fail closed when any input is missing or malformed.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

from predator_mesh import operator_proof_workflows
from predator_mesh import report_contract_registry
from predator_mesh import staged_gate_common as sgc

ROOT = Path(__file__).resolve().parents[1]
MIN_SUPPORTED_VERSION = 106
MAX_SUPPORTED_VERSION = 304
LIVE_PROOF_ACK = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"

_STABLE_STAGE_RUNNERS: dict[int, Callable[[], dict[str, Any]]] = {
    297: operator_proof_workflows.run_command_seal_reports,
    298: operator_proof_workflows.run_execute_once_reports,
    300: operator_proof_workflows.run_reconcile_reports,
    301: operator_proof_workflows.run_post_proof_reports,
    303: operator_proof_workflows.run_starvation_reports,
}

_DYNAMIC_NAME = re.compile(
    r"^(?P<kind>generate_all|generate_bundle|run)_v"
    r"(?P<version>[0-9]+)_reports(?:_for_tests)?$"
)


class ReportContractError(RuntimeError):
    """A requested report factory is absent or does not satisfy the contract."""


@lru_cache(maxsize=None)
def _stage(version: int) -> ModuleType:
    if version < MIN_SUPPORTED_VERSION or version > MAX_SUPPORTED_VERSION:
        raise ReportContractError(
            f"report version {version} is outside the retained "
            f"V{MIN_SUPPORTED_VERSION}-V{MAX_SUPPORTED_VERSION} contract"
        )
    try:
        stage = report_contract_registry.load_contract(version)
        milestone = stage.MILESTONE
        report_contract_registry.factory_type(version)
    except (AttributeError, LookupError, RuntimeError) as exc:
        raise ReportContractError(
            f"report version {version} has no importable retained factory"
        ) from exc

    required = (
        "DEFAULT_REQUIRED_REPORT_NAMES",
        "FINAL_NAME",
        "INDEX_KEYS",
        "MISSION_NAME",
        "VERIFICATION_COMMANDS",
        "WORKSTREAM",
    )
    missing = [name for name in required if not hasattr(stage, name)]
    if missing:
        raise ReportContractError(
            f"report version {version} is missing: {', '.join(missing)}"
        )
    setattr(stage, "_stable_runtime_milestone", milestone)
    return stage


def _factory(version: int, **kwargs: Any) -> Any:
    _stage(version)
    return report_contract_registry.factory_type(version)(**kwargs)


def generate_report_bundle(
    version: int, **kwargs: Any
) -> dict[str, dict[str, Any]]:
    """Build component reports without writing artifacts."""

    reports = _factory(version, **kwargs).build()
    if not isinstance(reports, dict):
        raise ReportContractError(
            f"report version {version} returned a non-dict bundle"
        )
    return reports


def generate_all_reports_for_tests(
    version: int, **kwargs: Any
) -> dict[str, dict[str, Any]]:
    """Build component and final reports without touching the artifact tree."""

    stage = _stage(version)
    reports = generate_report_bundle(version, **kwargs)
    reports[stage.FINAL_NAME] = sgc.build_final(
        reports,
        workstream=stage.WORKSTREAM,
        milestone=stage._stable_runtime_milestone,
        mission_name=stage.MISSION_NAME,
        verification_commands=stage.VERIFICATION_COMMANDS,
        required_names=stage.DEFAULT_REQUIRED_REPORT_NAMES,
    )
    return reports


def _load_object(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


class _NoContactContractDouble:
    """Non-broker double for the retained V269 adapter-shape check."""

    def __init__(self, attempt_id: str) -> None:
        self._attempt_id = attempt_id

    def submit(self, order: dict[str, Any]) -> dict[str, Any]:
        is_market = bool(order.get("is_market_order"))
        return {
            "order_attempt_id": "" if is_market else self._attempt_id,
            "accepted": not is_market,
            "real_broker_contacted": False,
            "market_order": is_market,
        }


def _v266_kwargs() -> dict[str, Any]:
    approval = _load_object(
        ROOT
        / "runtime"
        / "approvals"
        / "dummy_controlled_production_pilot_approval.json"
    )
    manifest = ROOT / "operator_authority_pack" / "authority_manifest.json"
    if approval is None or not manifest.exists():
        return {}
    return {
        "import_approval": approval,
        "live_submit_descriptor": True,
        "caps_descriptor": True,
        "firewall_descriptor": True,
    }


def _v267_kwargs() -> dict[str, Any]:
    manifest = _load_object(
        ROOT / "operator_authority_pack" / "authority_manifest.json"
    )
    return {"manifest": manifest} if manifest is not None else {}


def _v268_kwargs() -> dict[str, Any]:
    pack = ROOT / "operator_authority_pack"
    live_submit = _load_object(pack / "live_submit_descriptor.json")
    caps = _load_object(pack / "caps_descriptor.json")
    if live_submit is None or caps is None:
        return {}
    return {
        "live_submit_descriptor": live_submit,
        "caps_descriptor": caps,
    }


def _v269_kwargs() -> dict[str, Any]:
    descriptor = _load_object(
        ROOT
        / "runtime"
        / "operator_external"
        / "livebrokerfirewall_adapter_descriptor.json"
    )
    if descriptor is None or descriptor.get("adapter_type") != "LiveBrokerFirewall":
        return {}
    return {
        "firewall_adapter": _NoContactContractDouble(
            str(descriptor.get("adapter_name", "v269-contract-double"))
        )
    }


def _authority_manifest_ready() -> bool:
    manifest = _load_object(
        ROOT / "operator_authority_pack" / "authority_manifest.json"
    )
    descriptor = (
        ROOT
        / "runtime"
        / "operator_external"
        / "livebrokerfirewall_adapter_descriptor.json"
    )
    return bool(
        manifest
        and descriptor.exists()
        and manifest.get("proof_target") == "FIRST_REAL_PILOT_PROOF"
    )


def _env_gate_present() -> bool:
    return (
        os.environ.get("DUMMY_LIVE_PROOF_MODE") == "1"
        and os.environ.get("DUMMY_LIVE_PROOF_ACK") == LIVE_PROOF_ACK
    )


def _v271_kwargs() -> dict[str, Any]:
    if not _authority_manifest_ready():
        return {}
    env_gate = _env_gate_present()
    return {
        "import_override": True,
        "schema_override": True,
        "caps_override": True,
        "adapter_override": True,
        "freeze_override": True,
        "env_gate_mode": env_gate,
        "env_gate_ack": LIVE_PROOF_ACK if env_gate else "",
    }


def _v296_kwargs() -> dict[str, Any]:
    if not _authority_manifest_ready():
        return {}
    return {
        "authority": {
            "import_ok": True,
            "authority_present": True,
            "caps_ok_prereq": True,
            "caps_ok": True,
            "adapter_ok": True,
            "env_gate": _env_gate_present(),
        }
    }


def _v299_kwargs() -> dict[str, Any]:
    report = _load_object(ROOT / "artifacts" / "dummy" / "final_report_v298.json")
    if (
        report is None
        or report.get("execute_once_final_proof_runner_v7_controller_status")
        != "PASS_EXECUTE_ONCE_FINAL_PROOF_RUNNER_SUBMITTED_AUTOLOCKED"
    ):
        return {}
    return {
        "attempt": {
            "proof_id": "v298-pilot-1",
            "proof_target": "FIRST_REAL_PILOT_PROOF",
            "order_attempt_id": "v298-final-proof-attempt-1",
            "idempotency_key": "operator-staged-k1",
            "timestamp": report.get("generated_at", ""),
            "attempt_status": report.get(
                "execute_once_final_proof_runner_v7_controller_status"
            ),
            "proof_lock": "AUTOLOCKED",
            "adapter_response_shape": "non_broker_double",
        }
    }


_STAGED_KWARGS: dict[int, Callable[[], dict[str, Any]]] = {
    266: _v266_kwargs,
    267: _v267_kwargs,
    268: _v268_kwargs,
    269: _v269_kwargs,
    271: _v271_kwargs,
    296: _v296_kwargs,
    299: _v299_kwargs,
}


def run_reports(version: int) -> dict[str, Any]:
    """Write one retained report chain using its exact historical contract."""

    stable_runner = _STABLE_STAGE_RUNNERS.get(version)
    if stable_runner is not None:
        return stable_runner()

    stage = _stage(version)
    kwargs = _STAGED_KWARGS.get(version, lambda: {})()
    reports = generate_report_bundle(version, **kwargs)
    paths = {
        name: sgc.write_report(name, data) for name, data in reports.items()
    }
    final = sgc.build_final(
        reports,
        workstream=stage.WORKSTREAM,
        milestone=stage._stable_runtime_milestone,
        mission_name=stage.MISSION_NAME,
        verification_commands=stage.VERIFICATION_COMMANDS,
        required_names=stage.DEFAULT_REQUIRED_REPORT_NAMES,
        paths=paths,
    )
    final_path = sgc.write_report(stage.FINAL_NAME, final)
    sgc.write_final_index(
        final, final_path, f"v{version}", stage.INDEX_KEYS
    )
    sgc.update_tests_summary(
        version,
        [
            "final_report.json",
            "tests_summary.json",
            stage.FINAL_NAME,
            *sorted(reports),
        ],
        sgc.required_stage_tests(version),
        final["verdict"],
        final["generated_at"],
        stage.VERIFICATION_COMMANDS,
    )
    return final


def __getattr__(name: str) -> Callable[..., Any]:
    """Expose import-compatible named callables without per-version modules."""

    match = _DYNAMIC_NAME.fullmatch(name)
    if match is None:
        raise AttributeError(name)
    version = int(match.group("version"))
    kind = match.group("kind")
    _stage(version)

    if kind == "generate_all":
        return lambda **kwargs: generate_all_reports_for_tests(
            version, **kwargs
        )
    if kind == "generate_bundle":
        return lambda **kwargs: generate_report_bundle(version, **kwargs)
    return lambda: run_reports(version)


__all__ = [
    "MAX_SUPPORTED_VERSION",
    "MIN_SUPPORTED_VERSION",
    "ReportContractError",
    "generate_all_reports_for_tests",
    "generate_report_bundle",
    "run_reports",
]
