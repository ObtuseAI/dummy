"""Shared helpers for real-proof registry/evidence tests (isolated to tmp_path)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

BACKUP_DIR_NAME = "real_proof_backup_20260707T1855"
INDEX_NAME = "REAL_BROKER_PROOF_EVIDENCE_INDEX.json"


def make_evidence_bundle(
    tmp_path: Path,
    *,
    status: str = "BROKER_REJECTED",
    contacted: bool = True,
    submitted_count: int = 0,
    rejection_captured: bool = True,
    broker_rejected: bool = True,
) -> tuple[Path, Path, Path, str]:
    """Create a self-contained real-proof registry + evidence index under tmp_path.

    Returns (tmp_root, registry_path, index_path, index_hash).
    """
    if not broker_rejected:
        status = "BROKER_ACCEPTED"
        rejection_captured = False
    root = tmp_path
    artifacts = root / "artifacts" / "dummy"
    backup = artifacts / BACKUP_DIR_NAME
    backup.mkdir(parents=True, exist_ok=True)

    source_payloads: dict[str, dict[str, Any]] = {
        "final_report_v298.json": {
            "version": 298,
            "execute_once_final_proof_runner_v7_controller_status": "PASS_EXECUTE_ONCE_FINAL_PROOF_RUNNER_SUBMITTED_AUTOLOCKED",
            "arm_state": "SUBMITTED_AUTOLOCKED_REAL_BROKER_ATTEMPT",
            "real_broker_contacted": True,
            "broker_rejection_captured": True,
            "real_live_orders_submitted_count": 0,
            "non_broker_double_used": False,
            "proof_is_real": True,
        },
        "final_report_v299.json": {"version": 299, "post_proof_auto_intake_v4_controller_status": "PASS_POST_PROOF_AUTO_INTAKE_READY_FOR_RECONCILE"},
        "final_report_v300.json": {"version": 300, "reconcile_forensic_auto_orchestrator_v6_controller_status": "PASS_RECONCILE_FORENSIC_AUTO_ORCHESTRATOR_V6_REVIEWED_LOCKED"},
        "final_report_v301.json": {"version": 301, "post_proof_route_autopilot_controller_status": "PASS_POST_PROOF_ROUTE_AUTOPILOT_READY_LOCKED"},
        "final_report_v304.json": {"version": 304, "completion_lift_v10_controller_status": "PASS_COMPLETION_LIFT_V10_REAL_PROOF_FORK_LOCKED"},
    }

    entries: list[dict[str, Any]] = []
    for name, payload in source_payloads.items():
        path = backup / name
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        h = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        entries.append({"path": f"artifacts/dummy/{BACKUP_DIR_NAME}/{name}", "sha256": h})

    index: dict[str, Any] = {
        "evidence_id": "dummy-real-broker-proof-evidence-20260707T1855-v298",
        "created_at": "2026-07-07T18:55:00+00:00",
        "source_artifact_paths": entries,
    }
    index_path = backup / INDEX_NAME
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    index_hash = hashlib.sha256(index_path.read_bytes()).hexdigest().upper()

    registry: dict[str, Any] = {
        "latest_real_broker_proof_evidence_dir": f"artifacts/dummy/{BACKUP_DIR_NAME}",
        "latest_real_broker_proof_index": f"artifacts/dummy/{BACKUP_DIR_NAME}/{INDEX_NAME}",
        "latest_real_broker_attempt_status": status,
        "latest_real_broker_contacted": contacted,
        "latest_real_live_orders_submitted_count": submitted_count,
        "latest_real_broker_rejection_captured": rejection_captured,
        "evidence_index_hash": index_hash,
        "proof_registry_does_not_enable_live_submit": True,
        "proof_registry_does_not_consume_new_proof": True,
        "proof_registry_does_not_call_broker": True,
        "created_at": "2026-07-07T19:29:20+00:00",
    }
    registry_path = artifacts / "real_proof_registry.json"
    registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")

    # A default-dry v298 final report so proof_lock_clear() returns True when the registry is hidden.
    final_v298 = artifacts / "final_report_v298.json"
    final_v298.write_text(
        json.dumps(
            {
                "execute_once_final_proof_runner_v7_controller_status": "PARTIAL_EXECUTE_ONCE_FINAL_PROOF_RUNNER_NOT_ARMED",
                "arm_state": "NOT_ARMED_DRY_DEFAULT",
                "real_broker_contacted": False,
                "real_live_orders_submitted_count": 0,
                "broker_rejection_captured": False,
                "non_broker_double_used": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return root, registry_path, index_path, index_hash


def patch_artifact_paths(monkeypatch, tmp_root: Path) -> None:
    """Point all registry/artifact lookups at tmp_root without touching repo files."""
    import predator_mesh.staged_gate_common as sgc
    import core.proof_lock as pl
    import predator_mesh.v304.reports as v304

    artifacts = tmp_root / "artifacts" / "dummy"
    monkeypatch.setattr(sgc, "ROOT", tmp_root)
    monkeypatch.setattr(sgc, "ARTIFACTS", artifacts)
    monkeypatch.setattr(pl, "REAL_PROOF_REGISTRY_PATH", artifacts / "real_proof_registry.json")
    monkeypatch.setattr(pl, "_v298_final_report_path", lambda: artifacts / "final_report_v298.json")
    monkeypatch.setattr(v304, "REGISTRY_PATH", artifacts / "real_proof_registry.json")
