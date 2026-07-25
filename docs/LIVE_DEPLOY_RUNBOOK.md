# Live deploy runbook

**Written 2026-07-25 (Wave-89).** Supersedes the gate table in
`DUMMY-TAKEOVER-HANDOFF-2026-07-25.md`, which listed one gate that does not
exist on the live path and omitted the one that arms trading.

This is the *trading* path: `autonomy/brain` → `allocator` → `autonomy/executor`
→ `LiveBrokerFirewall.submit` → `client.create_order`. It is the only wired
route to a real order.

The `one-shot-*` operator ceremony in
`tools/operator_authority_appliance/operator_full_completion.py` is **not** this
path and cannot place an order — see "The ceremony is vestigial" below.

Run everything from `C:\src\engine\dummy`. The appliance resolves artifacts from
the current directory; from anywhere else the gate readings are meaningless.

---

## What the live path actually checks

Two independent layers, both fail-closed.

**1. Firewall authority** — `live_execution_authority_status()`
(`live_firewall/firewall.py:169`), re-checked inside every `submit()`:

| check | source | state 2026-07-25 |
|---|---|---|
| `live_submit` one-proof enabled | `configs/live_submit.json` | ❌ `{"enabled": false}` |
| `DUMMY_LIVE_PROOF_MODE` = `1` | process env | ❌ unset |
| `DUMMY_LIVE_PROOF_ACK` = `FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY` | process env | ❌ unset |
| command seal | `artifacts/dummy/final_report_v297.json` | ✅ `PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT` |
| `caps_strict` + registration | `configs/caps.json`, `runtime/operator_external/caps_authority_registration_v2.json` | ✅ bound to `83FCE350…` |
| adapter descriptor staged | `runtime/operator_external/livebrokerfirewall_adapter_descriptor.json` | ✅ |
| credentials resolve (signing key parses) | `.env` → `KALSHI_API_KEY_ID`, private key | ✅ from `.env` |
| proof lock clear | `artifacts/dummy/real_proof_registry.json` | ✅ cleared (Wave-87) |

**2. Session authority** — `load_session()` (`autonomy/executor.py:54`) plus a
clear kill file. A LIVE session requires `mode: "LIVE"`, the exact
`AUTONOMY_ACK`, `accounting_version >= 2`, and an unexpired `expires_at`. Any
doubt reads as SHADOW.

Both layers must hold. Neither implies the other.

### Not an operator gate: `STATE.mode` / `AccountMode.AUTONOMOUS_LIVE_CAPPED`

The handoff listed `STATE.mode != AUTONOMOUS_LIVE_CAPPED` as a blocking operator
gate. Nothing is required of the operator here: `build_brain(SessionMode.LIVE)`
sets that mode itself (`autonomy/session.py:620`) as a consequence of building a
live brain. It is an effect of arming, not a precondition for it.

The surfaces that *do* gate on it — `execution/autonomous_path.py`,
`execution/hybrid_path.py`, and the retired v4–v8 report scripts and routes
under `archive/` — are not on this route. `autonomy/` imports neither execution
module; the brain reaches the broker through `autonomy/executor.py` →
`LiveBrokerFirewall`.

The gate the handoff was missing is the session in layer 2. Without it the
executor routes to the shadow book no matter how open layer 1 is.

### Credentials come from `.env`, and the gate loads them

`KALSHI_API_KEY_ID` and `KALSHI_API_PRIVATE_KEY_PEM_PATH` live in `.env`, not the
user environment. The authority status reads `os.environ`, so
`live_session_readiness()` loads the whitelisted refs first (Wave-89) —
idempotently, never overwriting. Before that fix the arming step refused a live
session for missing credentials that were present on disk. You do not need to
export them by hand.

---

## Going live

Steps 1–3 are the operator's: they enable submission and write a risk
acknowledgement. Do not delegate them.

**1. Arm one-proof live-submit.** All four flags are required and
`--typed-confirmation` must match exactly:

```bash
python tools/operator_authority_appliance/operator_full_completion.py enable-one-proof-live-submit --operator "Chris" --reason "first live pilot, KXSOL15M series" --expires-at "2026-07-26T00:00:00Z" --typed-confirmation "I confirm live-submit is enabled for one controlled proof only and Dummy must still pass all gates before any order"
```

Writes `configs/live_submit.json` atomically with a timestamped `.bak`, binding
the current caps and descriptor hashes. It does not contact the broker.

Reverse it with `disable-live-submit` — but see the `.bak` gotcha below.

**2. Set the env gate.** PowerShell — `export` from the old bash runbook
silently no-ops:

```bash
$env:DUMMY_LIVE_PROOF_MODE="1"; $env:DUMMY_LIVE_PROOF_ACK="FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"
```

Process-scoped on purpose. The live session in step 3 runs in *this* shell and
inherits them. Do **not** `setx` these — that would leave the env gate open for
every future process, including the scheduled tasks, long after the pilot.

Confirm layer 1 reads open before continuing:

```bash
python -c "from live_firewall.firewall import live_execution_authority_status as s; import json; print(json.dumps(s(), indent=2))"
```

`execution_authority` must be `true`. If it is `false`, `blocker` names the one
failing check.

**3. Start the live session — this is the arming step.**

```bash
python scripts/run_dummy_autonomous.py start --live --hours 6 --ack "I authorize an autonomous Dummy trading session with self-managed risk under the LiveBrokerFirewall, LIMIT orders only, until I stop it"
```

`start_session` refuses unless layer 1 passes *and* a signed Kalshi balance read
clears `MIN_LIVE_SESSION_BALANCE_CENTS` (100¢) — a locally armed config is
necessary but not sufficient, the credentials must actually work. On success it
writes
`runtime/autonomy/session.json` (`accounting_version: 2`), clears any stale
`runtime/autonomy/KILL`, and loops cycles in the foreground while the session
stays valid. Watch it.

**Stop, any time:**

```bash
python scripts/run_dummy_autonomous.py stop
```

Writes the kill file and deletes the session — unconditional, no gates.

---

## Caps in force

Unchanged from the registered hash: 100¢ max single order, 500¢ per market,
500¢ daily loss, 1000¢ total live exposure, 3 open markets, 5 orders/hour,
LIMIT only, no market orders, kill switch required, Elections and Politics
blocked, 5¢ max spread, 50 bps min edge.

## What is authorized to trade

`allowed_markets: []`, `allowed_series: ["KXSOL15M"]`. Exact-ticker grants
cannot express authorization for contracts that rotate every fifteen minutes, so
the grant is series-level.

`KXSOL15M` is the contract family for `crypto_patience_confirm|sol|15m_direction|15m`,
which carries a positive lower-bound edge in
`runtime/autonomy/no_edge_map.json` (mean 0.0409, CI-lower 0.0131, 99 clusters).
Two sol scopes clear that bar; the other, `crypto_technical_foundry|sol|ladder|hourly`,
is significantly negative and is not authorized.

Expect low order frequency: because the series rotates every fifteen minutes,
typically one or two of its contracts are open at once (1 of 3,582 rows on the
2026-07-25T07:46Z board). `max_orders_per_hour: 5` is not the binding
constraint; contract availability is.

Widening the grant is a caps ceremony, not a config edit: change
`configs/caps.json`, update `PROTECTED_CAPS_SHA256` in `core/caps_authority.py`,
then reissue `runtime/operator_external/caps_authority_registration_v2.json`
against the new hash with the operator's exact acknowledgement.

---

## The ceremony is vestigial

`one-shot-prepare`, `one-shot-install`, `one-shot-check`, `one-shot-live` and the
`operator_authority_pack/` files read as though they can place an order. They
cannot, and nothing on the live path reads that pack — the descriptor the
firewall actually checks lives in `runtime/operator_external/`.

Commit `7b77b40` (2026-07-22) consolidated order creation behind the central
firewall and retired the per-runner write paths; both legacy runners are now
stubs returning `LEGACY_*_RETIRED_USE_CENTRAL_FIREWALL`. The ceremony was never
repointed at the replacement.

Two ways it misleads, both of which have cost real time:

- `one-shot-check` reports green while `one-shot-install` has errored. It
  measures gates, not whether the install ran.
- Its `ARM_CHECKS` pattern is what produced three recorded "broker attempts"
  that never contacted a broker
  (`docs/corrections/2026-07-24-phantom-broker-rejection.md`).

Use it for gate *readings* only. Ignore its verdict strings.

## Gotchas

- Piping pytest through `tail` reports `tail`'s exit code, not pytest's. Check
  `PIPESTATUS[0]` or write to a file.
- `disable-live-submit` writes a functionally-disabled but structurally
  different file than a pristine `{"enabled": false}`, breaking two hash-pinned
  tests. Restore from the `.bak`.
- `runtime/` and `artifacts/dummy/` are gitignored. The corrected proof registry
  and the caps registration exist on this box only.
- A worktree whose `runtime` is a junction to the live directory leaks the live
  `no_edge_map.json` into that worktree's suite and breaks pipeline tests.
