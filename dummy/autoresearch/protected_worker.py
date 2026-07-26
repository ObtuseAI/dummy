"""Private entry point for code-owned, zero-network research plugins.

This file is launched directly with ``python -I``.  It is not a general command
runner: plugin IDs, versions, kinds, and callable targets are fixed in source.
"""

from __future__ import annotations

import json
import socket
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dummy.autoresearch.control_models import (  # noqa: E402
    EvidenceSnapshot,
    ResearchDefinition,
    ResearchKind,
)
from dummy.autoresearch.negative_controls import (  # noqa: E402
    run_negative_control_suite,
)
from dummy.autoresearch.research_plugins import (  # noqa: E402
    EVOLUTION_PLUGIN_ID,
    EVOLUTION_PLUGIN_VERSION,
    INTELLIGENCE_PLUGIN_ID,
    INTELLIGENCE_PLUGIN_VERSION,
)


def _deny_network(*_args: Any, **_kwargs: Any) -> None:
    raise PermissionError("network access is disabled in the research worker")


def _install_network_guard() -> None:
    socket.socket = _deny_network  # type: ignore[assignment]
    socket.create_connection = _deny_network  # type: ignore[assignment]
    socket.getaddrinfo = _deny_network  # type: ignore[assignment]


def _execute_intelligence(
    definition: ResearchDefinition,
    evidence: EvidenceSnapshot,
) -> dict[str, Any]:
    controls = run_negative_control_suite(definition, evidence)
    registered = bool(definition.parameters.get("registered_intervention"))
    if not registered:
        return {
            "worker_status": "BLOCKED",
            "outcome": "BLOCKED",
            "reason": "BLOCKED_NO_REGISTERED_EXECUTOR",
            "candidate_id": definition.candidate_id,
            "negative_controls": controls,
            "validated_effect": False,
        }
    # Generated cognitive protocols are prose-level preregistrations.  The
    # worker records that they passed adversarial input checks, but it cannot
    # invent an effect or access the protected private evaluator.
    return {
        "worker_status": "COMPLETE",
        "outcome": "INCONCLUSIVE",
        "reason": "AWAITING_REGISTERED_FIXED_COST_DOMAIN_EVALUATOR",
        "candidate_id": definition.candidate_id,
        "negative_controls": controls,
        "validated_effect": False,
        "private_item_details": None,
    }


def _execute_evolution(
    definition: ResearchDefinition,
    evidence: EvidenceSnapshot,
) -> dict[str, Any]:
    controls = run_negative_control_suite(definition, evidence)
    if not controls["passed"]:
        return {
            "worker_status": "BLOCKED",
            "outcome": "FAIL",
            "reason": "NEGATIVE_CONTROL_FAILURE",
            "candidate_id": definition.candidate_id,
            "negative_controls": controls,
            "validated_effect": False,
        }
    from autonomy.evolution_lab import run_evolution_lab

    payload = evidence.payload
    rows = [dict(item) for item in payload.get("rows", ())]
    previous = dict(payload.get("previous_report") or {})
    report = run_evolution_lab(
        rows,
        previous_report=previous,
        as_of=evidence.captured_at,
        population_size=int(definition.parameters["population_size"]),
        bootstrap_simulations=int(
            definition.parameters["bootstrap_simulations"]
        ),
    )
    active = report.get("active_research_candidate") or {}
    retrospective = report.get("retrospective_out_of_sample") or {}
    forward = report.get("forward_ratchet") or {}
    ready = bool(forward.get("ready_for_explicit_shadow_review"))
    candidate_id = str(active.get("genome_id") or definition.candidate_id)
    return {
        "worker_status": "COMPLETE",
        "outcome": "PASS" if ready else "INCONCLUSIVE",
        "reason": (
            "READY_FOR_HUMAN_RESEARCH_REVIEW"
            if ready
            else "ACCUMULATING_FORWARD_EVIDENCE"
        ),
        "candidate_id": candidate_id,
        "negative_controls": controls,
        "validated_effect": ready,
        "evolution_summary": {
            "generation": int(report.get("generation") or 0),
            "status": str(report.get("status") or "UNKNOWN"),
            "evidence": dict(report.get("evidence") or {}),
            "research_leader": report.get("research_leader"),
            "active_research_candidate": active,
            "retrospective_gate": bool(
                retrospective.get("passes_research_epoch_gate")
            ),
            "forward_gate": ready,
            "forward_failed": bool(forward.get("failed_research_epoch")),
            "authority": dict(report.get("authority") or {}),
            "evidence_quarantine": dict(
                report.get("evidence_quarantine") or {}
            ),
        },
    }


_ALLOWLIST = {
    (
        INTELLIGENCE_PLUGIN_ID,
        INTELLIGENCE_PLUGIN_VERSION,
        ResearchKind.INTELLIGENCE_PROTOCOL,
    ): _execute_intelligence,
    (
        EVOLUTION_PLUGIN_ID,
        EVOLUTION_PLUGIN_VERSION,
        ResearchKind.EVOLUTION_GENERATION,
    ): _execute_evolution,
}


def execute(request: dict[str, Any]) -> dict[str, Any]:
    definition = ResearchDefinition.from_dict(request["definition"])
    evidence = EvidenceSnapshot.from_dict(request["evidence"])
    key = (definition.plugin_id, definition.plugin_version, definition.kind)
    handler = _ALLOWLIST.get(key)
    if handler is None:
        return {
            "worker_status": "BLOCKED",
            "outcome": "BLOCKED",
            "reason": "PLUGIN_NOT_ALLOWLISTED",
            "candidate_id": definition.candidate_id,
            "negative_controls": {"checks": {}, "passed": False},
            "validated_effect": False,
        }
    return handler(definition, evidence)


def main() -> int:
    _install_network_guard()
    raw = sys.stdin.buffer.read()
    try:
        request = json.loads(raw.decode("utf-8"))
        if not isinstance(request, dict):
            raise ValueError("worker request must be an object")
        result = execute(request)
        result.update(
            {
                "schema_version": 1,
                "sandbox": {
                    "isolated_process": True,
                    "network_access": False,
                    "credential_access": False,
                    "environment_policy": "EXPLICIT_CODE_OWNED_ONLY",
                    "working_directory": ".",
                },
                "source_edit_applied": False,
                "runtime_application": False,
                "automatic_promotion": False,
                "execution_authority": False,
                "capital_authority": False,
                "orders_placed": False,
            }
        )
        sys.stdout.write(
            json.dumps(
                result,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        )
        return 0
    except Exception as exc:  # noqa: BLE001 - emit a bounded failure contract
        failure = {
            "schema_version": 1,
            "worker_status": "FAILED",
            "outcome": "FAIL",
            "reason": type(exc).__name__,
            "message": str(exc)[:500],
            "source_edit_applied": False,
            "runtime_application": False,
            "automatic_promotion": False,
            "execution_authority": False,
            "capital_authority": False,
            "orders_placed": False,
        }
        sys.stdout.write(
            json.dumps(failure, sort_keys=True, separators=(",", ":"))
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
