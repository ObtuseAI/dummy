# Real Broker Execution Wiring Design — v298 Execute-Once Final Proof Runner

## Goal
Wire the existing v298 execute-once final proof runner so that, when every existing gate is satisfied, it makes exactly one real Kalshi limit-order attempt through the existing `KalshiLiveBrokerFirewallAdapter.submit_limit_order` path, and writes truthful proof artifacts.

## Non-goals
- No new V305+ stage or architecture ladder.
- No rewrite of the Kalshi adapter unless tests prove it broken.
- No market orders, scale, autonomy, or direct Kalshi bypass.
- No fake proof or counting non-broker doubles as live proof.

## Current state
- `predator_mesh/v298/reports.py` `_controller` returns `PASS_EXECUTE_ONCE_FINAL_PROOF_RUNNER_SUBMITTED_AUTOLOCKED` with `uses_non_broker_double=True` and never calls a broker.
- `KalshiLiveBrokerFirewallAdapter` exists and is tested with mocked transport.
- `live_firewall/firewall.py` `LiveBrokerFirewall` evaluates orders but calls `self.client.create_order`, not the adapter.
- `core/live_submit_state.py` defines the one-proof enabled state model.
- Command seal, runtime approval, descriptor, caps, and credentials are already staged/ready.

## Design

### 1. Execution mode classifier (`core/live_execution_mode.py`)
Define explicit modes:
- `DEFAULT_DISABLED`
- `REHEARSAL_OR_TEST_DOUBLE`
- `OPERATOR_ONE_PROOF_LIVE_READY`
- `INVALID_OR_BLOCKED`

Classify from `configs/live_submit.json`, env gate (`DUMMY_LIVE_PROOF_MODE` + `DUMMY_LIVE_PROOF_ACK`), command seal, caps, descriptor, credentials, and proof-lock state.

### 2. LiveBrokerFirewall adapter path (`live_firewall/firewall.py`)
Add `LiveBrokerFirewall.submit_limit_order_adapter(req: LimitOrderRequest) -> LiveOrderResult` that:
- Re-runs the policy gates required for one-proof live submit (live-submit enabled, command seal ready, caps strict, LIMIT only, no market orders, max_order_count == 1, idempotency key present, proof_id/proof_target present, proof lock clear, descriptor hash match).
- Constructs a `KalshiLiveBrokerFirewallAdapter` with the gate flags.
- Calls `adapter.submit_limit_order(req)` once.
- Records exposure only on accepted submit.
- Returns a `LiveOrderResult` with `success`, `order_id`, `error`.
- Never retries.

Existing `evaluate`/`submit_rehearsal`/`submit` methods stay unchanged so rehearsal tests keep working.

### 3. v298 runner wiring (`predator_mesh/v298/reports.py`)
When the arm packet is fully truthy (all `ARM_CHECKS` pass), instead of returning the non-broker-double result:
- Build one `LimitOrderRequest` for the smallest proof:
  - `venue="KALSHI"`, `order_type="LIMIT"`, `market_orders_allowed=False`
  - `side="yes"`, `action="buy"`, `quantity=1`, `price=1` (1 cent, smallest)
  - `market_ticker` discovered from Kalshi or a known active ticker
  - `idempotency_key` / `client_order_id` derived from proof_id, descriptor hash, caps hash, live-submit hash, nonce
  - `proof_id` and `proof_target="FIRST_REAL_PILOT_PROOF"`
- Call `LiveBrokerFirewall(...).submit_limit_order_adapter(req)` via `asyncio.run()`.
- Map the adapter `SubmitResult` to truthful artifact fields:
  - `real_broker_contacted = True` if a real broker request was attempted (submitted or broker rejection captured).
  - `real_live_orders_submitted_count = 1` only if `result.submitted` is True.
  - `broker_rejection_captured = True` if the adapter returned a structured broker rejection.
  - `non_broker_double_used = False`.
  - `proof_is_real = True` only for real broker contact/rejection.
- Preserve rehearsal/test path so unarmed runs still report `non_broker_double_used=True` and `real_broker_contacted=False`.

### 4. v304 completion lift update (`predator_mesh/v304/reports.py`)
Treat a v298 result as real proof when:
- v298 status is the submitted/autolocked status,
- `non_broker_double_used` is False,
- `real_broker_contacted` is True,
- either `real_live_orders_submitted_count == 1` or `broker_rejection_captured` is True (per policy that a real broker rejection is a real attempt).

### 5. Tests
Add:
- `tests/test_execute_once_real_broker_wiring.py`
- `tests/test_v298_real_proof_semantics.py`
- `tests/test_live_firewall_real_adapter_path.py`

Cover rehearsal double cannot claim real proof, missing env gate blocks, missing live-submit blocks, missing seal blocks, strict caps blocks, firewall adapter call ordering, accepted/rejected mocked broker responses, idempotency/proof lock, secrets redaction, and v304 lift semantics.

### 6. Validation / live attempt
- py_compile changed modules.
- Focused adapter/state/firewall/v298 tests.
- Full default-state suite.
- Frontend build.
- Enable one-proof live-submit via the controlled helper.
- Set env gate and run `one-shot-live` exactly once.
- Run post-proof pipeline.
- Restore default disabled live-submit if repo policy requires baseline disabled.

## Risks and mitigations
- Async/sync boundary: v298 controller is synchronous; wrap the async adapter call in `asyncio.run()` and close the adapter client.
- Market ticker unknown: attempt discovery via `KalshiClient.get_markets()`; if discovery fails, attempt a known conservative ticker so the broker rejection still counts as real contact.
- Caps market allowlist empty: the new one-proof path does not use `LiveBrokerFirewall.evaluate`, so the empty allowlist does not block the real attempt.
- Proof lock: check `artifacts/dummy/final_report_v298.json` for existing `real_broker_contacted` / `real_live_orders_submitted_count` before attempting.
