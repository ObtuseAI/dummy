# Operator Full Completion

Top-level one-shot driver that sequences the existing operator tools
(`operator_bootstrap` → `operator_env_wizard` → `operator_authority_appliance`) so the remaining
real-proof path runs in one local command sequence. Adds no Dummy architecture, never self-authorizes
Dummy, never creates `runtime/approvals` by default, never modifies live-submit/caps, never injects a
broker adapter, never contacts a broker, never calls the Dummy execute-once script directly (only via the
appliance `run-live-proof-once`), and never runs live-proof without the exact env gate.

Exit codes: `0` ok · `2` missing/mismatched operator input · `3` subprocess failure · `4` safety rejection · `5` external dependency missing.

## Commands
| Command | Writes? | Purpose |
|---|---|---|
| `status` | no | Concise state + first hard blocker. |
| `doctor` | doctor report only | Full non-live diagnosis + `operator_full_completion_doctor.json`. |
| `one-shot-prepare --operator ... --typed-approval ... --risk-ack ...` | operator env + pack only | Generate env, build+verify pack; rejects fuzzy/broad/market/scale. No install. |
| `one-shot-install --authority-pack-dir ... --operator-confirm-install ...` | runtime/approvals (via appliance) | Install approval file with exact confirmation only. |
| `one-shot-check` | no | Authority checks + seal + classify; no live proof. |
| `one-shot-live` | conditional | ONLY live command; requires exact env gate + armable seal + clear proof lock; calls appliance `run-live-proof-once` only. |
| `full-auto` | conditional | Do every safe step from env; stop before install/live unless authorized. |
| `print-final-runbook` | no | Shortest exact final sequence with stop points. |

## First hard blocker classes
`MISSING_OPERATOR_VALUES`, `AUTHORITY_PACK_NOT_BUILT`, `AUTHORITY_PACK_NOT_VERIFIED`,
`INSTALL_CONFIRMATION_MISSING`, `LIVE_SUBMIT_CAPS_EXTERNAL_MISSING`, `COMMAND_SEAL_BLOCKED`,
`ENV_GATE_MISSING`, `PROOF_ALREADY_ATTEMPTED`, `READY_FOR_LIVE_PROOF`.

## Shortest operator path
```
python tools/operator_authority_appliance/operator_full_completion.py one-shot-prepare \
  --operator "chris" --reason "controlled pilot" --expires-at "2026-07-08T21:00:00Z" \
  --authority-pack-dir "operator_authority_pack" \
  --typed-approval "I approve Dummy to run one controlled production pilot through LiveBrokerFirewall only, with no market orders, strict caps, live-submit already operator-enabled, per-order fail-closed checks, and immediate pilot auto-lock" \
  --risk-ack "I understand this can place one real limit order only through LiveBrokerFirewall after all Dummy gates pass"
# EXTERNAL: operator enables live-submit, confirms caps, injects LiveBrokerFirewall adapter
export DUMMY_AUTHORITY_INSTALL_CONFIRM="I authorize installing these operator-created authority files into Dummy runtime"
python tools/operator_authority_appliance/operator_full_completion.py one-shot-install --authority-pack-dir "operator_authority_pack" --operator-confirm-install "$DUMMY_AUTHORITY_INSTALL_CONFIRM"
python tools/operator_authority_appliance/operator_full_completion.py one-shot-check
export DUMMY_LIVE_PROOF_MODE=1 DUMMY_LIVE_PROOF_ACK=FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY
python tools/operator_authority_appliance/operator_full_completion.py one-shot-live
```
`full-auto` runs all of the above as far as the current env safely allows. Hard max one attempt, auto-lock.
