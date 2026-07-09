# Read-Only Kalshi Metadata Candidate V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or AgentSwarm to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Replace Dummy's stale no-network next-proof candidate with a read-only Kalshi metadata-validated V2 candidate packet that uses a currently tradable, live-eligible market/contract shape, while keeping repeat-submit protection and live-submit disabled.

**Architecture:** Extend `core/kalshi_market_validator.py` with a real read-only discovery path that wraps `kalshi.client.KalshiClient` behind a method-guarded transport. Add a `core/proof_order_candidate_v2.py` builder that consumes discovered metadata and emits the V2 packet + report. Wire `tools/operator_authority_appliance/operator_full_completion.py validate-next-proof-candidate --mode read-only` to call the new flow without any broker write. Update the dashboard `next-proof-candidate` endpoint/panel to show V1 and V2 status side by side. Harden everything with focused tests.

**Tech Stack:** Python 3.11+, FastAPI, React/JSX, pytest, httpx, existing Kalshi client/signers.

## Global Constraints

- Read-only GET metadata only; no POST/PATCH/PUT/DELETE order calls.
- No live order submission, no cancel, no modify.
- No one-shot-live invocation by this bundle.
- No live-submit enablement outside isolated tests.
- No proof-lock reset, no new proof authority generation.
- No market orders, no scale, no autonomy.
- No secrets printed or persisted; redact all idempotency/private-key material.
- Do not overwrite `VALIDATED_KALSHI_PROOF_CANDIDATE.json` (V1); write `VALIDATED_KALSHI_PROOF_CANDIDATE_V2.json`.
- Do not commit unless explicitly requested.

## File Map

| File | Responsibility |
|------|----------------|
| `core/kalshi_market_validator.py` | Add `KalshiReadOnlyMetadataClient` adapter, `discover_live_eligible_candidates`, metadata→price derivation. |
| `core/proof_order_candidate.py` | Extend `ProofCandidate` / builder to support V2 fields (price_source, price_validated, candidate_found, etc.). |
| `core/read_only_transport_guard.py` | New transport guard that allows GET/HEAD and blocks all write methods; records blocked attempts. |
| `tools/operator_authority_appliance/operator_full_completion.py` | Add `--mode {no-network,read-only}`, explicit market/contract options, discovery policy, V2 artifact writes. |
| `dashboard/backend/operator_control_routes.py` | Add/update `/next-proof-candidate` to return V1 + V2 status with no secrets and no submit action. |
| `dashboard/frontend/src/screens/OperatorControl.jsx` | Update `NextProofCandidatePanel` to show V1/V2 split status. |
| `tests/test_kalshi_read_only_metadata_discovery.py` | Metadata discovery, candidate selection, closed/untradable rejection, price derivation. |
| `tests/test_next_proof_candidate_v2_builder.py` | V2 builder fields, hashes, no secrets, candidate_found false path. |
| `tests/test_validate_next_proof_candidate_read_only_command.py` | CLI `--mode read-only` writes V2 packet/report, no mutations. |
| `tests/test_read_only_transport_guard.py` | GET allowed, POST/DELETE/cancel blocked. |
| `tests/test_dashboard_next_proof_candidate_v2_status.py` | Dashboard V2 panel fields, no secrets, no submit action. |

---

## Task 1: Read-Only Metadata Discovery Core

**Files:**
- Create: `core/read_only_transport_guard.py`
- Modify: `core/kalshi_market_validator.py`

**Interfaces:**
- Consumes: `kalshi.client.KalshiClient`, `core.env_loader` for base URL/key refs.
- Produces: `KalshiReadOnlyMetadataClient`, `discover_live_eligible_candidates(...)` returning `(candidate_found, MarketMetadata|None, reason)`.

- [ ] **Step 1: Write transport guard class**

```python
class ReadOnlyTransportGuard:
    ALLOWED_METHODS = {"GET", "HEAD"}
    def request(self, method: str, path: str, **kwargs): ...
```

- [ ] **Step 2: Add KalshiReadOnlyMetadataClient**

Wraps `KalshiClient` with the guard; exposes only `get_markets()`, `get_market(ticker)`, `get_contract(ticker)` (if supported), and audit log. No `create_order`/`cancel_order` reachable.

- [ ] **Step 3: Implement discovery policy**

`discover_live_eligible_candidates(client, max_candidates=10, prefer_event=None)` queries active/tradable markets, filters for LIMIT-possible, count=1-compatible, derives a valid price, and returns the lowest-risk candidate.

- [ ] **Step 4: Implement metadata→price derivation**

Use `min_price_cents` + tick alignment. If metadata lacks ticks, use a conservative validated price only if schema confirms; otherwise `price_validated=False`.

- [ ] **Step 5: Add/update tests**

`tests/test_kalshi_read_only_metadata_discovery.py` and `tests/test_read_only_transport_guard.py`.

---

## Task 2: V2 Candidate Builder

**Files:**
- Modify: `core/proof_order_candidate.py`

**Interfaces:**
- Consumes: `MarketMetadata`, caps dict, proof context dict, `validation_mode`, `candidate_found`, `price_source`.
- Produces: `ProofCandidate` with V2 fields; `build_validated_proof_candidate_v2(...)`; `write_candidate_packet_v2(...)`.

- [ ] **Step 1: Extend ProofCandidate dataclass**

Add `candidate_found: bool`, `price_source: str`, `price_validated: bool`, `market_status: str`, `contract_status: str`, `market_tradable: bool`, `contract_tradable: bool`, `action: str`, `read_only_metadata_contact: bool`, `broker_submit_contact: bool`, `live_order_count: int`, `order_write_methods_blocked: bool`, `metadata_mode: str`.

- [ ] **Step 2: Implement V2 builder**

`build_validated_proof_candidate_v2(...)` always sets `submit_allowed_now=False` when proof lock consumed; sets `requires_new_operator_proof_authority=True`; records `reason_submit_not_allowed=PREVIOUS_REAL_BROKER_ATTEMPT_RECORDED`.

- [ ] **Step 3: Add V2 writer**

`write_candidate_packet_v2(candidate, path)` writes to `VALIDATED_KALSHI_PROOF_CANDIDATE_V2.json`.

- [ ] **Step 4: Add tests**

`tests/test_next_proof_candidate_v2_builder.py`.

---

## Task 3: CLI Command Update

**Files:**
- Modify: `tools/operator_authority_appliance/operator_full_completion.py`

**Interfaces:**
- Consumes: `core.kalshi_market_validator.discover_live_eligible_candidates`, `core.proof_order_candidate.build_validated_proof_candidate_v2`.
- Produces: `VALIDATED_KALSHI_PROOF_CANDIDATE_V2.json`, `NEXT_PROOF_CANDIDATE_READ_ONLY_METADATA_REPORT.json`.

- [ ] **Step 1: Add CLI options**

`--mode {no-network,read-only}`, `--market-ticker`, `--contract-ticker`, `--max-candidates`, `--allow-read-only-kalshi-get`.

- [ ] **Step 2: Implement no-network path**

Keep existing behavior, write V1 packet/report unchanged.

- [ ] **Step 3: Implement read-only path**

Load credentials via `core.env_loader` (do not print values), instantiate guarded client, discover candidate, build V2, write V2 packet + read-only report, record `read_only_metadata_contact=True`, `broker_submit_contact=False`, `live_order_count=0`.

- [ ] **Step 4: Handle failures**

If auth/network/API fails → `READ_ONLY_METADATA_BLOCKED` with exact safe blocker; still write a report.

- [ ] **Step 5: Add tests**

`tests/test_validate_next_proof_candidate_read_only_command.py`.

---

## Task 4: Dashboard V2 Panel

**Files:**
- Modify: `dashboard/backend/operator_control_routes.py`
- Modify: `dashboard/frontend/src/screens/OperatorControl.jsx`

**Interfaces:**
- Consumes: V1 and V2 candidate packets/reports.
- Produces: JSON with `v1_status`, `v2_status`, no secrets, no submit action.

- [ ] **Step 1: Update backend endpoint**

Read both V1 and V2 artifacts; return combined status including `candidate_found`, `market_tradable`, `contract_tradable`, `price_validated`, `submit_allowed_now`, `requires_new_operator_proof_authority`, `proof_lock_status`.

- [ ] **Step 2: Update frontend panel**

Show V1 no-network status and V2 read-only metadata status side by side; no submit button; no live-submit auto-enable.

- [ ] **Step 3: Add tests**

`tests/test_dashboard_next_proof_candidate_v2_status.py`.

---

## Task 5: Validation & Final Report

**Files:**
- All changed/new modules.
- Artifacts: `artifacts/dummy/next_proof_candidate/VALIDATED_KALSHI_PROOF_CANDIDATE_V2.json`, `artifacts/dummy/next_proof_candidate/NEXT_PROOF_CANDIDATE_READ_ONLY_METADATA_REPORT.json`.

- [ ] **Step 1: py_compile all changed modules**
- [ ] **Step 2: Run focused pytest suite**
- [ ] **Step 3: Run full default-state suite**
- [ ] **Step 4: Run no-network and read-only CLI commands**
- [ ] **Step 5: Run one-shot-check default state**
- [ ] **Step 6: Compute hashes and emit `DUMMY_READ_ONLY_METADATA_CANDIDATE_V2_REPORT`**

---

## Self-Review

- **Spec coverage:** All Parts A-I map to tasks above.
- **Placeholder scan:** No TBD/TODO; all signatures and files specified.
- **Type consistency:** `MarketMetadata`/`ContractMetadata` reused; V2 builder extends existing dataclass.
