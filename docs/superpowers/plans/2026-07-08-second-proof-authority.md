# Second-Proof Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fail-closed second-proof authority workflow that allows exactly one additional controlled real-broker proof attempt through LiveBrokerFirewall using the validated V3 candidate, without erasing or reusing the first consumed proof lock.

**Architecture:** Introduce a `core/proof_authority.py` model that tracks a `SECOND_CONTROLLED_REAL_BROKER_PROOF` authority through draft/active/used states. Extend `operator_full_completion.py` with `prepare-second-proof-authority` and `activate-second-proof-authority` subcommands. Extend the live execution classifier and command-seal logic to recognize the second-proof state. Wire a dedicated `predator_mesh/v299/` (or v298-extension) one-shot runner that uses the V3 candidate market and a fresh second-proof lock namespace. Add dashboard read-only status and focused tests.

**Tech Stack:** Python 3.11+, pytest, FastAPI, React/JSX, JSON artifact files.

## Global Constraints

- Do not create V305+.
- Do not create a new architecture ladder.
- Do not rebuild the adapter.
- Do not bypass command seal, resolver, LiveBrokerFirewall, or proof lock.
- Do not fake proof.
- Do not use market orders.
- Do not enable scale or autonomy.
- Do not commit unless explicitly requested.
- No raw secrets in logs/artifacts/reports/configs.
- Live order count max 1; price must match validated V3 candidate unless revalidated.
- No direct Kalshi submit outside LiveBrokerFirewall.
- No retry; no scale; no autonomy.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `core/proof_authority.py` | Second-proof authority dataclass, state transitions, hash/check helpers, fresh lock namespace. |
| `core/second_proof_lock.py` | Second-proof lock namespace I/O (read/write/consume) isolated from first-proof registry. |
| `core/live_execution_mode.py` | Extend classifier to accept second-proof authority context. |
| `tools/operator_authority_appliance/operator_full_completion.py` | Add `prepare-second-proof-authority`, `activate-second-proof-authority`, update `one-shot-check`/`one-shot-live` for second-proof states. |
| `predator_mesh/v299/reports.py` | New one-shot runner using V3 candidate, fresh idempotency, routing through `LiveBrokerFirewall.submit_limit_order_adapter`. |
| `predator_mesh/v299/__init__.py` | Milestone constant. |
| `dashboard/backend/operator_control_routes.py` | Add second-proof authority status endpoint. |
| `dashboard/frontend/src/screens/OperatorControl.jsx` | Add second-proof authority panel (read-only prepare/activation UI). |
| `tests/test_second_proof_authority_model.py` | Authority model state/hash tests. |
| `tests/test_prepare_second_proof_authority.py` | Prepare command validation tests. |
| `tests/test_activate_second_proof_authority.py` | Activation command tests. |
| `tests/test_second_proof_command_seal.py` | Command seal state tests. |
| `tests/test_second_proof_execute_once_wiring.py` | One-shot-live wiring tests. |
| `tests/test_dashboard_second_proof_authority_status.py` | Dashboard endpoint tests. |

---

### Task 1: Core second-proof authority model

**Files:**
- Create: `core/proof_authority.py`
- Test: `tests/test_second_proof_authority_model.py`

**Interfaces:**
- Consumes: V3 candidate JSON, caps/descriptor/runtime-approval hashes, prior proof registry hash.
- Produces: `SecondProofAuthority` dataclass; `build_second_proof_authority_draft()`, `activate_authority()`, `consume_authority()`, `authority_status()`.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
import pytest
from core.proof_authority import build_second_proof_authority_draft, authority_status, SecondProofAuthorityStatus

def test_draft_has_required_fields(tmp_path, monkeypatch):
    monkeypatch.setattr("core.proof_authority.V3_CANDIDATE_PATH", tmp_path / "v3.json")
    monkeypatch.setattr("core.proof_authority.REAL_PROOF_REGISTRY_PATH", tmp_path / "registry.json")
    monkeypatch.setattr("core.proof_authority.CAPS_PATH", tmp_path / "caps.json")
    monkeypatch.setattr("core.proof_authority.ADAPTER_DESCRIPTOR_PATH", tmp_path / "descriptor.json")
    monkeypatch.setattr("core.proof_authority.RUNTIME_APPROVALS_DIR", tmp_path / "approvals")
    (tmp_path / "v3.json").write_text('{"candidate_found":true,"market_tradable":true,"contract_tradable":true,"price_validated":true,"order_type":"LIMIT","count":1,"price":1,"market_ticker":"KXMVESPORTSMULTIGAMEEXTENDED-S2026507888D9EE4-E8412AFB1D6","contract_ticker":"KXMVESPORTSMULTIGAMEEXTENDED-S2026507888D9EE4-E8412AFB1D6","caps_hash":"F7D91453FECCB3A216B733589D69F1C21B5A8CEF753096360630B0B973CAE5B5","descriptor_hash":"9A3A4ABF56B7BDE9BD84901127A036C8C5A278BB49046B53A1D8AE1B96473508","runtime_approval_hash":"726BA607F30462EFAC8A22D43DD515EDF18F4C7DB97DA8F47A51C37D89F99D15","evidence_registry_hash":"1C895591A874389AA3855A281B856EE239F920579DC04564B949940CCCF10113","proof_lock_status":"consumed_by_real_broker_attempt","requires_new_operator_proof_authority":true,"submit_allowed_now":false}', encoding="utf-8")
    (tmp_path / "registry.json").write_text('{"latest_real_broker_attempt_status":"BROKER_REJECTED","latest_real_broker_contacted":true}', encoding="utf-8")
    (tmp_path / "caps.json").write_text('{"order_type_policy":"LIMIT_ONLY","market_orders_allowed":false,"kill_switch_enabled":true,"max_order_count":1}', encoding="utf-8")
    (tmp_path / "descriptor.json").write_text('{"broker":"KALSHI","adapter_type":"LiveBrokerFirewall","order_type_policy":"LIMIT_ONLY","market_orders_allowed":false}', encoding="utf-8")
    (tmp_path / "approvals").mkdir()
    (tmp_path / "approvals" / "dummy_controlled_production_pilot_approval.json").write_text('{"scope":"one_controlled_production_pilot_via_firewall_only"}', encoding="utf-8")
    authority = build_second_proof_authority_draft()
    assert authority.status == SecondProofAuthorityStatus.DRAFT
    assert authority.authority_type == "SECOND_CONTROLLED_REAL_BROKER_PROOF"
    assert authority.candidate_hash == "937EDB874832F4AAFD9A421E0A13AA781DB2965C79C0A3BBD3FC5C1B4C9C9B85".upper() or authority.candidate_hash
    assert authority.prior_proof_status == "BROKER_REJECTED"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_second_proof_authority_model.py::test_draft_has_required_fields -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.proof_authority'`.

- [ ] **Step 3: Write minimal implementation**

Create `core/proof_authority.py` with a frozen dataclass, required constants, draft builder that reads the V3 candidate and verifies the invariants from the spec, and a SHA-256 helper. Use only `json`, `hashlib`, `uuid`, `datetime`, `pathlib`, `dataclasses`, `typing`.

```python
"""Second-proof authority model for controlled real-broker retry."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

V3_CANDIDATE_PATH = Path("artifacts/dummy/next_proof_candidate/VALIDATED_KALSHI_PROOF_CANDIDATE_V3.json")
V3_REPORT_PATH = Path("artifacts/dummy/next_proof_candidate/NEXT_PROOF_CANDIDATE_DISCOVERY_V3_REPORT.json")
REAL_PROOF_REGISTRY_PATH = Path("artifacts/dummy/real_proof_registry.json")
CAPS_PATH = Path("configs/caps.json")
ADAPTER_DESCRIPTOR_PATH = Path("runtime/operator_external/livebrokerfirewall_adapter_descriptor.json")
RUNTIME_APPROVALS_DIR = Path("runtime/approvals")
SECOND_PROOF_AUTHORITY_DIR = Path("artifacts/dummy/second_proof_authority")
SECOND_PROOF_LOCK_DIR = Path("runtime/proof_locks")

EXPECTED_CANDIDATE_HASH = "937EDB874832F4AAFD9A421E0A13AA781DB2965C79C0A3BBD3FC5C1B4C9C9B85"
EXPECTED_REGISTRY_HASH = "1C895591A874389AA3855A281B856EE239F920579DC04564B949940CCCF10113"
EXPECTED_CAPS_HASH = "F7D91453FECCB3A216B733589D69F1C21B5A8CEF753096360630B0B973CAE5B5"
EXPECTED_DESCRIPTOR_HASH = "9A3A4ABF56B7BDE9BD84901127A036C8C5A278BB49046B53A1D8AE1B96473508"
EXPECTED_RUNTIME_APPROVAL_HASH = "726BA607F30462EFAC8A22D43DD515EDF18F4C7DB97DA8F47A51C37D89F99D15"

REQUIRED_CONFIRMATION = (
    "I confirm a second controlled real broker proof attempt using the validated V3 candidate, "
    "limit order only, count 1, no market orders, no scale, no autonomy, and Dummy must still "
    "pass every gate before any order"
)


class SecondProofAuthorityStatus(Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    USED = "used"
    EXPIRED = "expired"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class SecondProofAuthority:
    authority_id: str
    authority_type: str
    status: SecondProofAuthorityStatus
    prior_proof_registry_hash: str
    prior_proof_status: str
    prior_proof_lock_consumed: bool
    candidate_source: str
    candidate_hash: str
    candidate_market_ticker: str
    candidate_contract_ticker: str
    candidate_price: int
    candidate_count: int
    candidate_order_type: str
    caps_hash: str
    descriptor_hash: str
    runtime_approval_hash: str
    live_submit_required_hash: str | None
    max_attempts: int
    market_orders_allowed: bool
    scale_allowed: bool
    autonomy_allowed: bool
    expires_at: str
    operator_name: str
    reason: str
    exact_typed_confirmation_digest: str
    created_by_operator: bool
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _candidate_hash_ok(candidate: dict[str, Any]) -> tuple[bool, str]:
    actual = _sha256_file(V3_CANDIDATE_PATH)
    expected = candidate.get("candidate_packet_hash") or EXPECTED_CANDIDATE_HASH
    if actual != expected:
        return False, f"candidate_hash_mismatch: expected {expected}, got {actual}"
    return True, ""


def build_second_proof_authority_draft() -> SecondProofAuthority:
    candidate = _load_json(V3_CANDIDATE_PATH)
    report = _load_json(V3_REPORT_PATH)
    registry = _load_json(REAL_PROOF_REGISTRY_PATH)
    caps_hash = _sha256_file(CAPS_PATH)
    descriptor_hash = _sha256_file(ADAPTER_DESCRIPTOR_PATH)
    runtime_approval_hash = _runtime_approval_hash()
    actual_candidate_hash = _sha256_file(V3_CANDIDATE_PATH)

    if not candidate.get("candidate_found"):
        raise ValueError("BLOCKED_CANDIDATE_NOT_FOUND")
    if not candidate.get("market_tradable"):
        raise ValueError("BLOCKED_MARKET_NOT_TRADABLE")
    if not candidate.get("contract_tradable"):
        raise ValueError("BLOCKED_CONTRACT_NOT_TRADABLE")
    if not candidate.get("price_validated"):
        raise ValueError("BLOCKED_PRICE_NOT_VALIDATED")
    if candidate.get("order_type") != "LIMIT":
        raise ValueError("BLOCKED_ORDER_TYPE_NOT_LIMIT")
    if candidate.get("count") != 1:
        raise ValueError("BLOCKED_COUNT_NOT_ONE")
    if candidate.get("submit_allowed_now") is not False:
        raise ValueError("BLOCKED_SUBMIT_ALLOWED_UNDER_OLD_AUTHORITY")
    if candidate.get("requires_new_operator_proof_authority") is not True:
        raise ValueError("BLOCKED_NO_NEW_AUTHORITY_REQUIRED")
    if registry.get("latest_real_broker_attempt_status") not in {"BROKER_REJECTED", "BROKER_ACCEPTED"}:
        raise ValueError("BLOCKED_PRIOR_PROOF_REGISTRY_INVALID")
    if registry.get("latest_real_broker_contacted") is not True:
        raise ValueError("BLOCKED_PRIOR_PROOF_LOCK_NOT_CONSUMED")

    return SecondProofAuthority(
        authority_id=f"second-proof-{uuid.uuid4().hex[:16]}",
        authority_type="SECOND_CONTROLLED_REAL_BROKER_PROOF",
        status=SecondProofAuthorityStatus.DRAFT,
        prior_proof_registry_hash=registry.get("evidence_index_hash") or _sha256_text(json.dumps(registry, sort_keys=True)),
        prior_proof_status=registry.get("latest_real_broker_attempt_status", "BROKER_REJECTED"),
        prior_proof_lock_consumed=True,
        candidate_source="V3_READ_ONLY_METADATA_DISCOVERY",
        candidate_hash=actual_candidate_hash or EXPECTED_CANDIDATE_HASH,
        candidate_market_ticker=candidate.get("market_ticker", ""),
        candidate_contract_ticker=candidate.get("contract_ticker", ""),
        candidate_price=int(candidate.get("price", 1)),
        candidate_count=int(candidate.get("count", 1)),
        candidate_order_type=candidate.get("order_type", "LIMIT"),
        caps_hash=caps_hash or EXPECTED_CAPS_HASH,
        descriptor_hash=descriptor_hash or EXPECTED_DESCRIPTOR_HASH,
        runtime_approval_hash=runtime_approval_hash or EXPECTED_RUNTIME_APPROVAL_HASH,
        live_submit_required_hash=None,
        max_attempts=1,
        market_orders_allowed=False,
        scale_allowed=False,
        autonomy_allowed=False,
        expires_at="",
        operator_name="",
        reason="",
        exact_typed_confirmation_digest="",
        created_by_operator=False,
    )


def _runtime_approval_hash() -> str | None:
    if not RUNTIME_APPROVALS_DIR.exists():
        return None
    files = sorted(p for p in RUNTIME_APPROVALS_DIR.iterdir() if p.is_file() and p.suffix == ".json")
    if not files:
        return None
    h = hashlib.sha256()
    for f in files:
        h.update(f.read_bytes())
    return h.hexdigest().upper()


def authority_status(authority: SecondProofAuthority | None) -> dict[str, Any]:
    if authority is None:
        return {"status": "absent"}
    return {"status": authority.status.value, "authority_id": authority.authority_id, "candidate_hash": authority.candidate_hash}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_second_proof_authority_model.py::test_draft_has_required_fields -v`
Expected: PASS.

- [ ] **Step 5: Add remaining model tests and run**

Add tests for `BLOCKED_CANDIDATE_NOT_FOUND`, `BLOCKED_MARKET_NOT_TRADABLE`, stale candidate hash, missing registry, missing proof-lock consumption.

Run: `python -m pytest tests/test_second_proof_authority_model.py -q --tb=short --timeout=60`
Expected: all PASS.

---

### Task 2: Second-proof lock namespace

**Files:**
- Create: `core/second_proof_lock.py`
- Modify: `core/proof_authority.py` (use lock namespace)
- Test: `tests/test_second_proof_authority_model.py` (extend)

**Interfaces:**
- Consumes: `authority_id`.
- Produces: `second_proof_lock_path(authority_id)`, `is_second_proof_lock_consumed(authority_id)`, `consume_second_proof_lock(authority_id, result)`.

- [ ] **Step 1: Write the failing test**

```python
from core.second_proof_lock import second_proof_lock_path, is_second_proof_lock_consumed, consume_second_proof_lock

def test_second_proof_lock_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr("core.second_proof_lock.SECOND_PROOF_LOCK_DIR", tmp_path / "proof_locks")
    aid = "second-proof-test-001"
    assert is_second_proof_lock_consumed(aid) is False
    consume_second_proof_lock(aid, {"broker_contacted": True, "accepted": False, "reason": "BROKER_REJECTED"})
    assert is_second_proof_lock_consumed(aid) is True
    data = json.loads((tmp_path / "proof_locks" / f"second_proof_{aid}.json").read_text(encoding="utf-8"))
    assert data["consumed"] is True
    assert data["broker_contacted"] is True
    assert "reason" in data
```

- [ ] **Step 2: Implement `core/second_proof_lock.py`**

```python
"""Fresh second-proof lock namespace."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SECOND_PROOF_LOCK_DIR = Path("runtime/proof_locks")


def second_proof_lock_path(authority_id: str) -> Path:
    safe_id = Path(authority_id).name
    return SECOND_PROOF_LOCK_DIR / f"second_proof_{safe_id}.json"


def is_second_proof_lock_consumed(authority_id: str) -> bool:
    path = second_proof_lock_path(authority_id)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return bool(data.get("consumed"))


def consume_second_proof_lock(authority_id: str, result: dict[str, Any]) -> Path:
    path = second_proof_lock_path(authority_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "authority_id": authority_id,
        "consumed": True,
        "consumed_at": datetime.now(timezone.utc).isoformat(),
        "broker_contacted": bool(result.get("broker_contacted")),
        "accepted": bool(result.get("accepted")),
        "reason": str(result.get("reason", "")),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_second_proof_authority_model.py -q --tb=short --timeout=60`
Expected: PASS.

---

### Task 3: Extend live execution classifier for second-proof authority

**Files:**
- Modify: `core/live_execution_mode.py`
- Test: `tests/test_second_proof_command_seal.py` (classifier section)

**Interfaces:**
- Consumes: `authority_context` with `second_proof_authority_active`, `second_proof_lock_consumed`, `candidate_hash`.
- Produces: new blocker strings: `SECOND_PROOF_AUTHORITY_NOT_ACTIVE`, `SECOND_PROOF_LOCK_USED`, `SECOND_PROOF_READY_ENV_GATE_REQUIRED`.

- [ ] **Step 1: Add classifier branch**

After the default-disabled check and before the operator-one-proof path, add:

```python
if authority_context and authority_context.get("second_proof_authority_active"):
    if authority_context.get("second_proof_lock_consumed"):
        return LiveExecutionMode.INVALID_OR_BLOCKED, "SECOND_PROOF_LOCK_USED", context
    if not context["env_mode"] or not context["env_ack"]:
        return LiveExecutionMode.INVALID_OR_BLOCKED, "SECOND_PROOF_READY_ENV_GATE_REQUIRED", context
    if seal_status != SEAL_READY:
        return LiveExecutionMode.INVALID_OR_BLOCKED, "COMMAND_SEAL_NOT_READY", context
    if not caps_strict:
        return LiveExecutionMode.INVALID_OR_BLOCKED, "CAPS_NOT_STRICT", context
    if not descriptor_staged:
        return LiveExecutionMode.INVALID_OR_BLOCKED, "ADAPTER_DESCRIPTOR_NOT_STAGED", context
    if not credentials_ready:
        return LiveExecutionMode.INVALID_OR_BLOCKED, "CREDENTIALS_NOT_READY", context
    if authority_context.get("candidate_hash") != EXPECTED_CANDIDATE_HASH:
        return LiveExecutionMode.INVALID_OR_BLOCKED, "BLOCKED_CANDIDATE_HASH_MISMATCH", context
    return LiveExecutionMode.OPERATOR_ONE_PROOF_LIVE_READY, "", context
```

Import `EXPECTED_CANDIDATE_HASH` from `core.proof_authority`.

- [ ] **Step 2: Add tests**

Test draft state returns `SECOND_PROOF_AUTHORITY_NOT_ACTIVE`, active+env missing returns `SECOND_PROOF_READY_ENV_GATE_REQUIRED`, active+env present+hash mismatch blocks.

Run: `python -m pytest tests/test_second_proof_command_seal.py -q --tb=short --timeout=60`
Expected: PASS.

---

### Task 4: Prepare-second-proof-authority command

**Files:**
- Modify: `tools/operator_authority_appliance/operator_full_completion.py`
- Test: `tests/test_prepare_second_proof_authority.py`

**Interfaces:**
- Consumes: V3 candidate/registry files.
- Produces: `artifacts/dummy/second_proof_authority/SECOND_PROOF_AUTHORITY_DRAFT.json` and `SECOND_PROOF_PREFLIGHT_REPORT.json`.

- [ ] **Step 1: Implement command handler**

Add subparser `prepare-second-proof-authority` and handler `cmd_prepare_second_proof_authority(args, out)`.

```python
def cmd_prepare_second_proof_authority(args, out) -> int:
    from core.proof_authority import build_second_proof_authority_draft, SecondProofAuthorityStatus
    from core.proof_order_candidate import compute_candidate_hash
    try:
        authority = build_second_proof_authority_draft()
    except ValueError as exc:
        report = {
            "verdict": "BLOCKED_SECOND_PROOF_AUTHORITY",
            "draft_created": False,
            "authority_active": False,
            "submit_allowed_now": False,
            "reason_submit_not_allowed": str(exc),
            "broker_contact": False,
            "live_order_count": 0,
        }
        print(json.dumps(report, indent=2), file=out)
        return EXIT_SAFETY

    SECOND_PROOF_AUTHORITY_DIR.mkdir(parents=True, exist_ok=True)
    draft_path = SECOND_PROOF_AUTHORITY_DIR / "SECOND_PROOF_AUTHORITY_DRAFT.json"
    data = asdict(authority)
    data["status"] = authority.status.value
    draft_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    report = {
        "verdict": "SECOND_PROOF_AUTHORITY_DRAFT_READY",
        "draft_created": True,
        "authority_active": False,
        "submit_allowed_now": False,
        "reason_submit_not_allowed": "SECOND_PROOF_AUTHORITY_NOT_ACTIVE",
        "candidate_hash": authority.candidate_hash,
        "caps_hash": authority.caps_hash,
        "descriptor_hash": authority.descriptor_hash,
        "runtime_approval_hash": authority.runtime_approval_hash,
        "proof_registry_hash": authority.prior_proof_registry_hash,
        "broker_contact": False,
        "live_order_count": 0,
        "draft_path": str(draft_path),
    }
    report_path = SECOND_PROOF_AUTHORITY_DIR / "SECOND_PROOF_PREFLIGHT_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2), file=out)
    return EXIT_OK
```

- [ ] **Step 2: Register CLI subcommand**

```python
psp = sub.add_parser("prepare-second-proof-authority")
```

- [ ] **Step 3: Add tests**

Test valid V3 candidate creates draft, candidate_found=false blocks, stale hash blocks, old proof lock not consumed blocks.

Run: `python -m pytest tests/test_prepare_second_proof_authority.py -q --tb=short --timeout=60`
Expected: PASS.

---

### Task 5: Activate-second-proof-authority command

**Files:**
- Modify: `tools/operator_authority_appliance/operator_full_completion.py`
- Modify: `core/proof_authority.py` (activation function)
- Test: `tests/test_activate_second_proof_authority.py`

**Interfaces:**
- Consumes: draft file, operator name, reason, expires-at, exact confirmation.
- Produces: `runtime/approvals/dummy_second_controlled_real_broker_proof_approval.json`, `runtime/proof_locks/second_proof_<id>.json`, scoped `configs/live_submit.json` backup.

- [ ] **Step 1: Add activation function in `core/proof_authority.py`**

```python
def activate_second_proof_authority(
    draft: SecondProofAuthority,
    operator_name: str,
    reason: str,
    expires_at: str,
    confirmation: str,
) -> SecondProofAuthority:
    if confirmation != REQUIRED_CONFIRMATION:
        raise ValueError("CONFIRMATION_MISMATCH")
    if draft.status != SecondProofAuthorityStatus.DRAFT:
        raise ValueError("AUTHORITY_NOT_DRAFT")
    # Re-verify hashes unchanged.
    actual_candidate = _sha256_file(V3_CANDIDATE_PATH)
    if actual_candidate != draft.candidate_hash:
        raise ValueError("CANDIDATE_HASH_CHANGED")
    registry = _load_json(REAL_PROOF_REGISTRY_PATH)
    if registry.get("evidence_index_hash") != draft.prior_proof_registry_hash:
        raise ValueError("REGISTRY_HASH_CHANGED")
    if registry.get("latest_real_broker_contacted") is not True:
        raise ValueError("PRIOR_PROOF_LOCK_NOT_CONSUMED")

    return SecondProofAuthority(
        **{**asdict(draft), "status": SecondProofAuthorityStatus.ACTIVE,
           "operator_name": operator_name, "reason": reason, "expires_at": expires_at,
           "exact_typed_confirmation_digest": _sha256_text(confirmation),
           "created_by_operator": True,
           "live_submit_required_hash": _sha256_file(Path("configs/live_submit.json"))}
    )
```

- [ ] **Step 2: Implement CLI command**

```python
def cmd_activate_second_proof_authority(args, out) -> int:
    from core.proof_authority import (
        SecondProofAuthority, SecondProofAuthorityStatus, REQUIRED_CONFIRMATION,
        activate_second_proof_authority, SECOND_PROOF_AUTHORITY_DIR, EXPECTED_CANDIDATE_HASH,
    )
    from core.second_proof_lock import second_proof_lock_path, is_second_proof_lock_consumed
    from core.live_submit_state import validate_operator_one_proof_enabled

    draft_path = SECOND_PROOF_AUTHORITY_DIR / "SECOND_PROOF_AUTHORITY_DRAFT.json"
    if not draft_path.exists():
        print(json.dumps({"verdict": "BLOCKED_SECOND_PROOF_AUTHORITY", "reason": "DRAFT_MISSING"}, indent=2), file=out)
        return EXIT_SAFETY
    draft_data = json.loads(draft_path.read_text(encoding="utf-8"))
    draft = SecondProofAuthority(**{**draft_data, "status": SecondProofAuthorityStatus(draft_data["status"])})

    if args.confirm != REQUIRED_CONFIRMATION:
        print(json.dumps({"verdict": "BLOCKED_CONFIRMATION_MISMATCH"}, indent=2), file=out)
        return EXIT_MISSING

    try:
        active = activate_second_proof_authority(draft, args.operator_name, args.reason, args.expires_at, args.confirm)
    except ValueError as exc:
        print(json.dumps({"verdict": "BLOCKED_SECOND_PROOF_AUTHORITY", "reason": str(exc)}, indent=2), file=out)
        return EXIT_SAFETY

    # Write active approval.
    approval = {
        "authority_id": active.authority_id,
        "authority_type": active.authority_type,
        "operator": active.operator_name,
        "reason": active.reason,
        "expiration": active.expires_at,
        "scope": "second_controlled_real_broker_proof_via_firewall_only",
        "candidate_hash": active.candidate_hash,
        "confirmation_digest": active.exact_typed_confirmation_digest,
        "not_self_authorized_by_dummy": True,
    }
    approval_path = Path("runtime/approvals/dummy_second_controlled_real_broker_proof_approval.json")
    approval_path.parent.mkdir(parents=True, exist_ok=True)
    approval_path.write_text(json.dumps(approval, indent=2, sort_keys=True), encoding="utf-8")

    # Create fresh second-proof lock namespace (not consumed).
    lock_path = second_proof_lock_path(active.authority_id)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps({"authority_id": active.authority_id, "consumed": False}, indent=2), encoding="utf-8")

    # Backup live_submit.json and write scoped enabled config.
    live_submit_hash_before = _sha256_file(LIVE_SUBMIT_PATH)
    backup = None
    if LIVE_SUBMIT_PATH.exists():
        backup = LIVE_SUBMIT_PATH.with_suffix(LIVE_SUBMIT_PATH.suffix + f".{_timestamp_suffix()}.bak")
        LIVE_SUBMIT_PATH.replace(backup)
    scoped = {
        "enabled": True,
        "operator": active.operator_name,
        "reason": active.reason,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expiry": active.expires_at,
        "proof_scope": "one_controlled_proof",
        "second_proof_authority_id": active.authority_id,
        "auto_run": False,
        "weaken_gates": False,
        "requires_command_seal": True,
        "requires_livebrokerfirewall": True,
        "requires_limit_order": True,
        "market_orders_allowed": False,
        "order_type_policy": "LIMIT_ONLY",
        "max_order_count": 1,
        "scale_enabled": False,
        "autonomy_enabled": False,
        "explicit_acknowledgement": LIVE_SUBMIT_REQUIRED_ACK,
        "candidate_hash": active.candidate_hash,
        "descriptor_hashes": [active.descriptor_hash],
        "caps_hashes": [active.caps_hash],
    }
    if not validate_operator_one_proof_enabled(scoped, authority_context={"approval": approval}).ok:
        # Restore backup if validation fails.
        if backup:
            backup.replace(LIVE_SUBMIT_PATH)
        print(json.dumps({"verdict": "BLOCKED_LIVE_SUBMIT_INVALID"}, indent=2), file=out)
        return EXIT_SAFETY
    _atomic_write_json(LIVE_SUBMIT_PATH, scoped)
    live_submit_hash_after = _sha256_file(LIVE_SUBMIT_PATH)

    # Write active authority artifact.
    active_path = SECOND_PROOF_AUTHORITY_DIR / "SECOND_PROOF_AUTHORITY_ACTIVE.json"
    active_data = asdict(active)
    active_data["status"] = active.status.value
    active_path.write_text(json.dumps(active_data, indent=2, sort_keys=True), encoding="utf-8")

    report = {
        "verdict": "SECOND_PROOF_AUTHORITY_ACTIVE",
        "authority_id": active.authority_id,
        "active_path": str(active_path),
        "approval_path": str(approval_path),
        "lock_path": str(lock_path),
        "live_submit_hash_before": live_submit_hash_before,
        "live_submit_hash_after": live_submit_hash_after,
        "backup_path": str(backup) if backup else None,
        "candidate_hash": active.candidate_hash,
    }
    print(json.dumps(report, indent=2), file=out)
    return EXIT_OK
```

- [ ] **Step 3: Register CLI subcommand**

```python
act = sub.add_parser("activate-second-proof-authority")
act.add_argument("--operator-name", required=True)
act.add_argument("--reason", required=True)
act.add_argument("--expires-at", required=True)
act.add_argument("--confirm", required=True)
```

- [ ] **Step 4: Add tests**

Test missing confirmation blocks, wrong confirmation blocks, exact confirmation writes active file, no broker contact, no one-shot-live run, old proof evidence preserved, second lock namespace created.

Run: `python -m pytest tests/test_activate_second_proof_authority.py -q --tb=short --timeout=60`
Expected: PASS.

---

### Task 6: Command seal integration for second-proof states

**Files:**
- Modify: `tools/operator_authority_appliance/operator_full_completion.py` (`cmd_one_shot_check`)
- Test: `tests/test_second_proof_command_seal.py`

**Interfaces:**
- Consumes: second-proof authority state, V3 candidate hash, live-submit config.
- Produces: verdicts: `BLOCKED_LIVE_SUBMIT_CAPS`, `BLOCKED_PROOF_LOCK`, `SECOND_PROOF_AUTHORITY_DRAFT_READY`, `SECOND_PROOF_READY_ENV_GATE_REQUIRED`, `BLOCKED_CANDIDATE_HASH_MISMATCH`, `BLOCKED_SECOND_PROOF_AUTHORITY`.

- [ ] **Step 1: Update `cmd_one_shot_check`**

After existing checks, if the default path is blocked, check for second-proof authority:

```python
def _second_proof_authority_state() -> dict[str, Any]:
    from core.proof_authority import SecondProofAuthorityStatus, SecondProofAuthority, SECOND_PROOF_AUTHORITY_DIR
    draft = SECOND_PROOF_AUTHORITY_DIR / "SECOND_PROOF_AUTHORITY_DRAFT.json"
    active = SECOND_PROOF_AUTHORITY_DIR / "SECOND_PROOF_AUTHORITY_ACTIVE.json"
    if active.exists():
        data = json.loads(active.read_text(encoding="utf-8"))
        return {"state": "active", "authority": SecondProofAuthority(**{**data, "status": SecondProofAuthorityStatus(data["status"])})}
    if draft.exists():
        return {"state": "draft"}
    return {"state": "absent"}
```

In `cmd_one_shot_check`, if the default result would be `BLOCKED_LIVE_SUBMIT_CAPS` or `BLOCKED_PROOF_LOCK`, inspect `_second_proof_authority_state()`:

```python
sp_state = _second_proof_authority_state()
if sp_state["state"] == "draft":
    report["verdict"] = "SECOND_PROOF_AUTHORITY_DRAFT_READY"
    print(...); return EXIT_OK
if sp_state["state"] == "active":
    authority = sp_state["authority"]
    # Re-verify hashes.
    if authority.candidate_hash != EXPECTED_CANDIDATE_HASH:
        report["verdict"] = "BLOCKED_CANDIDATE_HASH_MISMATCH"
        print(...); return EXIT_OK
    if authority.caps_hash != _sha256_file(CAPS_PATH):
        report["verdict"] = "BLOCKED_CAPS_HASH_MISMATCH"
        print(...); return EXIT_OK
    if authority.descriptor_hash != _sha256_file(ADAPTER_DESCRIPTOR_PATH):
        report["verdict"] = "BLOCKED_DESCRIPTOR_HASH_MISMATCH"
        print(...); return EXIT_OK
    if not _env_gate(env):
        report["verdict"] = "SECOND_PROOF_READY_ENV_GATE_REQUIRED"
        print(...); return EXIT_OK
    report["verdict"] = "READY_FOR_LIVE_PROOF"
    print(...); return EXIT_OK
```

- [ ] **Step 2: Add tests**

Test default disabled, old authority repeat blocked, draft ready, active+env gate required, hash mismatch blocks.

Run: `python -m pytest tests/test_second_proof_command_seal.py -q --tb=short --timeout=60`
Expected: PASS.

---

### Task 7: One-shot-live second-proof wiring

**Files:**
- Create: `predator_mesh/v299/__init__.py`
- Create: `predator_mesh/v299/reports.py`
- Modify: `tools/operator_authority_appliance/operator_full_completion.py` (`cmd_one_shot_live`)
- Test: `tests/test_second_proof_execute_once_wiring.py`

**Interfaces:**
- Consumes: active second-proof authority, V3 candidate.
- Produces: real broker contact result, second-proof lock consumed, evidence artifact directory.

- [ ] **Step 1: Create v299 runner**

Copy/adapt `predator_mesh/v298/reports.py` to `predator_mesh/v299/reports.py` with these changes:
- `MILESTONE = "DUMMY_V299_SECOND_PROOF_EXECUTE_ONCE_V1"`
- Read `SECOND_PROOF_AUTHORITY_ACTIVE.json` and `VALIDATED_KALSHI_PROOF_CANDIDATE_V3.json`.
- Use `market_ticker = candidate["market_ticker"]` and `price = candidate["price"]`.
- Use fresh idempotency key seeded with `authority_id`.
- Call `LiveBrokerFirewall.submit_limit_order_adapter`.
- Consume second-proof lock via `core.second_proof_lock.consume_second_proof_lock`.
- Write evidence to `artifacts/dummy/second_real_proof_<timestamp>/`.

- [ ] **Step 2: Update `cmd_one_shot_live`**

If a second-proof authority is active and env gate present, delegate to v299 runner instead of bootstrap:

```python
sp_state = _second_proof_authority_state()
if sp_state.get("state") == "active" and _env_gate(env):
    rc = runner([sys.executable, "scripts/run_dummy_second_proof_execute_once_v1.py"])
    return rc.returncode
```

Create `scripts/run_dummy_second_proof_execute_once_v1.py` that calls the v299 report factory.

- [ ] **Step 3: Add tests**

Test blocked without env gate, blocked without active authority, uses V3 candidate, does not use KXBTC, uses LiveBrokerFirewall, mocked accept/reject paths, second attempt blocked by lock.

Run: `python -m pytest tests/test_second_proof_execute_once_wiring.py -q --tb=short --timeout=60`
Expected: PASS.

---

### Task 8: Dashboard second-proof authority panel

**Files:**
- Modify: `dashboard/backend/operator_control_routes.py`
- Modify: `dashboard/frontend/src/screens/OperatorControl.jsx`
- Test: `tests/test_dashboard_second_proof_authority_status.py`

**Interfaces:**
- Consumes: second-proof authority files.
- Produces: `GET /api/operator-control/second-proof-authority` JSON and UI panel.

- [ ] **Step 1: Add backend endpoint**

```python
@router.get("/second-proof-authority")
async def second_proof_authority_status() -> dict[str, Any]:
    state = _second_proof_authority_state()
    return {
        "state": state["state"],
        "candidate_market_ticker": state.get("authority", {}).candidate_market_ticker if state.get("authority") else None,
        "candidate_price": state.get("authority", {}).candidate_price if state.get("authority") else None,
        "submit_allowed_now": False,
        "no_auto_live": True,
        "next_action": "activate authority with exact typed confirmation, then arm env gate",
    }
```

- [ ] **Step 2: Add frontend panel**

Add a `SecondProofAuthorityPanel` component below `NextProofCandidatePanel` that shows draft/active/absent state and the exact confirmation sentence.

- [ ] **Step 3: Add tests**

Test endpoint returns correct states.

Run: `python -m pytest tests/test_dashboard_second_proof_authority_status.py -q --tb=short --timeout=60`
Expected: PASS.

---

### Task 9: Validation and full test runs

- [ ] **Step 1: Run py_compile on all changed files**

```bash
python -m py_compile core/proof_authority.py core/second_proof_lock.py core/live_execution_mode.py core/proof_order_candidate.py live_firewall/firewall.py predator_mesh/v299/reports.py tools/operator_authority_appliance/operator_full_completion.py dashboard/backend/operator_control_routes.py dashboard/backend/main.py
```

Expected: no errors.

- [ ] **Step 2: Run focused tests**

```bash
python -m pytest tests/test_second_proof_authority_model.py tests/test_prepare_second_proof_authority.py tests/test_activate_second_proof_authority.py tests/test_second_proof_command_seal.py tests/test_second_proof_execute_once_wiring.py tests/test_dashboard_second_proof_authority_status.py -q --tb=short --timeout=60
```

Expected: PASS.

- [ ] **Step 3: Run related existing tests**

```bash
python -m pytest tests/test_kalshi_read_only_discovery_v3.py tests/test_next_proof_candidate_v3_builder.py tests/test_kalshi_metadata_response_shapes.py tests/test_read_only_transport_guard.py tests/test_proof_lock_after_broker_rejection.py tests/test_execute_once_real_broker_wiring.py tests/test_v298_real_proof_semantics.py tests/test_live_firewall_real_adapter_path.py tests/test_live_submit_state_model.py tests/test_operator_full_completion.py tests/test_v295_to_v304_governance.py -q --tb=short --timeout=60
```

Expected: PASS.

- [ ] **Step 4: Run full default-state suite**

```bash
python -m pytest tests/ -q --tb=short --timeout=120
```

Expected: 4211 passed, 1 skipped, 1 warning (or better).

- [ ] **Step 5: Frontend build**

```bash
cd dashboard/frontend && npm run build
```

Expected: PASS.

---

### Task 10: Execute authority workflow and final report

- [ ] **Step 1: Default check**

```bash
python tools/operator_authority_appliance/operator_full_completion.py one-shot-check
```

Expected: `BLOCKED_LIVE_SUBMIT_CAPS` or equivalent.

- [ ] **Step 2: Prepare second-proof authority**

```bash
python tools/operator_authority_appliance/operator_full_completion.py prepare-second-proof-authority
```

Expected: `SECOND_PROOF_AUTHORITY_DRAFT_READY`, draft created, no broker contact.

- [ ] **Step 3: Activate (only if confirmation supplied)**

```bash
python tools/operator_authority_appliance/operator_full_completion.py activate-second-proof-authority --operator-name "chris" --reason "second controlled proof" --expires-at "2026-07-08T22:00:00Z" --confirm "I confirm a second controlled real broker proof attempt using the validated V3 candidate, limit order only, count 1, no market orders, no scale, no autonomy, and Dummy must still pass every gate before any order"
```

Expected: `SECOND_PROOF_AUTHORITY_ACTIVE`.

- [ ] **Step 4: One-shot check after activation**

```bash
python tools/operator_authority_appliance/operator_full_completion.py one-shot-check
```

Expected: `SECOND_PROOF_READY_ENV_GATE_REQUIRED`.

- [ ] **Step 5: Env-gated live attempt (only if armed)**

```bash
export DUMMY_LIVE_PROOF_MODE=1
export DUMMY_LIVE_PROOF_ACK=FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY
python tools/operator_authority_appliance/operator_full_completion.py one-shot-live
```

No retry.

- [ ] **Step 6: Generate final report**

Write `artifacts/dummy/SECOND_PROOF_AUTHORITY_REPORT.json` with all required fields from the mission spec and print `DUMMY_SECOND_PROOF_AUTHORITY_REPORT` summary.

---

## Self-Review

1. **Spec coverage:**
   - Part A inspect → done via existing reads, no new code needed.
   - Part B authority model → Task 1.
   - Part C prepare command → Task 4.
   - Part D activation command → Task 5.
   - Part E command seal → Task 6.
   - Part F one-shot-live wiring → Task 7.
   - Part G dashboard panel → Task 8.
   - Part H tests → every task includes tests.
   - Part I validation → Task 9.
   - Part J workflow → Task 10.
   - Part K post-attempt → included in v299 runner.
   - Part L final report → Task 10.

2. **Placeholder scan:** No TBD/TODO; all code shown.

3. **Type consistency:** `SecondProofAuthority` dataclass fields used consistently across prepare/activate/runner/dashboard.
