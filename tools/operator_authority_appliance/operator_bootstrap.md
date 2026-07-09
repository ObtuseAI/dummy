# Operator Bootstrap

One-stop operator-side orchestrator that chains the **existing** tools — `operator_env_wizard.py` and
`operator_authority_appliance.py` — to remove clerical friction in one command. It adds no Dummy
architecture, never self-authorizes Dummy, never creates `runtime/approvals` by default, never modifies
live-submit/caps, never injects a broker adapter, never contacts a broker, never calls the Dummy
execute-once script directly, and never runs live-proof without the exact env gate. All validation is
delegated to the existing tools.

Exit codes: `0` success · `2` missing operator input · `3` subprocess failure · `4` safety rejection.

## Commands
| Command | Writes? | Purpose |
|---|---|---|
| `status` | no | Compact blocker table (env vars, seal, gate, install, runtime, proof-lock, stop rule). |
| `generate-env --output <p> ...` | operator env file only | Reuse wizard `write-env-file`; rejects fuzzy/broad/market/scale approval. |
| `generate-env-template [--output <p>]` | template only | Ready-to-edit `NOT_APPROVAL` env template (gate + install commented). |
| `build-and-verify-pack` | operator pack dir only | Requires 6 build vars; calls wizard build then verify. |
| `prepare-install-command` | no | Verify + print exact install command/env (does not install). |
| `install-if-confirmed` | runtime/approvals (via appliance) | Requires exact `DUMMY_AUTHORITY_INSTALL_CONFIRM`. |
| `authority-checks` | no | Wizard `run-checks-from-env` + exact blocker (no live proof). |
| `prepare-live-proof-command` | no | Checks + print env-gate + run command (does not run). |
| `run-live-proof-if-ready` | conditional | Requires exact env gate; wizard `run-live-proof-from-env` only. |
| `max-progress` | template (+ pack/install only if env present) | Do every safe step; stop before live/install unless authorized. |

## max-progress default (no env)
Writes only `operator_authority_pack/operator_authority.env.template` (NOT_APPROVAL), prints blocker
table + exact next command, verdict `OPERATOR_ENV_REQUIRED`. No pack, no runtime/approvals, no live proof.

## Fastest operator path
```
python tools/operator_authority_appliance/operator_bootstrap.py max-progress   # writes template
# edit operator_authority_pack/operator_authority.env.template → real .env, then:
source operator_authority_pack/operator_authority.env
python tools/operator_authority_appliance/operator_bootstrap.py max-progress   # builds+verifies pack, stops for external config
# operator externally enables live-submit + confirms caps + injects LiveBrokerFirewall adapter
export DUMMY_AUTHORITY_INSTALL_CONFIRM="I authorize installing these operator-created authority files into Dummy runtime"
python tools/operator_authority_appliance/operator_bootstrap.py max-progress   # installs, checks, stops for env gate
export DUMMY_LIVE_PROOF_MODE=1 DUMMY_LIVE_PROOF_ACK=FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY
python tools/operator_authority_appliance/operator_bootstrap.py max-progress   # ONE live attempt if fully armable
```
Chat approval never accepted. Hard max one attempt. Auto-lock after attempt.
