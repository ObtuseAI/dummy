# Operator Env Wizard

Operator-side helper that removes the clerical block of setting six env variables, then drives the
**existing** Operator Authority Appliance. It never lets Dummy self-authorize, never creates
`runtime/approvals` itself (only the appliance `install-authority-pack` does, with exact confirmation),
never modifies live-submit/caps, never injects a broker adapter, never calls the Dummy execute-once
script directly, and never runs live-proof without the exact env gate. No Dummy stage/gate/V305+ added.

Exit codes: `0` success · `2` missing/mismatched operator input · `3` subprocess failure · `4` safety rejection.

## Commands
| Command | Writes? | Purpose |
|---|---|---|
| `status` | no | Report which env vars are set + exactness of phrase/ack/install/gate. |
| `print-export-template` | no | Shell-safe `export` template with exact phrase/ack/install; env gate commented. |
| `write-env-file --output <p> ...` | operator .env only | Write operator-owned `.env`; rejects fuzzy/broad/market/scale approvals. |
| `print-build-command` | no | Print exact `build-authority-pack` command from current env (or list missing vars). |
| `print-full-operator-sequence` | no | Print the safe end-to-end sequence with stop points. |
| `build-pack-from-env` | operator pack dir only | Shell to appliance `build-authority-pack`. |
| `verify-pack-from-env` | no | Shell to appliance `verify-authority-pack`. |
| `install-pack-from-env` | runtime/approvals (via appliance) | Requires exact `DUMMY_AUTHORITY_INSTALL_CONFIRM`. |
| `run-checks-from-env` | no | Shell to appliance `run-authority-checks` (no execute-once). |
| `run-live-proof-from-env` | conditional | Requires exact env gate; shells to appliance `run-live-proof-once` only. |

## Required env vars
`DUMMY_OPERATOR_NAME`, `DUMMY_OPERATOR_REASON`, `DUMMY_OPERATOR_EXPIRES_AT`, `DUMMY_AUTHORITY_PACK_DIR`,
`DUMMY_TYPED_APPROVAL`, `DUMMY_RISK_ACK`, plus (for later phases) `DUMMY_AUTHORITY_INSTALL_CONFIRM`,
`DUMMY_LIVE_PROOF_MODE=1`, `DUMMY_LIVE_PROOF_ACK=FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY`.

## Flow
```
python tools/operator_authority_appliance/operator_env_wizard.py print-export-template > op.env   # fill, then source
source op.env
python tools/operator_authority_appliance/operator_env_wizard.py build-pack-from-env
python tools/operator_authority_appliance/operator_env_wizard.py verify-pack-from-env
# operator externally enables live-submit, confirms caps, injects LiveBrokerFirewall adapter
export DUMMY_AUTHORITY_INSTALL_CONFIRM="I authorize installing these operator-created authority files into Dummy runtime"
python tools/operator_authority_appliance/operator_env_wizard.py install-pack-from-env
python tools/operator_authority_appliance/operator_env_wizard.py run-checks-from-env
export DUMMY_LIVE_PROOF_MODE=1 DUMMY_LIVE_PROOF_ACK=FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY
python tools/operator_authority_appliance/operator_env_wizard.py run-live-proof-from-env   # ONE attempt, auto-lock
```
Chat approval is never accepted. Hard max one attempt.
