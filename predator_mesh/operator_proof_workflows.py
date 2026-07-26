"""Stable report workflows used by the legacy operator proof appliance.

Artifact names and controller semantics intentionally remain compatible with
the v297/v298/v300/v301/v303 evidence chain.  The implementation no longer
depends on version-numbered Python packages or ``archive.report_scripts``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from predator_mesh import staged_gate_common as sgc
from predator_mesh.operator_proof_stages import command_seal
from predator_mesh.operator_proof_stages import execute_once
from predator_mesh.operator_proof_stages import post_proof
from predator_mesh.operator_proof_stages import reconcile
from predator_mesh.operator_proof_stages import starvation

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "dummy"
PACK_DIR = ROOT / "operator_authority_pack"
MANIFEST_PATH = PACK_DIR / "authority_manifest.json"
APPROVAL_PATH = (
    ROOT
    / "runtime"
    / "approvals"
    / "dummy_controlled_production_pilot_approval.json"
)
LIVE_SUBMIT_PATH = ROOT / "configs" / "live_submit.json"
CAPS_PATH = ROOT / "configs" / "caps.json"
ADAPTER_DESCRIPTOR_PATH = (
    ROOT
    / "runtime"
    / "operator_external"
    / "livebrokerfirewall_adapter_descriptor.json"
)
V298_FINAL = ARTIFACTS / "final_report_v298.json"

LIVE_PROOF_ACK = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"
REQUIRED_SCOPE = "one_controlled_production_pilot_via_firewall_only"


def _load_object(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _staged_seal_kwargs() -> dict[str, Any]:
    manifest = _load_object(MANIFEST_PATH)
    approval = _load_object(APPROVAL_PATH)
    if (
        manifest is None
        or approval is None
        or not ADAPTER_DESCRIPTOR_PATH.exists()
        or manifest.get("proof_target") != "FIRST_REAL_PILOT_PROOF"
        or approval.get("scope") != REQUIRED_SCOPE
    ):
        return {}
    return {
        "seal": {
            "authority_ready": True,
            "proof_target": "FIRST_REAL_PILOT_PROOF",
            "idempotency_key": "operator-staged-k1",
            "adapter_descriptor": {"firewall": True},
            "manifest": {"version": "v3"},
        }
    }


def _approval_valid() -> bool:
    approval = _load_object(APPROVAL_PATH)
    return approval is not None and approval.get("scope") == REQUIRED_SCOPE


def _live_submit_enabled() -> bool:
    data = _load_object(LIVE_SUBMIT_PATH)
    return bool(
        data
        and data.get("enabled")
        and data.get("proof_scope") == "one_controlled_proof"
    )


def _caps_confirmed() -> bool:
    data = _load_object(CAPS_PATH)
    if data is None:
        return False
    limit_only = (
        data.get("order_type_policy") == "LIMIT_ONLY"
        or data.get("limit_orders_only") is True
    )
    no_market = (
        data.get("market_orders_allowed") is False
        or data.get("allow_market_orders") is False
    )
    kill_on = (
        data.get("kill_switch_enabled") is True
        or data.get("kill_switch_required") is True
    )
    return (
        limit_only
        and no_market
        and kill_on
        and data.get("max_order_count", 1) == 1
    )


def _staged_arm_kwargs() -> dict[str, Any]:
    manifest = _load_object(MANIFEST_PATH)
    if (
        manifest is None
        or not ADAPTER_DESCRIPTOR_PATH.exists()
        or manifest.get("proof_target") != "FIRST_REAL_PILOT_PROOF"
        or os.environ.get("DUMMY_LIVE_PROOF_MODE") != "1"
        or os.environ.get("DUMMY_LIVE_PROOF_ACK") != LIVE_PROOF_ACK
        or not _approval_valid()
        or not _live_submit_enabled()
        or not _caps_confirmed()
    ):
        return {}
    arm = {key: True for key, _ in execute_once.ARM_CHECKS}
    arm.update({"env_mode": True, "env_ack": True})
    return {"arm": arm}


def _successful_v298() -> bool:
    """Return whether v298 contains a real, single-order broker receipt.

    The legacy fixture path deliberately uses the same controller status as a
    submitted attempt for report-contract compatibility.  Status text alone
    is therefore not proof and must never unlock reconcile, repeat/session, or
    proof-starvation state.
    """
    report = _load_object(V298_FINAL)
    return bool(
        report
        and report.get("verdict") == "PASS"
        and report.get("execute_once_final_proof_runner_v7_controller_status")
        == "PASS_EXECUTE_ONCE_FINAL_PROOF_RUNNER_SUBMITTED_AUTOLOCKED"
        and report.get("proof_is_real") is True
        and report.get("fixture_only") is False
        and report.get("uses_non_broker_double") is False
        and report.get("non_broker_double_used") is False
        and report.get("submitted_autolocked") is True
        and report.get("real_broker_contacted") is True
        and type(report.get("real_live_orders_submitted_count")) is int
        and report.get("real_live_orders_submitted_count") == 1
        and report.get("market_order_submitted") is False
        and report.get("max_attempts") == 1
        and bool(str(report.get("broker_order_id") or "").strip())
        and bool(str(report.get("proof_id") or "").strip())
        and len(str(report.get("idempotency_key") or "")) == 32
    )


def _staged_proof_kwargs() -> dict[str, Any]:
    """Never infer fill/reconciliation truth from a submit receipt.

    A verified v298 receipt proves at most that one limit order reached the
    broker.  It does not prove fill state, fees, slippage, residual exposure,
    kill behavior, or forensic review.  The retired workflow has no trusted
    broker-reconciliation loader, so its production runner stays blocked.
    Deterministic tests may still pass an explicit ``proof`` to the pure report
    factory without creating runtime authority.
    """
    return {}


def _staged_route_kwargs() -> dict[str, Any]:
    """Keep repeat/session routing blocked without reconciled broker truth."""
    return {}


def _staged_real_proof_kwargs() -> dict[str, Any]:
    return {"real_proof_override": True} if _successful_v298() else {}


def _build_bundle(
    stage: ModuleType,
    factory: Callable[..., Any],
    kwargs: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    del stage
    return factory(**kwargs).build()


def _build_for_tests(
    stage: ModuleType,
    factory: Callable[..., Any],
    kwargs: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    reports = _build_bundle(stage, factory, kwargs)
    reports[stage.FINAL_NAME] = sgc.build_final(
        reports,
        workstream=stage.WORKSTREAM,
        milestone=stage.MILESTONE,
        mission_name=stage.MISSION_NAME,
        verification_commands=stage.VERIFICATION_COMMANDS,
        required_names=stage.DEFAULT_REQUIRED_REPORT_NAMES,
    )
    return reports


def _run(
    version: int,
    stage: ModuleType,
    factory: Callable[..., Any],
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    reports = _build_bundle(stage, factory, kwargs)
    paths = {name: sgc.write_report(name, data) for name, data in reports.items()}
    final = sgc.build_final(
        reports,
        workstream=stage.WORKSTREAM,
        milestone=stage.MILESTONE,
        mission_name=stage.MISSION_NAME,
        verification_commands=stage.VERIFICATION_COMMANDS,
        required_names=stage.DEFAULT_REQUIRED_REPORT_NAMES,
        paths=paths,
    )
    final_path = sgc.write_report(stage.FINAL_NAME, final)
    sgc.write_final_index(final, final_path, f"v{version}", stage.INDEX_KEYS)
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


def generate_command_seal_reports_for_tests(
    **kwargs: Any,
) -> dict[str, dict[str, Any]]:
    return _build_for_tests(
        command_seal, command_seal.CommandSealReportFactory, kwargs
    )


def generate_execute_once_reports_for_tests(
    **kwargs: Any,
) -> dict[str, dict[str, Any]]:
    return _build_for_tests(
        execute_once, execute_once.ExecuteOnceProofReportFactory, kwargs
    )


def generate_reconcile_reports_for_tests(
    **kwargs: Any,
) -> dict[str, dict[str, Any]]:
    return _build_for_tests(
        reconcile, reconcile.ReconcileForensicReportFactory, kwargs
    )


def generate_post_proof_reports_for_tests(
    **kwargs: Any,
) -> dict[str, dict[str, Any]]:
    return _build_for_tests(
        post_proof, post_proof.PostProofRouteReportFactory, kwargs
    )


def generate_starvation_reports_for_tests(
    **kwargs: Any,
) -> dict[str, dict[str, Any]]:
    return _build_for_tests(
        starvation, starvation.ProofStarvationReportFactory, kwargs
    )


def run_command_seal_reports() -> dict[str, Any]:
    return _run(
        297,
        command_seal,
        command_seal.CommandSealReportFactory,
        _staged_seal_kwargs(),
    )


def run_execute_once_reports() -> dict[str, Any]:
    return _run(
        298,
        execute_once,
        execute_once.ExecuteOnceProofReportFactory,
        _staged_arm_kwargs(),
    )


def run_reconcile_reports() -> dict[str, Any]:
    return _run(
        300,
        reconcile,
        reconcile.ReconcileForensicReportFactory,
        _staged_proof_kwargs(),
    )


def run_post_proof_reports() -> dict[str, Any]:
    return _run(
        301,
        post_proof,
        post_proof.PostProofRouteReportFactory,
        _staged_route_kwargs(),
    )


def run_starvation_reports() -> dict[str, Any]:
    return _run(
        303,
        starvation,
        starvation.ProofStarvationReportFactory,
        _staged_real_proof_kwargs(),
    )


__all__ = [
    "generate_command_seal_reports_for_tests",
    "generate_execute_once_reports_for_tests",
    "generate_post_proof_reports_for_tests",
    "generate_reconcile_reports_for_tests",
    "generate_starvation_reports_for_tests",
    "run_command_seal_reports",
    "run_execute_once_reports",
    "run_post_proof_reports",
    "run_reconcile_reports",
    "run_starvation_reports",
]
