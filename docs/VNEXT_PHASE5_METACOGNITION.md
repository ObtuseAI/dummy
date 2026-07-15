# DUMMY vNext Phase 5 shadows, synthesis, and metacognition

Status: **IMPLEMENTED_VALIDATED_EVIDENCE_GATE_PENDING**

Phase 5 adds a contraction-only control layer around the first forecast
organisms. It reviews causal provenance, combines evidence by independent
source family, decomposes confidence, states knowledge boundaries, accounts
for information and resource costs, and recommends whether analysis should
continue, narrow, or abstain.

The controls remain research-only. They cannot grant execution or promotion
authority, increase a source's influence, change an incumbent, contact a
broker, modify capital, or automatically acquire more compute. Current
metacognitive mappings and the information-gain proxy are explicitly
uncalibrated. Except for safety contraction, their recommendations are inert.

## Eight contraction-only guards

`dummy/shadows` runs exactly one finding from each reviewed guard:

1. **Provenance** detects unavailable or unsupported state and requests
   evidence while reducing affected-family influence.
2. **Leakage** vetoes future-received evidence and mixed decision-time state.
3. **Confidence** requires typed uncertainty and calibration evidence.
4. **Duplication** detects aliases and caps their shared family rather than
   counting correlated messages repeatedly.
5. **Resource** narrows, abstains, or terminates when measured usage approaches
   or exceeds a reviewed budget.
6. **Market prior** requires one fresh market-price source and enforces the
   reviewed 0.50 weight floor.
7. **Regime** requests evidence or contracts influence when regime relevance
   is unknown or mismatched.
8. **Authority** terminates any attempt to obtain execution, automatic
   promotion, incumbent substitution, or non-shadow realization.

The action lattice is monotone: `OBSERVE`, `DOWNGRADE`, `REQUEST_EVIDENCE`,
`REQUIRE_MARKET_PRIOR`, `QUARANTINE_SOURCE`, `VETO`, `REQUIRE_ABSTENTION`, and
`TERMINATE`. No guard action can increase confidence, influence, budget, or
authority. Serialized reviews revalidate the same boundary when read back.

## Structured evidence synthesis

`dummy/synthesis` replaces unstructured averaging with deterministic
family-capped allocation:

- exactly one fresh `market-price` prior is mandatory;
- the prior retains at least 0.50 of total influence;
- a calibrated non-market family is capped at 0.35;
- an entirely uncalibrated family is advisory and capped at 0.15;
- a stale source receives zero weight;
- aliases divide one family allocation instead of multiplying it;
- shadow caps can only lower the reviewed family cap;
- disagreement widens the forecast interval;
- fees and half-spread are deducted before an edge claim.

The result records normalized source and family weights, the enforced prior
floor, calibration state, uncertainty interval, dominant evidence,
counterevidence, excluded sources, and policy version. Missing or stale market
priors fail closed rather than silently switching to a model-only forecast.

## Metacognitive state

`dummy/metacognition` reports 12 independent confidence components: model,
evidence completeness, evidence freshness, data reliability, regime
familiarity, historical analogue strength, calibration reliability, market
agreement, source independence, causal confidence, forecast stability, and
settlement support. Final confidence is the minimum critical component, not an
average that can hide a zero-evidence weakness.

Knowledge is classified as `KNOWN`, `PARTIALLY_KNOWN`, `UNKNOWN`, `UNSTABLE`,
`UNOBSERVABLE`, or `OUTSIDE_AUTHORITY`. Difficulty, disagreement, strategy,
abstention, stopping, and resource recommendations carry their calibration
identity and whether they were applied. An uncalibrated recommendation cannot
apply `CONTINUE`, expand evidence, add agents, or increase resources. Only
`ABSTAIN`, `TERMINATE`, and `QUARANTINE_SOURCE` may be applied without verified
meta-calibration, because those actions contract risk.

## Resource and marginal-information accounting

`dummy/metabolism` records provider calls, data fetches, messages, payload and
storage bytes, simulations, Monte Carlo paths, agent count, CPU, peak memory,
wall time, replay time, and hydration time. Unknown measurements remain
`null`; they are never replaced with zero.

The initial information-gain estimate is labeled `UNCALIBRATED_PROXY`.
Marginal utility combines it with expected calibration and decision value only
when critical resource costs are known. When CPU, memory, or wall time is
unmeasured, the utility claim is refused and the only automatic-safe
recommendation is to narrow scope. The proxy cannot authorize additional
analysis or budget.

## Organism integration

The Phase 3 BTC 15-minute and MLB pregame organisms now pass their single
frozen Phase 4 state version through the shadow controller and synthesizer.
The issued decision embeds the full guard review, structured synthesis,
confidence decomposition, knowledge boundary, metacognitive state, resource
ledger, and unresolved or measured marginal utility. Replay remains
byte-identical, and the execution and promotion boundaries remain sealed.

## Evidence reports and current non-claims

`scripts/run_vnext_phase5_audit.py` accepts verified, settled evaluation cases
with unique event-cluster IDs and deterministically emits:

- `VNEXT_PHASE5_CONTROL_POLICY.json`;
- `VNEXT_PHASE5_ABSTENTION_VALUE.json`;
- `VNEXT_PHASE5_RESOURCE_EFFICIENCY.json`; and
- `VNEXT_PHASE5_METACOGNITION_CALIBRATION.json`.

The three empirical reports require at least 100 unique settled clusters by
default. The checked-in reports contain zero cases and therefore state
`INSUFFICIENT_SETTLED_EVIDENCE`. They do not prove that selective abstention
beats fixed coverage, resource-aware control reduces compute without quality
regression, or confidence and difficulty estimates are calibrated.

Accordingly, the Phase 5 software contract is implemented and locally
validated, but its empirical exit gates remain open. No Phase 5 output is
eligible for production promotion, and the Phase 0 baseline remains
`NOT_READY`.

## Validation

Validation completed on 2026-07-14:

- focused Phase 5 plus organism tests: **51 passed**;
- complete cross-vNext family: **151 passed**;
- complete autonomy family: **1,134 passed**;
- expanded firewall, secret, live-submit, no-order, and order-bypass family:
  **400 passed**;
- repository-wide Ruff and Python compilation: **passed**;
- full repository suite: **5,650 passed in 411.37 seconds**;
- deterministic artifact regeneration and `git diff --check`: **passed**.
