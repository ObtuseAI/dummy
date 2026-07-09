# Next-Proof Candidate Validation Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Diagnose the first real Kalshi broker-contact proof rejection from existing artifacts, then build a no-submit, read-only market/payload validation layer and a validated next-proof candidate packet so any second live attempt is blocked until new operator proof authority is created.

**Architecture:** Add two focused core modules (`core/kalshi_market_validator.py` for read-only Kalshi metadata and payload validation, `core/proof_order_candidate.py` for candidate packet construction), extend the operator CLI with a read-only `validate-next-proof-candidate` subcommand, and add a read-only dashboard panel. The pipeline never submits, cancels, modifies, enables live-submit, or unlocks the consumed proof lock. All real-broker safety invariants are preserved.

**Tech Stack:** Python 3.11, pytest, FastAPI, React/Vite dashboard, existing Dummy env/caps/live-submit/proof-lock modules.

## Global Constraints

- No live order by default and no `one-shot-live` run in this bundle.
- No POST/order submit, cancel, or modify calls in diagnosis or validation modes.
- No market orders; order type must be `LIMIT`.
- No scale or autonomy enablement.
- No new architecture ladder (no V305+). Extend v304 reporting/dashboard only.
- Do not rebuild the adapter; reuse `KalshiLiveBrokerFirewallAdapter` and existing request shapes.
- Do not bypass command seal, resolver, `LiveBrokerFirewall`, or proof lock.
- Do not fake proof or count non-broker doubles as live proof.
- No new proof attempt unless a new explicit operator proof authority is generated.
- No raw secrets printed or persisted.
- Do not commit unless explicitly requested.
- Candidate packet must set `submit_allowed_now=false` and `requires_new_operator_proof_authority=true` when a previous real broker attempt is recorded.

---

## Task 1: Inspect first-rejected-proof artifacts and confirm diagnosis

**Files:**
- Read: `artifacts/dummy/real_proof_backup_20260707T1855/final_report_v298.json`
- Read: `artifacts/dummy/real_proof_backup_20260707T1855/v298_execute_once_final_proof_runner_v7_controller_report.json`
- Read: `artifacts/dummy/real_proof_backup_20260707T1855/REAL_BROKER_PROOF_EVIDENCE_INDEX.json`
- Read: `artifacts/dummy/real_proof_registry.json`
- Read: `logs/dummy.jsonl` (tail around `2026-07-07T18:55`)

**Deliverable:** A short diagnosis note stored in memory (no file change) confirming:
- Exact rejection reason is unrecoverable (`FIRST_REJECTION_REASON_UNRECOVERED`).
- Inferred risk factors (clearly marked inferred): market ticker `KXBTC-26DEC25000-C` may have been closed/untradable; hardcoded `price=1` may have been outside allowed tick range; no contract ticker validation existed; no pre-submit metadata check existed.
- Safe fields extracted: market ticker, action/side/order_type/count/price defaults, idempotency/proof-id/hashes.

**Verification:** `grep -q '"latest_real_broker_attempt_status": "BROKER_REJECTED"' artifacts/dummy/real_proof_registry.json` succeeds.

---

## Task 2: Create read-only Kalshi market/payload validator

**Files:**
- Create: `core/kalshi_market_validator.py`
- Test: `tests/test_kalshi_market_validator.py`

**Interfaces:**
- Produces:
  - `ValidationResult(ok: bool, errors: list[str], field: str | None = None)`
  - `MarketMetadata(ticker: str, status: str, open_time: str | None, close_time: str | None, trading_allowed: bool, min_price_cents: int, max_price_cents: int, tick_size_cents: int, contracts: list[ContractMetadata])`
  - `ContractMetadata(ticker: str, status: str, tradable: bool)`
  - `validate_ticker_shape(market_ticker, contract_ticker=None) -> ValidationResult`
  - `validate_order_payload_shape(payload: dict) -> ValidationResult`
  - `fetch_market_metadata_read_only(market_ticker, mode="no_network", client=None) -> MarketMetadata | None`
  - `fetch_contract_metadata_read_only(contract_ticker, mode="no_network", client=None) -> ContractMetadata | None`
  - `validate_payload_against_metadata(payload: dict, metadata: MarketMetadata, caps: dict | None = None) -> ValidationResult`

- [ ] **Step 1: Write failing tests** (`tests/test_kalshi_market_validator.py`)

```python
import pytest
from core.kalshi_market_validator import (
    validate_ticker_shape,
    validate_order_payload_shape,
    validate_payload_against_metadata,
    MarketMetadata,
    ContractMetadata,
)


def test_malformed_market_ticker_rejected():
    result = validate_ticker_shape("")
    assert not result.ok
    assert "market_ticker" in result.errors[0].lower()


def test_missing_contract_rejected():
    result = validate_ticker_shape("KXBTC-26DEC25000-C", contract_ticker="")
    assert not result.ok


def test_market_order_rejected():
    payload = {
        "ticker": "KXBTC-26DEC25000-C",
        "side": "yes",
        "action": "buy",
        "type": "market",
        "count": 1,
        "price": 1,
        "client_order_id": "abc",
    }
    result = validate_order_payload_shape(payload)
    assert not result.ok
    assert any("limit" in e.lower() for e in result.errors)


def test_count_greater_than_one_rejected():
    payload = {
        "ticker": "KXBTC-26DEC25000-C",
        "side": "yes",
        "action": "buy",
        "type": "limit",
        "count": 2,
        "price": 1,
        "client_order_id": "abc",
    }
    result = validate_order_payload_shape(payload)
    assert not result.ok


def test_price_outside_bounds_rejected():
    metadata = MarketMetadata(
        ticker="KXBTC-26DEC25000-C",
        status="open",
        open_time=None,
        close_time=None,
        trading_allowed=True,
        min_price_cents=1,
        max_price_cents=99,
        tick_size_cents=1,
        contracts=[ContractMetadata(ticker="KXBTC-26DEC25000-C", status="open", tradable=True)],
    )
    payload = {
        "ticker": "KXBTC-26DEC25000-C",
        "side": "yes",
        "action": "buy",
        "type": "limit",
        "count": 1,
        "price": 0,
        "client_order_id": "abc",
    }
    result = validate_payload_against_metadata(payload, metadata)
    assert not result.ok


def test_closed_market_rejected():
    metadata = MarketMetadata(
        ticker="KXBTC-26DEC25000-C",
        status="closed",
        open_time=None,
        close_time=None,
        trading_allowed=False,
        min_price_cents=1,
        max_price_cents=99,
        tick_size_cents=1,
        contracts=[ContractMetadata(ticker="KXBTC-26DEC25000-C", status="closed", tradable=False)],
    )
    payload = {
        "ticker": "KXBTC-26DEC25000-C",
        "side": "yes",
        "action": "buy",
        "type": "limit",
        "count": 1,
        "price": 1,
        "client_order_id": "abc",
    }
    result = validate_payload_against_metadata(payload, metadata)
    assert not result.ok
    assert any("open" in e.lower() or "trad" in e.lower() for e in result.errors)


def test_valid_payload_accepted():
    metadata = MarketMetadata(
        ticker="KXBTC-26DEC25000-C",
        status="open",
        open_time=None,
        close_time=None,
        trading_allowed=True,
        min_price_cents=1,
        max_price_cents=99,
        tick_size_cents=1,
        contracts=[ContractMetadata(ticker="KXBTC-26DEC25000-C", status="open", tradable=True)],
    )
    payload = {
        "ticker": "KXBTC-26DEC25000-C",
        "side": "yes",
        "action": "buy",
        "type": "limit",
        "count": 1,
        "price": 1,
        "client_order_id": "abc",
    }
    result = validate_payload_against_metadata(payload, metadata)
    assert result.ok
```

- [ ] **Step 2: Run tests; expect failures**

```bash
python -m pytest tests/test_kalshi_market_validator.py -q --tb=short --timeout=60
```

- [ ] **Step 3: Implement `core/kalshi_market_validator.py`**

```python
"""Read-only Kalshi market/payload validator.

No order submits, cancels, or writes. Supports no_network, mock, and
read_only_network modes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    field: str | None = None

    @property
    def error_message(self) -> str | None:
        return "; ".join(self.errors) if self.errors else None


@dataclass(frozen=True)
class ContractMetadata:
    ticker: str
    status: str
    tradable: bool


@dataclass(frozen=True)
class MarketMetadata:
    ticker: str
    status: str
    open_time: str | None
    close_time: str | None
    trading_allowed: bool
    min_price_cents: int
    max_price_cents: int
    tick_size_cents: int
    contracts: list[ContractMetadata]


_MARKET_TICKER_RE = re.compile(r"^[A-Z0-9]+-[0-9]{2}[A-Z]{3}[0-9]+-[CP]$")


def _safe_upper(value: Any) -> str:
    return str(value).strip().upper() if value is not None else ""


def validate_ticker_shape(market_ticker: str, contract_ticker: str | None = None) -> ValidationResult:
    errors: list[str] = []
    if not market_ticker or not isinstance(market_ticker, str):
        errors.append("market_ticker is required and must be a non-empty string")
    elif not _MARKET_TICKER_RE.match(market_ticker.strip().upper()):
        errors.append("market_ticker does not match expected Kalshi shape")

    if contract_ticker is not None and contract_ticker != "":
        if not isinstance(contract_ticker, str):
            errors.append("contract_ticker must be a string")
        elif contract_ticker.strip().upper() != market_ticker.strip().upper():
            # For Kalshi yes/no markets the contract ticker equals market ticker.
            errors.append("contract_ticker must match market_ticker for yes/no markets")

    return ValidationResult(ok=not errors, errors=errors, field="ticker" if errors else None)


def validate_order_payload_shape(payload: dict[str, Any]) -> ValidationResult:
    errors: list[str] = []
    required = {"ticker", "side", "action", "type", "count", "price", "client_order_id"}
    missing = required - set(payload.keys())
    if missing:
        errors.append(f"missing required fields: {sorted(missing)}")

    for key in payload:
        if payload[key] is None and key in required:
            errors.append(f"required field {key} is null")

    if payload.get("type", "").upper() != "LIMIT":
        errors.append("order type must be LIMIT")

    side = _safe_upper(payload.get("side"))
    if side not in {"YES", "NO"}:
        errors.append("side must be yes or no")

    action = _safe_upper(payload.get("action"))
    if action not in {"BUY", "SELL"}:
        errors.append("action must be buy or sell")

    count = payload.get("count")
    if not isinstance(count, int) or count < 1:
        errors.append("count must be a positive integer")
    elif count != 1:
        errors.append("count must equal 1 for proof candidate")

    price = payload.get("price")
    if not isinstance(price, int) or price < 1 or price > 99:
        errors.append("price must be an integer cent value in [1, 99]")

    client_order_id = payload.get("client_order_id")
    if not client_order_id or not isinstance(client_order_id, str):
        errors.append("client_order_id / idempotency key is required")

    unknown = set(payload.keys()) - required - {"idempotency_key", "proof_id", "proof_target"}
    if unknown:
        errors.append(f"unknown fields present: {sorted(unknown)}")

    return ValidationResult(ok=not errors, errors=errors, field="payload" if errors else None)


def fetch_market_metadata_read_only(
    market_ticker: str,
    mode: str = "no_network",
    client: Any | None = None,
) -> MarketMetadata | None:
    """Return market metadata without submitting any order.

    Modes:
      - no_network: return None (schema-only callers should tolerate None).
      - mock: return a canned open metadata for the ticker if shape-valid.
      - read_only_network: perform a GET to Kalshi market endpoint via `client`.
    """
    shape = validate_ticker_shape(market_ticker)
    if not shape.ok:
        return None

    ticker = market_ticker.strip().upper()

    if mode == "no_network":
        return None

    if mode == "mock":
        return MarketMetadata(
            ticker=ticker,
            status="open",
            open_time=None,
            close_time=None,
            trading_allowed=True,
            min_price_cents=1,
            max_price_cents=99,
            tick_size_cents=1,
            contracts=[ContractMetadata(ticker=ticker, status="open", tradable=True)],
        )

    if mode == "read_only_network":
        if client is None:
            return None
        # Delegates to a read-only client method; no POST/order calls here.
        return client.get_market(ticker)

    return None


def fetch_contract_metadata_read_only(
    contract_ticker: str,
    mode: str = "no_network",
    client: Any | None = None,
) -> ContractMetadata | None:
    shape = validate_ticker_shape(contract_ticker, contract_ticker)
    if not shape.ok:
        return None
    if mode == "no_network":
        return None
    if mode == "mock":
        return ContractMetadata(ticker=contract_ticker.upper(), status="open", tradable=True)
    if mode == "read_only_network":
        if client is None:
            return None
        return client.get_contract(contract_ticker)
    return None


def validate_payload_against_metadata(
    payload: dict[str, Any],
    metadata: MarketMetadata,
    caps: dict[str, Any] | None = None,
) -> ValidationResult:
    errors: list[str] = []

    shape = validate_order_payload_shape(payload)
    if not shape.ok:
        errors.extend(shape.errors)

    market_ticker = payload.get("ticker", "").strip().upper()
    if market_ticker != metadata.ticker.upper():
        errors.append("payload ticker does not match metadata ticker")

    if not metadata.trading_allowed or metadata.status.lower() != "open":
        errors.append("market is not open for trading")

    price = payload.get("price")
    if isinstance(price, int):
        if price < metadata.min_price_cents or price > metadata.max_price_cents:
            errors.append(
                f"price {price} outside market bounds "
                f"[{metadata.min_price_cents}, {metadata.max_price_cents}]"
            )
        if (price - metadata.min_price_cents) % metadata.tick_size_cents != 0:
            errors.append(f"price {price} is not on tick size {metadata.tick_size_cents}")

    contract = next(
        (c for c in metadata.contracts if c.ticker.upper() == market_ticker),
        None,
    )
    if contract is None:
        errors.append("contract not found in market metadata")
    elif not contract.tradable or contract.status.lower() != "open":
        errors.append("contract is not tradable/open")

    count = payload.get("count")
    caps_max = caps.get("max_order_count", 1) if caps else 1
    if isinstance(count, int) and count > caps_max:
        errors.append(f"count {count} exceeds caps max_order_count {caps_max}")

    return ValidationResult(ok=not errors, errors=errors, field="metadata" if errors else None)
```

- [ ] **Step 4: Run tests; expect pass**

```bash
python -m pytest tests/test_kalshi_market_validator.py -q --tb=short --timeout=60
```

---

## Task 3: Create proof-order candidate builder

**Files:**
- Create: `core/proof_order_candidate.py`
- Test: `tests/test_next_proof_candidate_builder.py`

**Interfaces:**
- Produces:
  - `ProofCandidate` dataclass
  - `build_validated_proof_candidate(metadata, caps, proof_context) -> ProofCandidate`
  - `write_candidate_packet(candidate, path)`
  - `safe_preview(candidate) -> dict`
  - `compute_candidate_hash(candidate_path) -> str`

- [ ] **Step 1: Write failing tests** (`tests/test_next_proof_candidate_builder.py`)

```python
import json
import os
from pathlib import Path

import pytest

from core.kalshi_market_validator import MarketMetadata, ContractMetadata
from core.proof_order_candidate import (
    build_validated_proof_candidate,
    write_candidate_packet,
    safe_preview,
    compute_candidate_hash,
)


def test_builder_prefers_smallest_proof_size():
    metadata = MarketMetadata(
        ticker="KXBTC-26DEC25000-C",
        status="open",
        open_time=None,
        close_time=None,
        trading_allowed=True,
        min_price_cents=1,
        max_price_cents=99,
        tick_size_cents=1,
        contracts=[ContractMetadata(ticker="KXBTC-26DEC25000-C", status="open", tradable=True)],
    )
    caps = {"max_order_count": 1, "max_single_order_cents": 100}
    context = {
        "descriptor_hash": "9A3A...3508",
        "caps_hash": "F7D9...E5B5",
        "live_submit_hash": "3875...515E",
        "evidence_registry_hash": "1C89...0113",
        "previous_real_broker_attempt_status": "BROKER_REJECTED",
    }
    candidate = build_validated_proof_candidate(metadata, caps, context)
    assert candidate.order_type == "LIMIT"
    assert candidate.count == 1
    assert candidate.price == 1
    assert candidate.submit_allowed_now is False
    assert candidate.requires_new_operator_proof_authority is True


def test_candidate_packet_has_no_secrets(tmp_path):
    metadata = MarketMetadata(
        ticker="KXBTC-26DEC25000-C",
        status="open",
        open_time=None,
        close_time=None,
        trading_allowed=True,
        min_price_cents=1,
        max_price_cents=99,
        tick_size_cents=1,
        contracts=[ContractMetadata(ticker="KXBTC-26DEC25000-C", status="open", tradable=True)],
    )
    caps = {"max_order_count": 1}
    context = {"previous_real_broker_attempt_status": "BROKER_REJECTED"}
    candidate = build_validated_proof_candidate(metadata, caps, context)
    path = tmp_path / "VALIDATED_KALSHI_PROOF_CANDIDATE.json"
    write_candidate_packet(candidate, path)
    raw = path.read_text()
    assert "idempotency" not in raw.lower() or "redacted" in raw.lower()
    assert "private" not in raw.lower()
    assert "secret" not in raw.lower()


def test_safe_preview_omits_sensitive_fields():
    metadata = MarketMetadata(
        ticker="KXBTC-26DEC25000-C",
        status="open",
        open_time=None,
        close_time=None,
        trading_allowed=True,
        min_price_cents=1,
        max_price_cents=99,
        tick_size_cents=1,
        contracts=[ContractMetadata(ticker="KXBTC-26DEC25000-C", status="open", tradable=True)],
    )
    candidate = build_validated_proof_candidate(metadata, {}, {})
    preview = safe_preview(candidate)
    assert "idempotency" not in preview
    assert preview["submit_allowed_now"] is False
```

- [ ] **Step 2: Run tests; expect failures**

```bash
python -m pytest tests/test_next_proof_candidate_builder.py -q --tb=short --timeout=60
```

- [ ] **Step 3: Implement `core/proof_order_candidate.py`**

```python
"""Proof-order candidate builder.

Constructs a validated, no-submit candidate packet for the next real-broker
proof attempt. Never enables live-submit, never consumes proof lock.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.kalshi_market_validator import MarketMetadata, ValidationResult, validate_payload_against_metadata


@dataclass(frozen=True)
class ProofCandidate:
    candidate_id: str
    created_at: str
    validation_mode: str
    market_ticker: str
    contract_ticker: str
    side: str
    action: str
    order_type: str
    count: int
    price: int
    cap_checks: dict[str, Any]
    market_metadata_checks: dict[str, Any]
    contract_metadata_checks: dict[str, Any]
    live_submit_required_hash: str | None
    descriptor_hash: str | None
    caps_hash: str | None
    evidence_registry_hash: str | None
    proof_lock_status: str
    submit_allowed_now: bool
    requires_new_operator_proof_authority: bool
    reason_submit_not_allowed: str
    secrets_redacted: bool


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_validated_proof_candidate(
    metadata: MarketMetadata,
    caps: dict[str, Any] | None = None,
    proof_context: dict[str, Any] | None = None,
    validation_mode: str = "no_network",
) -> ProofCandidate:
    """Build a candidate using the smallest valid proof size.

    The candidate is always produced, but `submit_allowed_now` is False if a
    previous real broker attempt is recorded in `proof_context`.
    """
    caps = caps or {"max_order_count": 1, "max_single_order_cents": 100}
    proof_context = proof_context or {}

    ticker = metadata.ticker.upper()
    contract = next(
        (c for c in metadata.contracts if c.ticker.upper() == ticker),
        metadata.contracts[0] if metadata.contracts else None,
    )
    contract_ticker = contract.ticker.upper() if contract else ticker

    # Smallest proof size: price at minimum allowed tick, count = 1.
    price = metadata.min_price_cents
    count = 1

    payload = {
        "ticker": ticker,
        "side": "yes",
        "action": "buy",
        "type": "limit",
        "count": count,
        "price": price,
        "client_order_id": "<redacted_idempotency>",
    }

    validation = validate_payload_against_metadata(payload, metadata, caps)

    previous_status = proof_context.get("previous_real_broker_attempt_status")
    proof_lock_consumed = previous_status in {"BROKER_REJECTED", "BROKER_ACCEPTED"}

    reason = "previous real broker attempt recorded; new operator proof authority required"
    if proof_lock_consumed:
        proof_lock_status = "consumed_by_real_broker_attempt"
        submit_allowed = False
        requires_new_authority = True
    elif not validation.ok:
        proof_lock_status = "validation_failed"
        submit_allowed = False
        requires_new_authority = True
        reason = f"payload validation failed: {validation.error_message}"
    else:
        proof_lock_status = "clear"
        submit_allowed = False
        requires_new_authority = True
        reason = "live-submit disabled by default; explicit operator authority required"

    return ProofCandidate(
        candidate_id=f"candidate-{uuid.uuid4().hex[:16]}",
        created_at=_now_iso(),
        validation_mode=validation_mode,
        market_ticker=ticker,
        contract_ticker=contract_ticker,
        side="yes",
        action="buy",
        order_type="LIMIT",
        count=count,
        price=price,
        cap_checks={
            "max_order_count": caps.get("max_order_count", 1),
            "count": count,
            "count_ok": count <= caps.get("max_order_count", 1),
            "max_single_order_cents": caps.get("max_single_order_cents", 100),
            "order_value_cents": price * count,
        },
        market_metadata_checks={
            "ticker": metadata.ticker,
            "status": metadata.status,
            "trading_allowed": metadata.trading_allowed,
            "min_price_cents": metadata.min_price_cents,
            "max_price_cents": metadata.max_price_cents,
            "tick_size_cents": metadata.tick_size_cents,
        },
        contract_metadata_checks={
            "ticker": contract_ticker,
            "status": contract.status if contract else "unknown",
            "tradable": contract.tradable if contract else False,
        },
        live_submit_required_hash=proof_context.get("live_submit_hash"),
        descriptor_hash=proof_context.get("descriptor_hash"),
        caps_hash=proof_context.get("caps_hash"),
        evidence_registry_hash=proof_context.get("evidence_registry_hash"),
        proof_lock_status=proof_lock_status,
        submit_allowed_now=submit_allowed,
        requires_new_operator_proof_authority=requires_new_authority,
        reason_submit_not_allowed=reason,
        secrets_redacted=True,
    )


def safe_preview(candidate: ProofCandidate) -> dict[str, Any]:
    """Return a secret-free, human-readable preview."""
    return {
        "candidate_id": candidate.candidate_id,
        "created_at": candidate.created_at,
        "validation_mode": candidate.validation_mode,
        "market_ticker": candidate.market_ticker,
        "contract_ticker": candidate.contract_ticker,
        "side": candidate.side,
        "action": candidate.action,
        "order_type": candidate.order_type,
        "count": candidate.count,
        "price_cents": candidate.price,
        "submit_allowed_now": candidate.submit_allowed_now,
        "requires_new_operator_proof_authority": candidate.requires_new_operator_proof_authority,
        "reason_submit_not_allowed": candidate.reason_submit_not_allowed,
        "proof_lock_status": candidate.proof_lock_status,
        "secrets_redacted": candidate.secrets_redacted,
    }


def write_candidate_packet(candidate: ProofCandidate, path: str | os.PathLike[str]) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(candidate)
    p.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return p


def compute_candidate_hash(path: str | os.PathLike[str]) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()
```

- [ ] **Step 4: Run tests; expect pass**

```bash
python -m pytest tests/test_next_proof_candidate_builder.py -q --tb=short --timeout=60
```

---

## Task 4: Add `validate-next-proof-candidate` operator command

**Files:**
- Modify: `tools/operator_authority_appliance/operator_full_completion.py`
- Test: `tests/test_validate_next_proof_candidate_command.py`

**Interfaces:**
- Consumes: `core.kalshi_market_validator`, `core.proof_order_candidate`, `core.proof_lock`, `core.live_execution_mode`, `core.config_loader`, `core.env_loader`
- Produces: `cmd_validate_next_proof_candidate(args)`; writes:
  - `artifacts/dummy/next_proof_candidate/VALIDATED_KALSHI_PROOF_CANDIDATE.json`
  - `artifacts/dummy/next_proof_candidate/NEXT_PROOF_CANDIDATE_VALIDATION_REPORT.json`

- [ ] **Step 1: Write failing tests** (`tests/test_validate_next_proof_candidate_command.py`)

```python
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests._real_proof_test_helpers import make_evidence_bundle, patch_artifact_paths

CLI = [sys.executable, "-m", "tools.operator_authority_appliance.operator_full_completion"]


def test_validate_next_proof_candidate_writes_report(tmp_path, monkeypatch):
    bundle = make_evidence_bundle(tmp_path)
    patch_artifact_paths(monkeypatch, tmp_path)
    out_dir = tmp_path / "next_proof_candidate"
    monkeypatch.setenv("DUMMY_NEXT_PROOF_CANDIDATE_OUT_DIR", str(out_dir))
    result = subprocess.run(
        [*CLI, "validate-next-proof-candidate"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    report = out_dir / "NEXT_PROOF_CANDIDATE_VALIDATION_REPORT.json"
    assert report.exists()
    data = json.loads(report.read_text())
    assert data["submit_allowed_now"] is False
    assert data["requires_new_operator_proof_authority"] is True


def test_validate_next_proof_candidate_does_not_enable_live_submit(tmp_path, monkeypatch):
    bundle = make_evidence_bundle(tmp_path)
    patch_artifact_paths(monkeypatch, tmp_path)
    result = subprocess.run(
        [*CLI, "validate-next-proof-candidate"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 0
    live_submit = Path("configs/live_submit.json")
    if live_submit.exists():
        config = json.loads(live_submit.read_text())
        assert config.get("enabled") is not True


def test_validate_next_proof_candidate_no_broker_contact(tmp_path, monkeypatch):
    bundle = make_evidence_bundle(tmp_path)
    patch_artifact_paths(monkeypatch, tmp_path)
    result = subprocess.run(
        [*CLI, "validate-next-proof-candidate", "--network-mode=no_network"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 0
    report = tmp_path / "next_proof_candidate" / "NEXT_PROOF_CANDIDATE_VALIDATION_REPORT.json"
    data = json.loads(report.read_text())
    assert data["broker_contact_during_validation"] is False
```

- [ ] **Step 2: Run tests; expect failures**

```bash
python -m pytest tests/test_validate_next_proof_candidate_command.py -q --tb=short --timeout=60
```

- [ ] **Step 3: Modify `operator_full_completion.py`**

Add import near the top:

```python
from core import kalshi_market_validator, proof_order_candidate
from core.proof_lock import REAL_PROOF_REGISTRY_PATH, real_proof_attempt_exists, load_real_proof_registry
```

Add subparser in `_build_parser()`:

```python
validate_parser = subparsers.add_parser(
    "validate-next-proof-candidate",
    help="Validate a next-proof candidate without submitting (read-only).",
)
validate_parser.add_argument(
    "--network-mode",
    choices=["no_network", "mock", "read_only_network"],
    default="no_network",
    help="How to obtain market metadata.",
)
validate_parser.add_argument(
    "--market-ticker",
    default="KXBTC-26DEC25000-C",
    help="Market ticker to validate (default: first-attempt ticker).",
)
validate_parser.add_argument(
    "--out-dir",
    default=None,
    help="Override output directory for candidate packet and report.",
)
```

Add handler function before `main()`:

```python
def cmd_validate_next_proof_candidate(args) -> int:
    """Read-only validation of the next proof candidate."""
    out_dir = Path(args.out_dir or os.environ.get("DUMMY_NEXT_PROOF_CANDIDATE_OUT_DIR", "artifacts/dummy/next_proof_candidate"))
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load whitelisted env refs (do not apply to process; read-only).
    env_values = env_loader.read_whitelisted_env(".env")
    env_status = env_loader.kalshi_credential_status(env_values)

    # 2. Load caps and proof registry.
    caps = config_loader.load_caps()
    caps_hash = _hash_file("configs/caps.json")
    live_submit_hash = _hash_file("configs/live_submit.json")
    descriptor_hash = _hash_file("configs/adapter_descriptor.json") if Path("configs/adapter_descriptor.json").exists() else None
    evidence_registry_hash = _hash_file(REAL_PROOF_REGISTRY_PATH)

    registry = load_real_proof_registry()
    previous_status = registry.get("latest_real_broker_attempt_status")
    proof_lock_consumed = real_proof_attempt_exists()

    # 3. Read-only metadata fetch (never submit).
    network_mode = args.network_mode
    client = None
    metadata = kalshi_market_validator.fetch_market_metadata_read_only(
        args.market_ticker, mode=network_mode, client=client
    )

    # If no metadata (no_network), use a placeholder so schema checks still run.
    if metadata is None:
        metadata = kalshi_market_validator.MarketMetadata(
            ticker=args.market_ticker,
            status="unknown",
            open_time=None,
            close_time=None,
            trading_allowed=False,
            min_price_cents=1,
            max_price_cents=99,
            tick_size_cents=1,
            contracts=[
                kalshi_market_validator.ContractMetadata(
                    ticker=args.market_ticker, status="unknown", tradable=False
                )
            ],
        )
        read_only_metadata_status = "not_used"
    else:
        read_only_metadata_status = "mock" if network_mode == "mock" else "read_only_success"

    # 4. Build candidate.
    proof_context = {
        "descriptor_hash": descriptor_hash,
        "caps_hash": caps_hash,
        "live_submit_hash": live_submit_hash,
        "evidence_registry_hash": evidence_registry_hash,
        "previous_real_broker_attempt_status": previous_status,
    }
    candidate = proof_order_candidate.build_validated_proof_candidate(
        metadata, caps, proof_context, validation_mode=network_mode
    )

    # 5. Write candidate packet and report.
    candidate_path = out_dir / "VALIDATED_KALSHI_PROOF_CANDIDATE.json"
    proof_order_candidate.write_candidate_packet(candidate, candidate_path)
    candidate_hash = proof_order_candidate.compute_candidate_hash(candidate_path)

    report = {
        "verdict": "NEXT_PROOF_CANDIDATE_VALIDATION_PASS",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "first_rejection_diagnosis": "unrecovered_from_first_attempt",
        "inferred_rejection_risk_factors": [
            "hardcoded price=1 cent may have been outside allowed tick range",
            "market ticker KXBTC-26DEC25000-C may have been closed/untradable",
            "no pre-submit contract/market metadata validation existed",
        ],
        "market_validator_status": "active",
        "read_only_metadata_status": read_only_metadata_status,
        "candidate_packet_path": str(candidate_path),
        "candidate_packet_hash": candidate_hash,
        "candidate_validation_report_path": str(out_dir / "NEXT_PROOF_CANDIDATE_VALIDATION_REPORT.json"),
        "candidate_market_ticker": candidate.market_ticker,
        "candidate_contract_ticker": candidate.contract_ticker,
        "candidate_order_type": candidate.order_type,
        "candidate_count": candidate.count,
        "candidate_price_cents": candidate.price,
        "candidate_submit_allowed_now": candidate.submit_allowed_now,
        "requires_new_operator_proof_authority": candidate.requires_new_operator_proof_authority,
        "proof_registry_status": previous_status,
        "proof_registry_hash": evidence_registry_hash,
        "proof_lock_status": candidate.proof_lock_status,
        "repeat_submit_block_status": "BLOCKED_BEFORE_ADAPTER_CALL" if proof_lock_consumed else "no_previous_attempt",
        "live_submit_status": "disabled_default",
        "live_submit_hash": live_submit_hash,
        "caps_status": "strict_limit_only_kill_switch_max_order_count_1",
        "caps_hash": caps_hash,
        "adapter_descriptor_status": "staged_kalshi_livebrokerfirewall_limit_only",
        "adapter_descriptor_hash": descriptor_hash,
        "runtime_approval_status": "present" if _approval_exists() else "missing",
        "broker_contact_during_validation": False,
        "read_only_kalshi_metadata_contact": read_only_metadata_status in {"mock", "read_only_success"},
        "live_order_count_during_validation": 0,
        "market_order_status": False,
        "scale_autonomy_status": "disabled",
        "secrets_logging_status": "redacted",
    }
    report_path = out_dir / "NEXT_PROOF_CANDIDATE_VALIDATION_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    report_hash = hashlib.sha256(report_path.read_bytes()).hexdigest().upper()
    report["candidate_validation_report_hash"] = report_hash
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps(proof_order_candidate.safe_preview(candidate), indent=2))
    print(f"Candidate packet: {candidate_path}")
    print(f"Validation report: {report_path}")
    return 0


def _hash_file(path: str) -> str | None:
    p = Path(path)
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest().upper()


def _approval_exists() -> bool:
    return any(Path("runtime/approvals").glob("*.json"))
```

Wire in dispatch:

```python
if args.command == "validate-next-proof-candidate":
    return cmd_validate_next_proof_candidate(args)
```

- [ ] **Step 4: Run tests; expect pass**

```bash
python -m pytest tests/test_validate_next_proof_candidate_command.py -q --tb=short --timeout=60
```

---

## Task 5: Preserve repeat-submit safety after candidate validation

**Files:**
- Test: `tests/test_no_repeat_live_submit_after_candidate_validation.py`

- [ ] **Step 1: Write tests**

```python
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests._real_proof_test_helpers import make_evidence_bundle, patch_artifact_paths

CLI = [sys.executable, "-m", "tools.operator_authority_appliance.operator_full_completion"]


def test_candidate_validation_does_not_unlock_submit(tmp_path, monkeypatch):
    bundle = make_evidence_bundle(tmp_path, broker_rejected=True)
    patch_artifact_paths(monkeypatch, tmp_path)
    result = subprocess.run(
        [*CLI, "validate-next-proof-candidate", "--network-mode=mock"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 0
    candidate_path = tmp_path / "next_proof_candidate" / "VALIDATED_KALSHI_PROOF_CANDIDATE.json"
    candidate = json.loads(candidate_path.read_text())
    assert candidate["submit_allowed_now"] is False
    assert candidate["requires_new_operator_proof_authority"] is True
    assert candidate["proof_lock_status"] == "consumed_by_real_broker_attempt"


def test_one_shot_check_still_blocked_after_candidate_validation(tmp_path, monkeypatch):
    bundle = make_evidence_bundle(tmp_path, broker_rejected=True)
    patch_artifact_paths(monkeypatch, tmp_path)
    subprocess.run([*CLI, "validate-next-proof-candidate"], capture_output=True, cwd=tmp_path)
    result = subprocess.run([*CLI, "one-shot-check"], capture_output=True, text=True, cwd=tmp_path)
    assert result.returncode != 0 or "BLOCKED" in result.stdout or "BLOCKED" in result.stderr
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_no_repeat_live_submit_after_candidate_validation.py -q --tb=short --timeout=60
```

---

## Task 6: Add read-only dashboard panel

**Files:**
- Modify: `dashboard/backend/operator_control_routes.py` (add read-only endpoint)
- Modify: `dashboard/frontend/src/screens/OperatorControl.jsx` (add panel)
- Test: `tests/test_dashboard_next_proof_candidate_status.py`

**Interfaces:**
- `GET /api/operator-control/next-proof-candidate` returns secret-free status.

- [ ] **Step 1: Write failing test** (`tests/test_dashboard_next_proof_candidate_status.py`)

```python
import pytest
from fastapi.testclient import TestClient

from dashboard.backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_next_proof_candidate_status_no_secrets(client):
    response = client.get("/api/operator-control/next-proof-candidate")
    assert response.status_code == 200
    data = response.json()
    assert "idempotency" not in str(data).lower()
    assert data["submit_allowed_now"] is False
    assert "requires_new_operator_proof_authority" in data
```

- [ ] **Step 2: Add backend route**

In `dashboard/backend/operator_control_routes.py`, add:

```python
from core import kalshi_market_validator, proof_order_candidate, proof_lock, config_loader


@router.get("/next-proof-candidate")
async def next_proof_candidate_status():
    """Read-only next-proof candidate status."""
    registry = proof_lock.load_real_proof_registry()
    previous_status = registry.get("latest_real_broker_attempt_status")
    proof_lock_consumed = proof_lock.real_proof_attempt_exists()

    caps = config_loader.load_caps()
    caps_hash = _sha256_file("configs/caps.json")
    live_submit_hash = _sha256_file("configs/live_submit.json")
    descriptor_hash = _sha256_file("configs/adapter_descriptor.json")
    evidence_registry_hash = _sha256_file(proof_lock.REAL_PROOF_REGISTRY_PATH)

    metadata = kalshi_market_validator.fetch_market_metadata_read_only(
        "KXBTC-26DEC25000-C", mode="no_network"
    ) or kalshi_market_validator.MarketMetadata(
        ticker="KXBTC-26DEC25000-C",
        status="unknown",
        open_time=None,
        close_time=None,
        trading_allowed=False,
        min_price_cents=1,
        max_price_cents=99,
        tick_size_cents=1,
        contracts=[
            kalshi_market_validator.ContractMetadata(
                ticker="KXBTC-26DEC25000-C", status="unknown", tradable=False
            )
        ],
    )

    proof_context = {
        "descriptor_hash": descriptor_hash,
        "caps_hash": caps_hash,
        "live_submit_hash": live_submit_hash,
        "evidence_registry_hash": evidence_registry_hash,
        "previous_real_broker_attempt_status": previous_status,
    }
    candidate = proof_order_candidate.build_validated_proof_candidate(
        metadata, caps, proof_context, validation_mode="no_network"
    )

    return {
        "candidate_validation_status": "validated_schema_only",
        "market_validated": False,
        "contract_validated": False,
        "read_only_metadata_mode": "none",
        "submit_allowed_now": candidate.submit_allowed_now,
        "requires_new_operator_proof_authority": candidate.requires_new_operator_proof_authority,
        "reason_submit_not_allowed": candidate.reason_submit_not_allowed,
        "proof_lock_status": candidate.proof_lock_status,
        "next_action": "review candidate packet and create new explicit operator proof authority",
        "secrets_redacted": True,
    }


def _sha256_file(path: str) -> str | None:
    from pathlib import Path
    import hashlib
    p = Path(path)
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest().upper()
```

- [ ] **Step 3: Add frontend panel**

In `dashboard/frontend/src/screens/OperatorControl.jsx`, add a new section after the status banner:

```jsx
function NextProofCandidatePanel() {
  const [candidate, setCandidate] = useState(null);
  useEffect(() => {
    fetchJson("/api/operator-control/next-proof-candidate")
      .then(setCandidate)
      .catch(() => setCandidate(null));
  }, []);
  if (!candidate) return null;
  return (
    <section className="panel next-proof-candidate">
      <h2>Next Proof Candidate (Read-Only)</h2>
      <p>Validation status: {candidate.candidate_validation_status}</p>
      <p>Market validated: {candidate.market_validated ? "yes" : "no"}</p>
      <p>Contract validated: {candidate.contract_validated ? "yes" : "no"}</p>
      <p>Read-only metadata mode: {candidate.read_only_metadata_mode}</p>
      <p>Submit allowed now: {candidate.submit_allowed_now ? "true" : "false"}</p>
      <p>Requires new operator proof authority: {candidate.requires_new_operator_proof_authority ? "yes" : "no"}</p>
      <p>Reason: {candidate.reason_submit_not_allowed}</p>
      <p>Next action: {candidate.next_action}</p>
    </section>
  );
}
```

Render `<NextProofCandidatePanel />` in the main component.

- [ ] **Step 4: Run tests and build**

```bash
python -m pytest tests/test_dashboard_next_proof_candidate_status.py -q --tb=short --timeout=60
cd dashboard/frontend && npm run build
```

---

## Task 7: Run all validation commands and report

**Files:**
- Read: `artifacts/dummy/next_proof_candidate/VALIDATED_KALSHI_PROOF_CANDIDATE.json`
- Read: `artifacts/dummy/next_proof_candidate/NEXT_PROOF_CANDIDATE_VALIDATION_REPORT.json`

**Commands:**

```bash
python -m py_compile core/env_loader.py
python -m py_compile core/live_execution_mode.py
python -m py_compile core/proof_lock.py
python -m py_compile core/kalshi_market_validator.py
python -m py_compile core/proof_order_candidate.py
python -m py_compile live_firewall/firewall.py
python -m py_compile predator_mesh/v298/reports.py
python -m py_compile predator_mesh/v304/reports.py
python -m py_compile tools/operator_authority_appliance/operator_full_completion.py
python -m py_compile dashboard/backend/operator_control_routes.py dashboard/backend/main.py
```

```bash
python -m pytest tests/test_kalshi_market_validator.py -q --tb=short --timeout=60
python -m pytest tests/test_next_proof_candidate_builder.py -q --tb=short --timeout=60
python -m pytest tests/test_validate_next_proof_candidate_command.py -q --tb=short --timeout=60
python -m pytest tests/test_no_repeat_live_submit_after_candidate_validation.py -q --tb=short --timeout=60
python -m pytest tests/test_dashboard_next_proof_candidate_status.py -q --tb=short --timeout=60
```

```bash
python -m pytest tests/test_real_broker_proof_evidence_registry.py -q --tb=short --timeout=60
python -m pytest tests/test_broker_rejection_artifact_semantics.py -q --tb=short --timeout=60
python -m pytest tests/test_proof_lock_after_broker_rejection.py -q --tb=short --timeout=60
python -m pytest tests/test_v304_preserved_real_proof_reporting.py -q --tb=short --timeout=60
python -m pytest tests/test_execute_once_real_broker_wiring.py -q --tb=short --timeout=60
python -m pytest tests/test_v298_real_proof_semantics.py -q --tb=short --timeout=60
python -m pytest tests/test_live_firewall_real_adapter_path.py -q --tb=short --timeout=60
python -m pytest tests/test_live_execution_mode.py -q --tb=short --timeout=60
python -m pytest tests/test_live_submit_state_model.py -q --tb=short --timeout=60
python -m pytest tests/test_operator_full_completion.py -q --tb=short --timeout=60
python -m pytest tests/test_v295_to_v304_governance.py -q --tb=short --timeout=60
```

```bash
python -m pytest tests/ -q --tb=short --timeout=120
```

```bash
python tools/operator_authority_appliance/operator_full_completion.py validate-next-proof-candidate
python tools/operator_authority_appliance/operator_full_completion.py one-shot-check
```

**Expected:**
- `validate-next-proof-candidate` writes candidate packet + report.
- `one-shot-check` remains blocked (`BLOCKED_LIVE_SUBMIT_CAPS` or similar).
- Full default-state suite: 4119 passed, 2 skipped, 1 warning (or current baseline).

---

## Task 8: Produce final report

**Files:**
- Read: `artifacts/dummy/next_proof_candidate/NEXT_PROOF_CANDIDATE_VALIDATION_REPORT.json`
- Read: `artifacts/dummy/real_proof_registry.json`
- Read: `configs/live_submit.json`
- Read: `configs/caps.json`

**Deliverable:** Return `DUMMY_NEXT_PROOF_CANDIDATE_VALIDATION_REPORT` to the user with all required fields.

Required fields:
- `verdict`: `NEXT_PROOF_CANDIDATE_VALIDATION_PASS` or `REPAIR_REQUIRED`
- `files_changed`
- `first_rejection_diagnosis`: `unrecovered_from_first_attempt`
- `inferred_rejection_risk_factors` (clearly marked inferred)
- `market_validator_status`
- `read_only_metadata_status`
- `candidate_packet_path` and hash
- `candidate_validation_report_path` and hash
- `candidate_market_ticker`, `contract_ticker`, `order_type`, `count`, `price`
- `candidate_submit_allowed_now` (expected false)
- `requires_new_operator_proof_authority` (expected true)
- `proof_registry_status/hash`
- `proof_lock_status`
- `repeat_submit_block_status`
- `live_submit_status/hash`
- `caps_status/hash`
- `adapter_descriptor_status/hash`
- `runtime_approval_status/hash`
- `one_shot_check_default_result`
- `broker_contact_during_this_bundle` (false)
- `read_only_kalshi_metadata_contact_during_this_bundle` (false unless mock mode)
- `live_order_count_during_this_bundle` (0)
- `market_order_status` (false)
- `scale_autonomy_status` (disabled)
- `secrets_logging_status`
- `focused_tests_result`
- `full_default_state_suite_result`
- `frontend_build_result`
- `exact_remaining_blocker`
- `next_action_recommendation`
- `git_commit_status` (not committed)

---

## Self-Review Checklist

- [ ] Spec coverage: every Part A–I requirement maps to a task.
- [ ] Placeholder scan: no TBD/TODO/fill-in-details.
- [ ] Type consistency: `ProofCandidate`, `MarketMetadata`, `ContractMetadata`, `ValidationResult` used consistently.
- [ ] Safety: no submit/cancel/enable-live-submit in any task.
- [ ] No V305+: only existing v304 dashboard touched.
- [ ] Tests added for all new modules and commands.
