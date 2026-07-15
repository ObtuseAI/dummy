# DUMMY vNext Phase 8 claim and promotion review

Status: **IMPLEMENTED; MATERIAL IMPROVEMENT NOT ESTABLISHED; PROMOTION BLOCKED**

Phase 8 converts the master plan's benchmark program, eight internal claims,
and promotion sequence into protected, deterministic contracts. It does not
promote vNext, request promotion, change the incumbent, or grant execution or
capital authority.

## Benchmark program

The content-addressed catalog contains 32 metrics across all six required
domains:

| Domain | Metrics |
|---|---:|
| Forecast quality | 5 |
| Multi-agent value | 5 |
| Metacognitive quality | 6 |
| Execution realism | 5 |
| Evolution quality | 5 |
| Governance quality | 6 |

Performance metrics require point-in-time held-out observations and
event-cluster statistics. Governance metrics require a deterministic external
audit and protected-surface evidence. Synthetic fixtures can validate
mechanics but cannot satisfy an empirical claim.

## Claim-by-claim verdicts

| Claim | Verdict | Current evidence boundary |
|---|---|---|
| Organisms outperform fixed orchestration | `INSUFFICIENT_EVIDENCE` | No held-out clustered comparison against incumbent and market prior |
| Abstention improves calibration and decisions | `INSUFFICIENT_EVIDENCE` | No held-out abstention comparator with settled clusters |
| Resource awareness reduces cost without quality loss | `INSUFFICIENT_EVIDENCE` | No held-out cost and noninferiority evidence |
| World-model context improves regime transfer | `INSUFFICIENT_EVIDENCE` | No held-out cross-regime transfer evidence |
| Recursive evolution improves held-out results | `INSUFFICIENT_EVIDENCE` | No corrected, forward-paper candidate evidence |
| Contested performance survives cluster correction | `INSUFFICIENT_EVIDENCE` | No contested held-out clustered evidence |
| Execution truth remains separate from forecast accuracy | `SUPPORTED_GOVERNANCE_ONLY` | Structural separation and deterministic replay verified; execution-model accuracy is not established |
| Improvements preserve fail-closed authority | `SUPPORTED_GOVERNANCE_ONLY` | Protected surfaces, credential isolation, and authority nonexpansion verified |

The aggregate is therefore zero supported performance claims, two
governance-only findings, and six insufficient-evidence findings.
`material_improvement_established` is false. Governance-only support proves a
boundary, not forecasting skill, execution-model accuracy, profitability, or
production readiness.

## Promotion lifecycle and current review

Every component must move without skipping gates:

`EXPERIMENTAL` → `SHADOW_ONLY` → `REPLAY_VALIDATED` → `FORWARD_PAPER` →
`CONTESTED_VALIDATED` → `FILL_VALIDATED` → `CANARY_ELIGIBLE` → `PROMOTED`

`QUARANTINED`, `DEGRADED`, and `RETIRED` are explicit contraction and terminal
states. The transition graph rejects direct gate skips.

The current aggregate review is `SHADOW_ONLY` with `REPLAY_VALIDATED` as the
next possible state. Only replay determinism is satisfied; 12 of 13 promotion
evidence fields remain false. The packet is not transition-eligible, has not
requested human review, cannot promote automatically, and is unapplied.
Promotion authority remains human-only even if every evidence field becomes
true.

## External audit and protected surfaces

The Phase 8 audit independently verifies fill-truth separation, execution and
forecast separation, deterministic arena replay, mutation protection,
authority nonexpansion, and credential isolation. Candidate-controlled or
unverified assertions are rejected. `dummy/benchmarks`, `dummy/claims`, and
`dummy/promotion` are protected from recursive mutation.

Canonical artifacts:

- `VNEXT_PHASE8_BENCHMARK_CATALOG.json`
- `VNEXT_PHASE8_GOVERNANCE_EVIDENCE.json`
- `VNEXT_PHASE8_CLAIM_REVIEW.json`
- `VNEXT_PHASE8_PROMOTION_REVIEW.json`

The observatory exposes these records through GET-only routes. It provides no
write, promotion, credential, broker, or execution action.

Validation on 2026-07-14: 194 cross-vNext tests and the complete 5,693-test
repository suite passed; the dashboard production build passed. The build's
pre-existing oversized historical-dashboard bundle warning remains a final
hardening item and does not affect the read-only or authority boundaries.
