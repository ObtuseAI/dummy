# Correction — the "broker rejection" that never reached a broker

**Date:** 2026-07-24
**Record corrected:** `artifacts/dummy/real_proof_registry.json`
**Authorization:** operator (Chris), 2026-07-24, after read-only evidence review
**Capital effect:** none. No live submission was enabled, attempted, or unblocked by this correction.

## Summary

The 2026-07-07 controlled-proof attempt was recorded as `BROKER_REJECTED` with
`latest_real_broker_contacted: true`. No broker was contacted. The event was a local gate
block, and the label latched `core/proof_lock.py`, which held live submission closed for
16 days on the belief that the one controlled proof budget had been spent. It had not.

## The contradiction, in one document

The v298 controller report asserts contact:

```
real_broker_contacted            = true
broker_rejection_captured        = true
rejected_by_broker               = true
arm_state = "SUBMITTED_AUTOLOCKED_REAL_BROKER_ATTEMPT"
```

Every mechanical fact in the same report says nothing left the box:

```
broker_submit_call_made          = false     <- no submit call
submit_call_present              = false
order_endpoints_used             = false     <- no order endpoint touched
broker_payloads_created          = false     <- no payload even built
broker_schema_created            = false
transform_to_broker_path_present = false
broker_order_id                  = null
live_submit_disabled             = true      <- submission disabled throughout
real_live_orders_submitted_count = 0
```

A broker cannot reject an order that was never built, never addressed to an endpoint, and
never sent, from a process with submission disabled.

## Corroboration

**1. The evidence index has no broker response in it.**

`REAL_BROKER_PROOF_EVIDENCE_INDEX.json`:

```
"broker_rejection_reason_code":        "UNRECOVERED_FROM_FIRST_ATTEMPT"
"broker_rejection_http_status":        null
"broker_rejection_adapter_error_type": null
"broker_rejection_raw_redacted":       null
"broker_rejection_safe_message":       "First v298 artifact collapsed structured rejection
                                        to BROKER_REJECTED; future path patched to retain
                                        structured rejection."
```

No HTTP status, no adapter error type, no raw payload. The reason code means "we could not
recover why," and the safe message admits the artifact *collapsed* an unknown outcome into
the string `BROKER_REJECTED`. `rejected_by_broker: true` is a default label over an unknown
local result, not an observed reply.

**2. The 07-08 attempt repeated the mislabel and named its own cause.**

`runtime/proof_locks/second_proof_second-proof-6dc8e9c29afd4a01.json`:

```json
{ "broker_contacted": true, "rejected": true, "accepted": false,
  "broker_order_id": "", "broker_rejection_code": "",
  "reason": "live_submit_disabled", "consumed": true }
```

Empty rejection code, and the recorded reason is that live submit was disabled locally.
This is the same class of event, labelled the same wrong way, one day later.

This is precisely the failure mode that caused `kalshi/rejection_classifier.py` and the
truth layer to be built on 2026-07-08. The classifier was written for this; the record it
was written to fix was never re-examined.

## What the correction changes

`artifacts/dummy/real_proof_registry.json` is **amended, not rewritten**. The original claim
is preserved verbatim under `correction.original_claim`. The evidence bundle under
`artifacts/dummy/real_proof_backup_20260707T1855/` is untouched — `evidence_index_hash` and
every `source_artifact_paths[].sha256` still recompute.

| Field | Was | Now |
|---|---|---|
| `latest_real_broker_attempt_status` | `BROKER_REJECTED` | `LOCAL_GATE_BLOCK_NO_BROKER_CONTACT` |
| `latest_real_broker_contacted` | `true` | `false` |
| `latest_real_broker_rejection_captured` | `true` | `false` |
| `latest_real_live_orders_submitted_count` | `0` | `0` (unchanged, always was 0) |

Two downstream effects, both intended:

- `core/proof_lock.py:proof_lock_clear()` — `false` → `true`. The proof budget is restored,
  because it was never spent.
- `core/proof_authority.py:_registry_invariants()` — now returns
  `BLOCKED_PRIOR_PROOF_REGISTRY_INVALID` (the attempt-status check at `:166` fires before the
  `latest_real_broker_contacted` check at `:168`). The second-proof authority path closes. This is
  correct: there is no consumed first proof for a second proof to replace. The original v298
  one-shot door is the applicable door again.

## What this correction does *not* do

It arms nothing. After the amendment the live gate is still held closed by, in evaluation
order (`core/live_execution_mode.py:classify_live_execution_mode`):

| Gate | State |
|---|---|
| `configs/live_submit.json` | `{"enabled": false}` — short-circuits to `DEFAULT_DISABLED` |
| `DUMMY_LIVE_PROOF_MODE` | unset |
| `DUMMY_LIVE_PROOF_ACK` | unset — operator-only, never set by Dummy |
| `caps_strict` | **false** — no caps authority registration |
| `descriptor_staged` | true |
| credentials | absent from env — operator-only |
| `proof_lock_clear` | true (this correction) |

Four of those are the operator's alone. Nothing here touches them.

## Two related items deliberately NOT done

The same authorization covered registering caps and populating `allowed_markets`. Both were
stopped, for reasons that are structural rather than discretionary:

**1. The caps authority registration must not be written by Dummy.**
`core/caps_authority.py` states the boundary in its own docstring: code "must never
manufacture the separate operator registration needed to use that baseline in a live-authority
decision." The required file contains `"not_self_authorized_by_dummy": true` alongside a
first-person operator acknowledgement. Writing it from here would make that field a false
statement — Dummy self-authorizing while asserting it did not. It belongs to the operator,
in the same class as `DUMMY_LIVE_PROOF_ACK`.

**2. Populating `allowed_markets` currently *breaks* `caps_strict`.**
`configs/caps.json` hashes to exactly `PROTECTED_CAPS_SHA256`
(`62878A5F…`). Any byte change raises `CAPS_PROTECTED_HASH_MISMATCH`, which clears
`config_integrity_valid`, which clears `authority_registration_valid`, which makes
`_caps_strict()` return `false`. So editing `allowed_markets` on its own moves the gate
backwards. It can only be changed as part of one operator ceremony: edit caps → re-seal
`PROTECTED_CAPS_SHA256` → issue a fresh registration against the new hash. Doing that
piecemeal from here would mean blessing my own edit by rewriting the seal that exists to
prevent exactly that.

Note also that `allowed_markets: []` is deny-all, not allow-all
(`live_firewall/firewall.py:499`), so leaving it empty is the conservative state.

## Operator ceremony to finish items 1 and 2

Author `runtime/operator_external/caps_authority_registration_v2.json` by hand:

```json
{
  "schema_version": 1,
  "caps_config_schema_version": 2,
  "authority_epoch": "caps-v2-kalshi-category-metadata-20260722",
  "caps_sha256": "62878A5F062D71D2EA3EFC3D998874B887FD8D8E885C7745231208F03D913797",
  "scope": "caps_policy_registration_for_controlled_firewall_only",
  "exact_acknowledgement": "I approve this exact caps-v2 hash for controlled firewall-only proof use, with no market orders, no scale, no autonomy, and every other live gate still required",
  "not_self_authorized_by_dummy": true,
  "live_submit_enabled_by_registration": false,
  "market_orders_allowed": false,
  "scale_allowed": false,
  "autonomy_allowed": false,
  "operator": "<your name>",
  "reason": "<why>",
  "issued_at": "<UTC ISO-8601, not in the future>",
  "expires_at": "<UTC ISO-8601, in the future>"
}
```

> **Superseded 2026-07-25 (Wave-88).** The hash below is the 2026-07-22 seal.
> `configs/caps.json` has since gained `allowed_series: ["KXSOL15M"]` and was re-sealed to
> `83FCE350D6AAF5DAA623F79FBE39455BE7120D4EE2C01EB254D39EB72B91E954`, with a fresh
> registration issued against it. Read `PROTECTED_CAPS_SHA256` from
> `core/caps_authority.py` rather than copying a hash from this historical record.

`caps_sha256` above is the hash of `configs/caps.json` **as it stood on 2026-07-24**, with
`allowed_markets` still empty. If you want the promoted SOL 15m family allowlisted, that
must happen first, and then the seal and the registration must both be reissued against the
new bytes.

The promoted family, for reference — `docs/promotions/2026-07-16-sol-15m-crypto.md`:

| source | subject | market_type | horizon |
|---|---|---|---|
| `crypto_blend_sigma` | `sol` | `15m_direction` | `15m` |
| `crypto_equities_flow` | `sol` | `15m_direction` | `15m` |
| `crypto_macro_regime` | `sol` | `15m_direction` | `15m` |

Those are **signal scopes, not Kalshi tickers**. `allowed_markets` is matched against
`req.market_ticker` (`firewall.py:499`), so it needs concrete `KXSOL15M-…` contract tickers,
resolved at the time of the proof. A scope string placed in `allowed_markets` would match
nothing and silently deny every order.
