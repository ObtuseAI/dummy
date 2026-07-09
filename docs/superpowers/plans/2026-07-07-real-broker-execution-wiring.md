# Real Broker Execution Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task in this session. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the existing v298 execute-once final proof runner to make exactly one real Kalshi limit-order attempt through `KalshiLiveBrokerFirewallAdapter.submit_limit_order` when all gates pass, and write truthful proof artifacts.

**Architecture:** Add a shared execution-mode classifier in `core/live_execution_mode.py`; add a new `submit_limit_order_adapter` method to `live_firewall/firewall.py` that enforces one-proof policy gates and delegates to the Kalshi adapter; update `predator_mesh/v298/reports.py` to call this method when armed; update `predator_mesh/v304/reports.py` to count real broker rejection as a real attempt; add tests; run validation; attempt one live proof.

**Tech Stack:** Python 3.11+, asyncio, httpx, KalshiClient, existing Dummy repo modules.

## Global Constraints

- No V305+ stage or new architecture ladder.
- No rewrite of `KalshiLiveBrokerFirewallAdapter` unless tests prove it broken.
- No market orders, scale, autonomy, or direct Kalshi bypass.
- No fake proof or counting non-broker doubles as live proof.
- Default-state suite must remain green.
- Secrets never logged or written to artifacts.

---

## File Map

| File | Responsibility |
|------|----------------|
| `core/live_execution_mode.py` (create) | Classify execution mode: default disabled, rehearsal/test double, operator one-proof live ready, invalid/blocked. |
| `live_firewall/firewall.py` (modify) | Add `submit_limit_order_adapter` policy gate + adapter call path; preserve existing evaluate/submit/rehearsal. |
| `predator_mesh/v298/reports.py` (modify) | When armed, build one `LimitOrderRequest`, call firewall adapter path, truthfully report real_broker_contacted/etc. |
| `predator_mesh/v304/reports.py` (modify) | Count real broker rejection as real proof when policy says attempts count. |
| `tests/test_live_execution_mode.py` (create) | Unit tests for mode classifier. |
| `tests/test_execute_once_real_broker_wiring.py` (create) | v298 runner wiring tests with mocked adapter. |
| `tests/test_v298_real_proof_semantics.py` (create) | Artifact semantics tests. |
| `tests/test_live_firewall_real_adapter_path.py` (create) | Firewall adapter path tests. |

---

## Task 1: Execution mode classifier

**Files:**
- Create: `core/live_execution_mode.py`
- Test: `tests/test_live_execution_mode.py`

**Interfaces:**
- Produces: `LiveExecutionMode` enum, `classify_live_execution_mode(...)` returning `(mode, blocker, context)`.

- [ ] **Step 1: Write failing test**

```python
from core.live_execution_mode import classify_live_execution_mode, LiveExecutionMode

def test_default_state_is_disabled(tmp_path):
    config = {"enabled": False}
    mode, blocker, ctx = classify_live_execution_mode(
        live_submit_config=config,
        env={},
        seal_status="PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT",
        caps_strict=True,
        descriptor_staged=True,
        credentials_ready=True,
        proof_lock_clear=True,
    )
    assert mode is LiveExecutionMode.DEFAULT_DISABLED
    assert blocker == "DEFAULT_DISABLED"
```

Run: `python -m pytest tests/test_live_execution_mode.py::test_default_state_is_disabled -v`
Expected: FAIL (module not found)

- [ ] **Step 2: Implement classifier**

```python
from __future__ import annotations

from enum import Enum
from typing import Any

from core.live_submit_state import (
    LIVE_SUBMIT_REQUIRED_ACK,
    validate_default_disabled,
    validate_operator_one_proof_enabled,
)


class LiveExecutionMode(Enum):
    DEFAULT_DISABLED = "default_disabled"
    REHEARSAL_OR_TEST_DOUBLE = "rehearsal_or_test_double"
    OPERATOR_ONE_PROOF_LIVE_READY = "operator_one_proof_live_ready"
    INVALID_OR_BLOCKED = "invalid_or_blocked"


def classify_live_execution_mode(
    live_submit_config: dict[str, Any],
    env: dict[str, str],
    seal_status: str,
    caps_strict: bool,
    descriptor_staged: bool,
    credentials_ready: bool,
    proof_lock_clear: bool,
    authority_context: dict[str, Any] | None = None,
) -> tuple[LiveExecutionMode, str, dict[str, Any]]:
    context: dict[str, Any] = {
        "live_submit_config": live_submit_config,
        "env_mode": env.get("DUMMY_LIVE_PROOF_MODE") == "1",
        "env_ack": env.get("DUMMY_LIVE_PROOF_ACK") == "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY",
        "seal_status": seal_status,
        "caps_strict": caps_strict,
        "descriptor_staged": descriptor_staged,
        "credentials_ready": credentials_ready,
        "proof_lock_clear": proof_lock_clear,
    }

    disabled = validate_default_disabled(live_submit_config)
    if disabled.ok:
        return LiveExecutionMode.DEFAULT_DISABLED, "DEFAULT_DISABLED", context

    enabled = validate_operator_one_proof_enabled(live_submit_config, authority_context=authority_context)
    if not enabled.ok:
        return LiveExecutionMode.INVALID_OR_BLOCKED, "LIVE_SUBMIT_INVALID", {**context, "errors": enabled.errors}

    if not context["env_mode"] or not context["env_ack"]:
        return LiveExecutionMode.INVALID_OR_BLOCKED, "ENV_GATE_MISSING", context

    if seal_status != "PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT":
        return LiveExecutionMode.INVALID_OR_BLOCKED, "COMMAND_SEAL_NOT_READY", context

    if not caps_strict:
        return LiveExecutionMode.INVALID_OR_BLOCKED, "CAPS_NOT_STRICT", context

    if not descriptor_staged:
        return LiveExecutionMode.INVALID_OR_BLOCKED, "ADAPTER_DESCRIPTOR_NOT_STAGED", context

    if not credentials_ready:
        return LiveExecutionMode.INVALID_OR_BLOCKED, "CREDENTIALS_NOT_READY", context

    if not proof_lock_clear:
        return LiveExecutionMode.INVALID_OR_BLOCKED, "PROOF_LOCK_USED", context

    return LiveExecutionMode.OPERATOR_ONE_PROOF_LIVE_READY, "", context
```

- [ ] **Step 3: Run test**

Run: `python -m pytest tests/test_live_execution_mode.py -q --tb=short`
Expected: PASS

---

## Task 2: LiveBrokerFirewall adapter submit path

**Files:**
- Modify: `live_firewall/firewall.py`
- Test: `tests/test_live_firewall_real_adapter_path.py`

**Interfaces:**
- Consumes: `LimitOrderRequest` from `predator_mesh.brokers.livebrokerfirewall_adapter`.
- Produces: `LiveOrderResult` with `success`, `order_id`, `error`.

- [ ] **Step 1: Write failing test**

```python
import pytest
from unittest.mock import AsyncMock
from live_firewall.firewall import LiveBrokerFirewall
from live_firewall.exposure_tracker import ExposureTracker
from predator_mesh.brokers import LimitOrderRequest

@pytest.mark.asyncio
async def test_submit_limit_order_adapter_blocks_when_live_submit_disabled(monkeypatch):
    import core.live_execution_mode as lem
    monkeypatch.setattr(lem, "classify_live_execution_mode", lambda **kw: (lem.LiveExecutionMode.INVALID_OR_BLOCKED, "LIVE_SUBMIT_INVALID", {}))

    fw = LiveBrokerFirewall(kalshi_client=None, exposure_tracker=ExposureTracker())
    req = LimitOrderRequest(
        venue="KALSHI", order_type="LIMIT", market_orders_allowed=False,
        side="yes", action="buy", price=1, quantity=1,
        idempotency_key="idem-1", market_ticker="TEST",
        proof_id="p1", proof_target="FIRST_REAL_PILOT_PROOF",
    )
    result = await fw.submit_limit_order_adapter(req)
    assert result.success is False
    assert "LIVE_SUBMIT_INVALID" in (result.error or "")
```

Run: `python -m pytest tests/test_live_firewall_real_adapter_path.py -v`
Expected: FAIL (method missing)

- [ ] **Step 2: Implement method**

Add imports to top of `live_firewall/firewall.py`:

```python
import asyncio
import hashlib
import json
from pathlib import Path

from core.live_execution_mode import LiveExecutionMode, classify_live_execution_mode
from core.env_loader import kalshi_credential_status
from predator_mesh.brokers import KalshiLiveBrokerFirewallAdapter, LimitOrderRequest
```

Add helper functions and method:

```python
LIVE_SUBMIT_PATH = Path("configs/live_submit.json")
ADAPTER_DESCRIPTOR_PATH = Path("runtime/operator_external/livebrokerfirewall_adapter_descriptor.json")
CAPS_PATH = Path("configs/caps.json")


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _kalshi_credentials_ready() -> bool:
    status = kalshi_credential_status()
    if not status.get("KALSHI_API_KEY_ID", {}).get("present"):
        return False
    key_refs = {
        "KALSHI_API_PRIVATE_KEY_PEM",
        "KALSHI_PRIVATE_KEY",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH",
        "KALSHI_PRIVATE_KEY_PATH",
    }
    for key in key_refs:
        entry = status.get(key, {})
        if not entry.get("present"):
            continue
        if "file_exists" in entry:
            if entry["file_exists"]:
                return True
        else:
            return True
    return False


def _load_live_submit_config() -> dict[str, Any]:
    if not LIVE_SUBMIT_PATH.exists():
        return {"enabled": False}
    try:
        data = json.loads(LIVE_SUBMIT_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"enabled": False}
    except Exception:
        return {"enabled": False}


def _caps_strict() -> bool:
    if not CAPS_PATH.exists():
        return False
    try:
        data = json.loads(CAPS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return False
    limit_only = data.get("order_type_policy") == "LIMIT_ONLY" or data.get("limit_orders_only") is True
    no_market = data.get("market_orders_allowed") is False or data.get("allow_market_orders") is False
    kill_on = data.get("kill_switch_enabled") is True or data.get("kill_switch_required") is True
    order_count_ok = data.get("max_order_count", 1) == 1
    return limit_only and no_market and kill_on and order_count_ok


def _descriptor_staged() -> bool:
    if not ADAPTER_DESCRIPTOR_PATH.exists():
        return False
    try:
        data = json.loads(ADAPTER_DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    except Exception:
        return False
    return (
        data.get("broker") == "KALSHI"
        and data.get("adapter_type") == "LiveBrokerFirewall"
        and data.get("order_type_policy") == "LIMIT_ONLY"
        and data.get("market_orders_allowed") is False
    )


def _command_seal_ready() -> bool:
    v297 = Path("artifacts/dummy/final_report_v297.json")
    if not v297.exists():
        return False
    try:
        data = json.loads(v297.read_text(encoding="utf-8"))
    except Exception:
        return False
    return str(data.get("execute_once_command_seal_controller_status", "")) == "PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT"


def _proof_lock_clear() -> bool:
    v298 = Path("artifacts/dummy/final_report_v298.json")
    if not v298.exists():
        return True
    try:
        data = json.loads(v298.read_text(encoding="utf-8"))
    except Exception:
        return True
    status = str(data.get("execute_once_final_proof_runner_v7_controller_status", ""))
    if status != "PASS_EXECUTE_ONCE_FINAL_PROOF_RUNNER_SUBMITTED_AUTOLOCKED":
        return True
    return not (
        data.get("real_broker_contacted") is True
        or int(data.get("real_live_orders_submitted_count", 0) or 0) > 0
        or data.get("broker_rejection_captured") is True
    )


async def submit_limit_order_adapter(self, req: LimitOrderRequest) -> LiveOrderResult:
    """One-proof live submit through KalshiLiveBrokerFirewallAdapter.

    Fail-closed: any missing gate returns LiveOrderResult(success=False).
    """
    mode, blocker, ctx = classify_live_execution_mode(
        live_submit_config=_load_live_submit_config(),
        env=dict(os.environ),
        seal_status=("PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT" if _command_seal_ready() else "BLOCKED"),
        caps_strict=_caps_strict(),
        descriptor_staged=_descriptor_staged(),
        credentials_ready=_kalshi_credentials_ready(),
        proof_lock_clear=_proof_lock_clear(),
    )

    if mode is LiveExecutionMode.DEFAULT_DISABLED:
        return LiveOrderResult(success=False, error="live_submit_disabled", proof_reference=req.proof_id or "")

    if mode is not LiveExecutionMode.OPERATOR_ONE_PROOF_LIVE_READY:
        logger.info("Live adapter submit blocked", extra={"component": "firewall", "blocker": blocker})
        return LiveOrderResult(success=False, error=blocker, proof_reference=req.proof_id or "")

    # Request-level policy validation (defense in depth).
    if req.order_type.upper() != "LIMIT":
        return LiveOrderResult(success=False, error="MARKET_ORDER_REJECTED", proof_reference=req.proof_id or "")
    if req.market_orders_allowed:
        return LiveOrderResult(success=False, error="MARKET_ORDERS_NOT_ALLOWED", proof_reference=req.proof_id or "")
    if req.max_order_count != 1:
        return LiveOrderResult(success=False, error="MAX_ORDER_COUNT_EXCEEDED", proof_reference=req.proof_id or "")
    if not req.idempotency_key:
        return LiveOrderResult(success=False, error="IDEMPOTENCY_KEY_MISSING", proof_reference=req.proof_id or "")
    if not req.proof_id or not req.proof_target:
        return LiveOrderResult(success=False, error="PROOF_LOCK_INCOMPLETE", proof_reference=req.proof_id or "")
    if req.price * req.quantity > req.max_order_size_cents:
        return LiveOrderResult(success=False, error="ORDER_SIZE_CAP_EXCEEDED", proof_reference=req.proof_id or "")

    adapter = KalshiLiveBrokerFirewallAdapter(
        live_submit_enabled=True,
        caps_confirmed=True,
        kill_switch_active=STATE.kill_switch.active,
        command_seal_ready=True,
        resolver_armable=True,
        require_proof_lock=False,  # lock handled by _proof_lock_clear and adapter's _attempted
    )

    try:
        submit_result = await adapter.submit_limit_order(req)
    except Exception as exc:
        logger.error("Adapter submit raised", extra={"component": "firewall", "error": str(exc)})
        return LiveOrderResult(success=False, error=f"ADAPTER_EXCEPTION:{type(exc).__name__}", proof_reference=req.proof_id or "")
    finally:
        await adapter.close()

    if submit_result.submitted and submit_result.order_id:
        self.exposure.record_order(req.market_ticker, req.quantity, req.price)
        self.exposure.add_open_order(submit_result.order_id, req.market_ticker, req.quantity, req.price)
        self.exposure.update_position(Position(
            market_ticker=req.market_ticker,
            contract_ticker=req.market_ticker,
            side=req.side,
            quantity=req.quantity,
            avg_price_cents=req.price,
            unrealized_pnl_cents=0,
        ))
        return LiveOrderResult(success=True, order_id=submit_result.order_id, proof_reference=req.proof_id or "")

    return LiveOrderResult(success=False, order_id=submit_result.order_id, error="BROKER_REJECTED", proof_reference=req.proof_id or "")
```

- [ ] **Step 3: Run test**

Run: `python -m pytest tests/test_live_firewall_real_adapter_path.py -q --tb=short`
Expected: PASS

---

## Task 3: v298 runner real submit wiring

**Files:**
- Modify: `predator_mesh/v298/reports.py`
- Test: `tests/test_execute_once_real_broker_wiring.py`, `tests/test_v298_real_proof_semantics.py`

**Interfaces:**
- Consumes: `LiveBrokerFirewall.submit_limit_order_adapter`, `LimitOrderRequest`.
- Produces: v298 controller dict with truthful `real_broker_contacted`, `real_live_orders_submitted_count`, `broker_rejection_captured`, `non_broker_double_used`, `proof_is_real`.

- [ ] **Step 1: Add helper to build idempotency key and order**

In `predator_mesh/v298/reports.py`, add imports:

```python
import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.env_loader import kalshi_credential_status
from core.live_execution_mode import LiveExecutionMode, classify_live_execution_mode
from live_firewall.exposure_tracker import ExposureTracker
from live_firewall.firewall import LiveBrokerFirewall
from predator_mesh.brokers import LimitOrderRequest
```

Add constants and helpers:

```python
LIVE_PROOF_ACK = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"
ADAPTER_DESCRIPTOR_PATH = Path("runtime/operator_external/livebrokerfirewall_adapter_descriptor.json")
CAPS_PATH = Path("configs/caps.json")
LIVE_SUBMIT_PATH = Path("configs/live_submit.json")


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _kalshi_credentials_ready() -> bool:
    status = kalshi_credential_status()
    if not status.get("KALSHI_API_KEY_ID", {}).get("present"):
        return False
    key_refs = {
        "KALSHI_API_PRIVATE_KEY_PEM",
        "KALSHI_PRIVATE_KEY",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH",
        "KALSHI_PRIVATE_KEY_PATH",
    }
    for key in key_refs:
        entry = status.get(key, {})
        if not entry.get("present"):
            continue
        if "file_exists" in entry:
            if entry["file_exists"]:
                return True
        else:
            return True
    return False


def _load_live_submit_config() -> dict[str, Any]:
    if not LIVE_SUBMIT_PATH.exists():
        return {"enabled": False}
    try:
        data = json.loads(LIVE_SUBMIT_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"enabled": False}
    except Exception:
        return {"enabled": False}


def _caps_strict() -> bool:
    if not CAPS_PATH.exists():
        return False
    try:
        data = json.loads(CAPS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return False
    limit_only = data.get("order_type_policy") == "LIMIT_ONLY" or data.get("limit_orders_only") is True
    no_market = data.get("market_orders_allowed") is False or data.get("allow_market_orders") is False
    kill_on = data.get("kill_switch_enabled") is True or data.get("kill_switch_required") is True
    order_count_ok = data.get("max_order_count", 1) == 1
    return limit_only and no_market and kill_on and order_count_ok


def _descriptor_staged() -> bool:
    if not ADAPTER_DESCRIPTOR_PATH.exists():
        return False
    try:
        data = json.loads(ADAPTER_DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    except Exception:
        return False
    return (
        data.get("broker") == "KALSHI"
        and data.get("adapter_type") == "LiveBrokerFirewall"
        and data.get("order_type_policy") == "LIMIT_ONLY"
        and data.get("market_orders_allowed") is False
    )


def _proof_lock_clear() -> bool:
    v298 = Path("artifacts/dummy/final_report_v298.json")
    if not v298.exists():
        return True
    try:
        data = json.loads(v298.read_text(encoding="utf-8"))
    except Exception:
        return True
    status = str(data.get("execute_once_final_proof_runner_v7_controller_status", ""))
    if status != "PASS_EXECUTE_ONCE_FINAL_PROOF_RUNNER_SUBMITTED_AUTOLOCKED":
        return True
    return not (
        data.get("real_broker_contacted") is True
        or int(data.get("real_live_orders_submitted_count", 0) or 0) > 0
        or data.get("broker_rejection_captured") is True
    )


def _idempotency_key(proof_id: str, nonce: str) -> str:
    descriptor_hash = _sha256_file(ADAPTER_DESCRIPTOR_PATH) or ""
    caps_hash = _sha256_file(CAPS_PATH) or ""
    live_submit_hash = _sha256_file(LIVE_SUBMIT_PATH) or ""
    payload = f"{proof_id}|{descriptor_hash}|{caps_hash}|{live_submit_hash}|{nonce}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _build_limit_order_request(proof_id: str, market_ticker: str, nonce: str) -> LimitOrderRequest:
    return LimitOrderRequest(
        venue="KALSHI",
        order_type="LIMIT",
        market_orders_allowed=False,
        side="yes",
        action="buy",
        price=1,
        quantity=1,
        idempotency_key=_idempotency_key(proof_id, nonce),
        market_ticker=market_ticker,
        proof_id=proof_id,
        proof_target="FIRST_REAL_PILOT_PROOF",
        client_order_id=_idempotency_key(proof_id, nonce),
        max_order_count=1,
        max_order_size_cents=100,
    )
```

- [ ] **Step 2: Modify `_controller` armed path**

Replace the armed success branch (the final `return {...}` in `_controller`) with:

```python
    # Armed: all gates passed. Attempt exactly one real broker submit.
    proof_id = f"v298-{MILESTONE}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    market_ticker = "KXBTC-26DEC25000-C"  # smallest-proof conservative default; discovery preferred

    req = _build_limit_order_request(proof_id, market_ticker, nonce=proof_id)
    firewall = LiveBrokerFirewall(kalshi_client=None, exposure_tracker=ExposureTracker())
    try:
        result = asyncio.run(firewall.submit_limit_order_adapter(req))
    except Exception as exc:
        result = LiveOrderResult(success=False, error=f"RUNNER_EXCEPTION:{type(exc).__name__}", proof_reference=proof_id)

    real_broker_contacted = bool(result.success or (result.error and result.error == "BROKER_REJECTED"))
    real_live_orders_submitted_count = 1 if result.success and result.order_id else 0
    broker_rejection_captured = bool(not result.success and result.error == "BROKER_REJECTED")
    broker_order_id = result.order_id if result.success else None
    non_broker_double_used = False
    proof_is_real = real_broker_contacted

    return {
        "status": "PASS_EXECUTE_ONCE_FINAL_PROOF_RUNNER_SUBMITTED_AUTOLOCKED",
        "verdict": "PASS",
        "fields": {
            "arm_state": "SUBMITTED_AUTOLOCKED_REAL_BROKER_ATTEMPT",
            "fixture_only": False,
            "uses_non_broker_double": False,
            "submitted_autolocked": True,
            "real_live_orders": real_live_orders_submitted_count,
            "real_live_orders_submitted_count": real_live_orders_submitted_count,
            "real_broker_contacted": real_broker_contacted,
            "broker_rejection_captured": broker_rejection_captured,
            "broker_order_id": broker_order_id,
            "market_order_submitted": False,
            "max_attempts": 1,
            "fixture_proof_inflates_real_score": False,
            "no_fixture_inflation_proof_status": "PASS_NO_FIXTURE_INFLATION",
            "no_submit_proof_status": "PASS_NO_SUBMIT" if real_live_orders_submitted_count == 0 else "PASS_SUBMIT",
            "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT" if not real_broker_contacted else "PASS_BROKER_CONTACT",
            "non_broker_double_used": non_broker_double_used,
            "proof_is_real": proof_is_real,
            "idempotency_key": req.idempotency_key,
            "proof_id": proof_id,
            "market_ticker": market_ticker,
        },
        "blockers": [],
        "next_action": "EXECUTE_ONCE_FINAL_PROOF_RUNNER_SUBMITTED_AUTOLOCKED_REAL_PROOF_NEXT_RUN_POST_PROOF_AUTO_INTAKE_NO_NEW_ORDER",
    }
```

Add `LiveOrderResult` import:

```python
from core.ontology import LiveOrderResult
```

- [ ] **Step 3: Update blocked/armed-not-ready branches**

Ensure blocked branches set `non_broker_double_used=False` and `real_broker_contacted=False` where appropriate. The existing blocked branches already set `fixture_only=True` and `real_live_orders_submitted=0`; update them to also set `non_broker_double_used=False` and `broker_rejection_captured=False`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_execute_once_real_broker_wiring.py tests/test_v298_real_proof_semantics.py -q --tb=short`
Expected: PASS

---

## Task 4: v304 completion lift real-rejection counting

**Files:**
- Modify: `predator_mesh/v304/reports.py`

- [ ] **Step 1: Update `v298_real_proof` predicate**

Change:

```python
    v298_real_proof = (
        runner_built
        and str(v298.get("execute_once_final_proof_runner_v7_controller_status", "")) == "PASS_EXECUTE_ONCE_FINAL_PROOF_RUNNER_SUBMITTED_AUTOLOCKED"
        and v298.get("real_broker_contacted") is True
        and int(v298.get("real_live_orders_submitted_count", 0) or 0) > 0
    )
```

To:

```python
    v298_real_proof = (
        runner_built
        and str(v298.get("execute_once_final_proof_runner_v7_controller_status", "")) == "PASS_EXECUTE_ONCE_FINAL_PROOF_RUNNER_SUBMITTED_AUTOLOCKED"
        and v298.get("non_broker_double_used") is False
        and v298.get("real_broker_contacted") is True
        and (
            int(v298.get("real_live_orders_submitted_count", 0) or 0) > 0
            or v298.get("broker_rejection_captured") is True
        )
    )
```

- [ ] **Step 2: Run v304 tests**

Run: `python -m pytest tests/test_v295_to_v304_governance.py -q --tb=short`
Expected: PASS

---

## Task 5: Validation and live proof attempt

- [ ] **Step 1: py_compile**

Run:
```bash
python -m py_compile dashboard/backend/operator_control_routes.py dashboard/backend/main.py
python -m py_compile predator_mesh/brokers/livebrokerfirewall_adapter.py predator_mesh/brokers/kalshi_livebrokerfirewall_adapter.py
python -m py_compile live_firewall/firewall.py
python -m py_compile scripts/generate_v298_reports.py
python -m py_compile predator_mesh/v304/reports.py
python -m py_compile core/live_execution_mode.py
python -m py_compile predator_mesh/v298/reports.py
```
Expected: no errors.

- [ ] **Step 2: Focused tests**

Run:
```bash
python -m pytest tests/test_kalshi_livebrokerfirewall_adapter.py -q --tb=short --timeout=60
python -m pytest tests/test_livebrokerfirewall_adapter_contract.py -q --tb=short --timeout=60
python -m pytest tests/test_live_submit_state_model.py -q --tb=short --timeout=60
python -m pytest tests/test_execute_once_real_broker_wiring.py -q --tb=short --timeout=60
python -m pytest tests/test_v298_real_proof_semantics.py -q --tb=short --timeout=60
python -m pytest tests/test_live_firewall_real_adapter_path.py -q --tb=short --timeout=60
python -m pytest tests/test_operator_control_external_prereqs.py -q --tb=short --timeout=60
python -m pytest tests/test_operator_control_routes.py -q --tb=short --timeout=60
python -m pytest tests/test_operator_full_completion.py -q --tb=short --timeout=60
python -m pytest tests/test_v295_to_v304_governance.py -q --tb=short --timeout=60
```
Expected: PASS.

- [ ] **Step 3: Full default-state suite**

Run:
```bash
python -m pytest tests/ -q --tb=short --timeout=120
```
Expected: ~4095 passed, 2 skipped, 1 warning.

- [ ] **Step 4: Frontend build**

Run:
```bash
cd dashboard/frontend && npm run build
```
Expected: PASS.

- [ ] **Step 5: Enable one-proof live-submit**

Run:
```bash
python tools/operator_authority_appliance/operator_full_completion.py enable-one-proof-live-submit \
  --operator "chris" \
  --reason "one controlled proof" \
  --expires-at "2099-01-01T00:00:00Z" \
  --typed-confirmation "I confirm live-submit is enabled for one controlled proof only and Dummy must still pass all gates before any order"
```
Expected: `LIVE_SUBMIT_ENABLED_ONE_PROOF`.

- [ ] **Step 6: one-shot-check**

Run:
```bash
python tools/operator_authority_appliance/operator_full_completion.py one-shot-check
```
Expected: `COMMAND_SEAL_READY_ENV_GATE_REQUIRED`.

- [ ] **Step 7: one-shot-live**

Run in PowerShell:
```powershell
$env:DUMMY_LIVE_PROOF_MODE="1"
$env:DUMMY_LIVE_PROOF_ACK="FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"
python tools/operator_authority_appliance/operator_full_completion.py one-shot-live
```
Expected: `EXECUTE_ONCE_INVOKED_THEN_POST_PROOF` and v298 artifact updated.

- [ ] **Step 8: Post-proof pipeline**

Confirm these ran as part of one-shot-live:
- `scripts/run_dummy_post_proof_auto_intake_v4.py`
- `scripts/run_dummy_reconcile_forensic_auto_orchestrator_v6.py`
- `scripts/run_dummy_post_proof_route_autopilot.py`
- `scripts/run_dummy_completion_lift_v10.py`

- [ ] **Step 9: Restore default disabled baseline**

Run:
```bash
python tools/operator_authority_appliance/operator_full_completion.py disable-live-submit
```
Expected: `LIVE_SUBMIT_DISABLED`.

- [ ] **Step 10: Re-run default-state suite**

Run:
```bash
python -m pytest tests/ -q --tb=short --timeout=120
```
Expected: still green.

---

## Spec Coverage Check

- Live execution modes: Task 1.
- Firewall adapter submit path with all gates: Task 2.
- v298 runner truthfully reports real broker contact/order/rejection: Task 3.
- v304 lift counts real rejection: Task 4.
- Tests for all semantic cases: Tasks 1-4.
- Validation and one live attempt: Task 5.
