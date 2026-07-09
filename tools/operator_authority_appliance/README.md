# Operator Authority Appliance (external, fail-closed)

External operator-side toolchain for the DUMMY live-proof path. It lives **outside** Dummy's
self-authorization path (`predator_mesh/*`). Dummy never self-authorizes: it does not create approval
files, `runtime/approvals`, live-submit config, caps, or broker adapters. This appliance only helps a
human operator **generate / verify / install operator-owned** authority artifacts, and only after
explicit typed local confirmation.

No command here submits an order, contacts a broker, enables live-submit, or modifies caps by default.
A real submit happens only when the operator supplies full external authority **and** the exact env
gate, at which point the appliance invokes the **existing, unmodified** Dummy execute-once script.

This is not a Dummy stage/gate and does not add V305+ architecture.

## Required exact approval phrase
```
I approve Dummy to run one controlled production pilot through LiveBrokerFirewall only, with no market orders, strict caps, live-submit already operator-enabled, per-order fail-closed checks, and immediate pilot auto-lock
```

## Required env gate
```
DUMMY_LIVE_PROOF_MODE=1
DUMMY_LIVE_PROOF_ACK=FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY
```

## Commands
| Command | Writes? | Purpose |
|---|---|---|
| `status` | no | Report locked state, missing authority artifacts, env gate. |
| `init-templates` | templates/ only | Write `NOT_APPROVAL` templates. |
| `build-authority-pack --output <dir> ...` | operator dir only | Build operator-owned authority pack after exact typed approval. |
| `verify-authority-pack --source <dir>` | no | Validate a pack (phrase, hashes, no market/scale/autonomy). |
| `install-authority-pack --source <dir> --operator-confirm-install "..."` | runtime/approvals | ONLY command that may create `runtime/approvals`. Copies approval file only. |
| `print-runbook` | no | Print the exact gated command sequence. |
| `dry-run-all` | no | Run safe read-only Dummy status scripts. |
| `run-authority-checks` | no | Run import wizard + armability + command seal (no execute-once). |
| `run-live-proof-once` | conditional | Invoke existing execute-once ONCE, then intake/reconcile/route — only if env gate + seal ready + proof lock clear. |

## Operator flow
```
python tools/operator_authority_appliance/operator_authority_appliance.py status
python tools/operator_authority_appliance/operator_authority_appliance.py init-templates
python tools/operator_authority_appliance/operator_authority_appliance.py build-authority-pack \
  --output ~/dummy_authority \
  --operator "chris" --reason "controlled pilot" --expires-at "2026-07-07T21:00:00Z" \
  --proof-target FIRST_REAL_PILOT_PROOF \
  --typed-approval "I approve Dummy to run one controlled production pilot through LiveBrokerFirewall only, with no market orders, strict caps, live-submit already operator-enabled, per-order fail-closed checks, and immediate pilot auto-lock" \
  --acknowledge-risk "I understand this can place one real limit order only through LiveBrokerFirewall after all Dummy gates pass"
python tools/operator_authority_appliance/operator_authority_appliance.py verify-authority-pack --source ~/dummy_authority
# Operator (not Dummy) enables live-submit, confirms caps, injects the LiveBrokerFirewall adapter externally.
python tools/operator_authority_appliance/operator_authority_appliance.py install-authority-pack \
  --source ~/dummy_authority \
  --operator-confirm-install "I authorize installing these operator-created authority files into Dummy runtime"
python tools/operator_authority_appliance/operator_authority_appliance.py run-authority-checks
DUMMY_LIVE_PROOF_MODE=1 DUMMY_LIVE_PROOF_ACK=FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY \
  python tools/operator_authority_appliance/operator_authority_appliance.py run-live-proof-once
```

Hard max one attempt. Auto-lock after attempt. No repeat. Chat approval alone is never accepted.
