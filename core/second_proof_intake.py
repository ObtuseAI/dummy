"""Second-proof evidence intake, truth reconciliation, and routing.

The older post-proof intake scripts are wired to the first-proof registry
layout and report ``no proof to ingest`` for second-proof attempts. This
module ingests a second-proof evidence directory, reconciles it against the
lock/authority state, re-derives broker contact from transport witnesses
(never from narrative fields), classifies the outcome, and emits a
timestamped route report. It never mutates canonical artifacts, locks,
authorities, registries, or live-submit state.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kalshi.rejection_classifier import classify_rejection

SECOND_PROOF_LOCK_DIR = Path("runtime/proof_locks")
V3_CANDIDATE_PATH = Path("artifacts/dummy/next_proof_candidate/VALIDATED_KALSHI_PROOF_CANDIDATE_V3.json")
LIVE_SUBMIT_PATH = Path("configs/live_submit.json")
EVIDENCE_REPORT_NAME = "SECOND_REAL_PROOF_EVIDENCE_REPORT.json"

ROUTE_NO_PROOF_TO_INGEST = "ROUTE_NO_PROOF_TO_INGEST"
ROUTE_PRE_BROKER_GATE_REPAIR = "ROUTE_PRE_BROKER_GATE_REPAIR"
ROUTE_CLASSIFIED_REJECTION_NEW_AUTHORITY_REQUIRED = "ROUTE_CLASSIFIED_REJECTION_NEW_AUTHORITY_REQUIRED"
ROUTE_POST_ACCEPTANCE_RECONCILE = "ROUTE_POST_ACCEPTANCE_RECONCILE"
ROUTE_EVIDENCE_UNTRUSTED_QUARANTINE = "ROUTE_EVIDENCE_UNTRUSTED_QUARANTINE"


def _evidence_root() -> Path:
    return Path(os.environ.get("DUMMY_EVIDENCE_ROOT", "artifacts/dummy"))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def find_latest_second_proof_evidence(root: Path | None = None) -> Path | None:
    """Return the newest second_real_proof_* dir containing an evidence report."""
    root = root or _evidence_root()
    if not root.exists():
        return None
    candidates = sorted(
        (p for p in root.iterdir() if p.is_dir() and p.name.startswith("second_real_proof_")),
        key=lambda p: p.name,
        reverse=True,
    )
    for candidate in candidates:
        if (candidate / EVIDENCE_REPORT_NAME).exists():
            return candidate
    return None


def _lock_path_for(authority_id: str) -> Path:
    return SECOND_PROOF_LOCK_DIR / f"second_proof_{authority_id}.json"


def _derive_truth(evidence: dict[str, Any], lock: dict[str, Any]) -> dict[str, Any]:
    """Re-derive broker contact and outcome from transport witnesses only."""
    accepted = bool(evidence.get("broker_accepted")) and bool(evidence.get("broker_order_id"))

    # Prefer structured fields from evidence; fall back to the lock's reason
    # string, which records the firewall's exact error code.
    error_code = evidence.get("broker_rejection_code") or lock.get("broker_rejection_code") or lock.get("reason") or ""
    classification = classify_rejection(
        error_code=str(error_code),
        http_status=evidence.get("broker_rejection_http_status"),
        safe_message=evidence.get("broker_rejection_safe_message"),
        stage=evidence.get("broker_rejection_stage"),
    )

    witnessed_contact = accepted or classification.broker_contacted
    claimed_contact = bool(evidence.get("broker_contacted")) or bool(lock.get("broker_contacted"))

    return {
        "accepted": accepted,
        "witnessed_broker_contact": witnessed_contact,
        "claimed_broker_contact": claimed_contact,
        "contact_claim_unsupported": bool(claimed_contact and not witnessed_contact),
        "classification": classification.to_dict(),
    }


def _repair_plan_for_pre_broker(block_code: str, lock_consumed: bool = False) -> list[str]:
    plan = [
        "Do not create a new authority for a pre-broker gate block: no real attempt was spent.",
    ]
    if lock_consumed:
        plan = [
            "The prior runner consumed this authority's lock on a pre-broker block (mislabeling "
            "bug, now fixed: pre-broker blocks no longer consume locks). Because the lock is "
            "spent on disk, this specific retry DOES need a fresh authority: prepare-second-"
            "proof-authority → activate → enable live-submit → one-shot-live.",
        ]
    if block_code == "live_submit_disabled":
        plan.append(
            "Root cause: configs/live_submit.json was in the disabled state at the moment of "
            "submit. The preflight requires disabled, the firewall requires enabled — the "
            "enablement must happen after preflight and immediately before one-shot-live."
        )
    plan += [
        "Run second-proof-runtime-preflight (expects live-submit disabled) and confirm PASS.",
        "Enable live-submit via enable-one-proof-live-submit (typed confirmation, future expiry).",
        "Immediately run one-shot-live in the same session with the env gate set; do not run "
        "any command between enablement and one-shot-live that restores the disabled default.",
        "Verify with the route report that the firewall reached the broker-transport stage.",
    ]
    return plan


def ingest_second_proof(
    evidence_dir: Path | str | None = None,
    lock_dir: Path | None = None,
    v3_candidate_path: Path | None = None,
    live_submit_path: Path | None = None,
) -> dict[str, Any]:
    """Ingest one second-proof evidence dir and return the route report dict.

    Read-only with respect to all canonical state; the caller decides whether
    to persist the returned report via :func:`write_route_report`.
    """
    lock_dir = lock_dir or SECOND_PROOF_LOCK_DIR
    v3_candidate_path = v3_candidate_path or V3_CANDIDATE_PATH
    live_submit_path = live_submit_path or LIVE_SUBMIT_PATH

    if evidence_dir is None:
        evidence_dir = find_latest_second_proof_evidence()
    if evidence_dir is None:
        return {
            "report_name": "SECOND_PROOF_ROUTE_REPORT",
            "route": ROUTE_NO_PROOF_TO_INGEST,
            "reason": "no second_real_proof_* directory with an evidence report was found",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    evidence_dir = Path(evidence_dir)
    evidence = _load_json(evidence_dir / EVIDENCE_REPORT_NAME)
    if not evidence:
        return {
            "report_name": "SECOND_PROOF_ROUTE_REPORT",
            "route": ROUTE_NO_PROOF_TO_INGEST,
            "reason": f"evidence report missing or unreadable in {evidence_dir}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    authority_id = str(evidence.get("authority_id", ""))
    lock_path = lock_dir / f"second_proof_{authority_id}.json"
    lock = _load_json(lock_path)

    truth = _derive_truth(evidence, lock)
    classification = truth["classification"]

    reconcile = {
        "authority_id": authority_id,
        "lock_present": lock_path.exists(),
        "lock_consumed": bool(lock.get("consumed")),
        "lock_reason": lock.get("reason"),
        "lock_matches_evidence_authority": bool(lock) and authority_id != "",
        "candidate_hash_in_evidence": evidence.get("candidate_hash"),
        "candidate_hash_current": _sha256_file(v3_candidate_path),
        "candidate_hash_matches": evidence.get("candidate_hash") == _sha256_file(v3_candidate_path),
        "live_submit_currently_disabled": _load_json(live_submit_path).get("enabled") is not True,
        "market_ticker": evidence.get("candidate_market_ticker"),
        "order_type": evidence.get("candidate_order_type"),
        "price_cents": evidence.get("candidate_price"),
    }

    # Evidence is trusted only when the runtime lock corroborates it. Test
    # doubles and fixture runs can write plausible-looking evidence dirs; a
    # consumed lock in runtime/proof_locks is the ground-truth witness that a
    # real one-shot spent its attempt under this authority.
    untrusted_reasons: list[str] = []
    if not reconcile["lock_present"]:
        untrusted_reasons.append("no lock file exists for the evidence's authority_id")
    elif truth["witnessed_broker_contact"] and not reconcile["lock_consumed"]:
        untrusted_reasons.append("evidence claims a spent attempt but the lock is not consumed")
    if not authority_id:
        untrusted_reasons.append("evidence has no authority_id")

    if untrusted_reasons:
        return {
            "report_name": "SECOND_PROOF_ROUTE_REPORT",
            "route": ROUTE_EVIDENCE_UNTRUSTED_QUARANTINE,
            "evidence_dir": str(evidence_dir),
            "verdict_in_evidence": evidence.get("verdict"),
            "untrusted_reasons": untrusted_reasons,
            "truth": truth,
            "reconcile": reconcile,
            "next_actions": [
                "Do not act on this evidence: it is not corroborated by a runtime proof lock.",
                "Likely a fixture/test artifact; verify DUMMY_EVIDENCE_ROOT isolation is active in tests.",
                "Re-run intake with --evidence-dir pointing at the lock-corroborated proof directory.",
            ],
            "mutates_canonical_state": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "secrets_redacted": True,
        }

    if truth["accepted"]:
        route = ROUTE_POST_ACCEPTANCE_RECONCILE
        next_actions = [
            "Fetch order status via the adapter's get_order_status and record fill state.",
            "Record acceptance in a new timestamped acceptance report (do not mutate the registry in-place).",
            "Cancel the resting order if the proof does not require holding the position.",
        ]
    elif truth["witnessed_broker_contact"]:
        route = ROUTE_CLASSIFIED_REJECTION_NEW_AUTHORITY_REQUIRED
        next_actions = [
            f"Rejection category: {classification['category']}.",
            classification["operator_action"],
            "Prepare a new second-proof authority (the consumed lock blocks reuse).",
            "Run pre-submit read-only validation against the new candidate before arming.",
        ]
    else:
        route = ROUTE_PRE_BROKER_GATE_REPAIR
        next_actions = _repair_plan_for_pre_broker(
            str(classification["details"].get("error_code", "")),
            lock_consumed=bool(reconcile["lock_consumed"]),
        )

    return {
        "report_name": "SECOND_PROOF_ROUTE_REPORT",
        "route": route,
        "evidence_dir": str(evidence_dir),
        "verdict_in_evidence": evidence.get("verdict"),
        "truth": truth,
        "reconcile": reconcile,
        "next_actions": next_actions,
        "mutates_canonical_state": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "secrets_redacted": True,
    }


def write_route_report(report: dict[str, Any], out_dir: Path | None = None) -> Path:
    """Persist a route report to a new timestamped file and return its path."""
    out_dir = out_dir or (_evidence_root() / "second_proof_route")
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    path = out_dir / f"SECOND_PROOF_ROUTE_REPORT_{timestamp}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return path
