# Second-Proof Operator Runbook (corrected sequence)

Updated 2026-07-08 after the truth-layer audit. Read this before any live attempt.

## What actually happened on 2026-07-08

The "SECOND_PROOF_EXECUTED_BROKER_REJECTED" verdict was false. The firewall's
execution-mode gate returned `live_submit_disabled` **before any network call**;
the old runner labeled every non-exception error as a broker rejection and
inferred contact. Kalshi was never reached. Ground truth lives in
`runtime/proof_locks/second_proof_<authority>.json` (`reason` field) and, going
forward, in the transport witness (`broker_rejection_http_status` /
`broker_rejection_stage == "broker_transport"`).

## The ordering trap

- `second-proof-runtime-preflight` **requires** `configs/live_submit.json` disabled.
- The firewall's one-proof mode **requires** it enabled (full operator-one-proof state).

Therefore enablement must happen **after** preflight and **immediately before**
`one-shot-live`, with nothing in between that restores the disabled default
(every runner invocation, including test-driven ones, auto-restores disabled).

## Correct sequence (one real attempt)

```bash
# 0. Read-only freshness: candidate still tradable? (never mutates canonical files)
python scripts/run_dummy_presubmit_validation.py

# 1. Fresh authority (old lock second-proof-6dc8e9... was consumed by the old bug)
python tools/operator_authority_appliance/operator_full_completion.py prepare-second-proof-authority
python tools/operator_authority_appliance/operator_full_completion.py activate-second-proof-authority \
  --operator-name "<name>" --reason "<reason>" --expires-at "<future-iso>" \
  --confirm "<exact REQUIRED_CONFIRMATION from core/proof_authority.py>"

# 2. Preflight (expects live-submit DISABLED)
python tools/operator_authority_appliance/operator_full_completion.py second-proof-runtime-preflight

# 3. Enable live-submit (typed confirmation; future expiry)
python tools/operator_authority_appliance/operator_full_completion.py enable-one-proof-live-submit \
  --operator "<name>" --reason "<reason>" --expires-at "<future-iso>" \
  --typed-confirmation "<exact LIVE_SUBMIT_TYPED_CONFIRMATION>"

# 4. IMMEDIATELY fire, same shell, env-gated
$env:DUMMY_LIVE_PROOF_MODE = "1"
$env:DUMMY_LIVE_PROOF_ACK = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"
python tools/operator_authority_appliance/operator_full_completion.py one-shot-live

# 5. Intake + route (truth-checked, lock-corroborated)
python scripts/run_dummy_second_proof_intake_v2.py
```

## Post-fix semantics

- A pre-broker gate block (`SECOND_PROOF_BLOCKED_BEFORE_BROKER`) no longer
  consumes the lock or retires the authority — repair the gate and re-fire.
- Only transport-witnessed outcomes (`ACCEPTED` / `BROKER_REJECTED`) spend the
  one-real-attempt budget.
- Evidence reports now embed `rejection_classification` (category, operator
  action, retry policy) from `kalshi/rejection_classifier.py`.
- Intake quarantines any evidence directory not corroborated by a runtime lock
  (`ROUTE_EVIDENCE_UNTRUSTED_QUARANTINE`) — fixture/test artifacts can no
  longer masquerade as real proofs.
- Tests write evidence under `DUMMY_EVIDENCE_ROOT` (tmp) — the real
  `artifacts/dummy` tree stays clean.

## Known-good state as of 2026-07-08

- Credentials: valid (authenticated read-only `GET /portfolio/balance` succeeded).
- API base: `https://api.elections.kalshi.com` + `trade-api/v2` (client, signer,
  adapter, v16 runtime config all aligned; legacy v1 host is dead).
- Order body: `yes_price`/`no_price` + required `client_order_id` (flat `price`
  never leaves the machine; presubmit validator rejects it).
- V3 candidate `KXMVESPORTSMULTIGAMEEXTENDED-S2026507888D9EE4-E8412AFB1D6`:
  real market, status active, closes 2026-07-12T02:10Z, tick 1¢, zero liquidity
  (a 1¢ LIMIT YES rests unfilled — acceptance is the proof; cancel afterwards).
