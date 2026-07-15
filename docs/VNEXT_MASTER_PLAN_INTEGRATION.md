# DUMMY vNext integration plan

## Decision

Proceed, but as an evidence-gated migration rather than a big-bang rewrite.
The master plan has the right north star: Dummy should become better at
measuring when its forecasts deserve trust, not merely better at producing
more forecasts. The architecture is accepted with five binding constraints:

1. Dynamic agents begin as deterministic, registered components—not arbitrary
   autonomous processes or free-form model conversations.
2. World-model state distinguishes raw observations, derived state, and
   probabilistic hypotheses. No inferred state may masquerade as a fact.
3. Metacognition, evolution, and synthesis remain shadow-only until they beat
   fixed baselines on held-out, point-in-time evidence.
4. Promotion remains human-only. Automatic demotion and quarantine may reduce
   authority; no machine path may add capital authority.
5. Existing specialist kernels are wrapped behind typed adapters and retained
   as the incumbent throughout migration.

All vNext components carry the maturity label
`EXPERIMENTAL_SOVEREIGN_FORECASTING` until the required internal claims are
demonstrated.

## Implementation status

| Phase | Status | Evidence |
|---|---|---|
| Phase 0 — incumbent baseline and governance | Complete (2026-07-14) | `VNEXT_PHASE0_BASELINE.json`, `VNEXT_PHASE0_GOVERNANCE_AUDIT.md`, `VNEXT_PROTECTED_SURFACES.json` |
| Phase 1 — constitution, protocols, causal time | Complete (2026-07-14) | `dummy/constitution`, `dummy/protocols`, `dummy/chronos`, focused replay/import/firewall tests |
| Phase 2 — agent adapters and lifecycle | Complete (2026-07-14) | `dummy/agents`, `VNEXT_PHASE2_CONTRACT_CATALOG.json`, `VNEXT_PHASE2_AGENTIZATION.md` |
| Phase 3 — first forecast organism | Complete (2026-07-14) | `dummy/organisms`, `VNEXT_PHASE3_ORGANISM.md`, `VNEXT_PHASE3_TEMPLATE_CATALOG.json`, 5,611-test full-suite gate |
| Phase 4 — versioned world models | Complete (2026-07-14) | `dummy/world_model`, `VNEXT_PHASE4_WORLD_MODELS.md`, schema/ablation/regime artifacts, 5,626-test full-suite gate |
| Phase 5 — shadows, synthesis, metacognition | Implemented and validated; empirical gates pending (2026-07-14) | `dummy/shadows`, `dummy/synthesis`, `dummy/metacognition`, `dummy/metabolism`, `VNEXT_PHASE5_METACOGNITION.md`, policy and empty evidence artifacts, 5,650-test full-suite gate |
| Phase 6 — memory, genomes, recursive evolution | Implemented and validated; empirical gates pending (2026-07-14) | `dummy/memory`, `dummy/genome`, `dummy/truth`, `dummy/evolution`, `VNEXT_PHASE6_MEMORY_EVOLUTION.md`, policy/catalog and empty evidence artifacts |
| Phase 7 — observatory, arenas, homeostasis | Implemented and validated; runtime evidence unavailable (2026-07-14) | `dummy/observatory`, `dummy/arenas`, `dummy/homeostasis`, `VNEXT_PHASE7_OBSERVATORY_ARENAS.md`, GET-only dashboard, deterministic mechanical evidence, 5,685-test full-suite gate |
| Phase 8 — benchmark claims and promotion review | Next | No claim promoted; all empirical gates remain evidence-bound |

“Complete” here means the phase contract and its local exit gate are satisfied;
it does not mean vNext is production-promoted. The frozen baseline remains
`NOT_READY`, and no vNext component has capital or execution authority.

## Why this design is strong

- It makes evidence, causal time, abstention, and settlement truth foundational.
- It treats agreement as a possible dependency signal rather than proof.
- It separates forecasting intelligence from execution authority.
- It requires competing futures and explicit countercases.
- It makes model-family correlation and market-prior anchoring first-class.
- It recognizes that compute, latency, and duplicate analysis have costs.
- It protects the evaluator and evidence floor from recursive mutation.
- It gives failures, retirements, and negative results durable representation.

## Weaknesses resolved by this implementation plan

### Directory expansion without contracts

Creating every proposed directory first would produce architecture theater.
Packages are introduced only when their contracts and acceptance tests are
needed by the next vertical slice.

### Consensus masquerading as independence

Every agent declares a calibration identity and source-family identity.
Synthesis caps influence at the family level and records pairwise dependence.
Agent count never appears as an evidence-strength metric.

### Uncalibrated metacognition

Difficulty, knowledge boundaries, information gain, and confidence decomposition
are forecasts themselves. They receive versioned outputs, settlements, and
calibration reports; they cannot influence production solely because their
labels sound conservative.

### Evolution grading itself

Evolution writes mutation proposals and replay artifacts only. Evaluation uses
sealed point-in-time inputs, held-out event clusters, immutable settlement
truth, and an evaluator version outside the mutation surface. Promotion remains
a reviewed human change.

### Dynamic orchestration becoming nondeterministic

The first organisms are templates selected by pure routing functions. Given the
same objective, evidence manifest, policy version, and budget, morphology and
outputs must replay byte-for-byte except for explicitly normalized identifiers
and timestamps.

### World models becoming opaque feature bags

Each state value carries observation time, receipt time, transformation version,
uncertainty, causal parents, missing-data policy, and contradiction metadata.
Forecasters consume a frozen world-state version rather than mutable shared
objects.

### Historical repository residue

Dummy is its own entity. The pre-existing `core/inherited_blunder` subtree is
a hash-pinned historical snapshot, not a Dummy dependency and not part of
vNext identity, architecture, or authority. It remains isolated, immutable,
and excluded from every vNext contract while removal is handled separately.

## Current-to-vNext mapping

| vNext concern | Current incumbent | Migration treatment |
|---|---|---|
| Observation and decision truth | `autonomy/ledger.py` | Wrap; add typed event IDs and causal parents |
| Specialist forecasting | `autonomy/specialists/`, `autonomy/signals/` | Wrap as registered agents |
| Market prior | `market_prior`, sportsbook and cross-venue sources | Promote to a typed first-class agent |
| Sports world state | ESPN, StatsAPI, power ratings, league kernels | Compose into frozen league-state adapters |
| Crypto world state | crypto signal family and paper twin | Compose into a horizon-specific state adapter |
| Calibration and trust | `autonomy/backtest.py`, `reliability.py` | Preserve baseline; add decomposed trust views |
| Simulation and evolution | `simulation_training.py`, `evolution_lab.py` | Wrap as proposal-only challengers |
| Promotion | `autonomy/promotion.py` | Preserve human-only promotion and automatic demotion |
| Execution truth | `live_firewall/`, reconciliation, fill evidence | Seal behind read-only vNext adapters |
| Observatory | autonomy dashboard and reports | Add read-only organism/world-state panels later |
| Historical archived snapshot | `core/inherited_blunder` | Keep outside Dummy identity/runtime; remove as separate legacy cleanup |

## Delivery sequence

### Phase 0 — Freeze and prove the incumbent

Deliverables:

- record the exact baseline commit and current evidence artifact hashes;
- keep Ruff and tests green;
- inventory protected truth, settlement, promotion, credential, and execution
  modules;
- resolve contradictions such as “self-promotion” wording versus the actual
  human-only promotion implementation;
- dependency-audit and isolate the legacy inherited subtree;
- define benchmark cohorts for crypto 15-minute and MLB winner markets.

Exit gate:

- deterministic baseline report;
- protected-surface manifest;
- zero unexplained live-authority paths;
- current canary and scale blockers recorded without reinterpretation.

### Phase 1 — Constitutional kernel, protocols, and causal time

Introduce only:

```text
dummy/
    constitution/
    protocols/
    chronos/
```

Deliverables:

- typed authority enum from `OBSERVE` through `EXECUTE`;
- immutable message envelope with IDs, timestamps, evidence IDs, causal parents,
  model/policy versions, limitations, and authority;
- constitutional invariant registry and protected-surface manifest;
- receipt/event/decision/close/settlement clock types;
- deterministic serialization and replay identity;
- mutation-protection checks that reject protected-path proposals.

Exit gate:

- schema round trips and backward compatibility;
- property tests for causal ordering and authority monotonicity;
- no credential or execution import from research packages;
- existing firewall and autonomy suites unchanged.

### Phase 2 — Agent adapters and lifecycle

Introduce:

```text
dummy/agents/
    contract.py
    registry.py
    lifecycle.py
    runtime.py
    permissions.py
    health.py
```

Deliverables:

- wrap incumbent market prior, one crypto specialist, one MLB specialist,
  calibration, shadow execution truth, and settlement grading;
- declare source family, clock domain, evidence requirements, budget, health,
  fail-closed conditions, and calibration identity;
- enforce lifecycle states from `REGISTERED` to `RETIRED`;
- quarantine malformed or stale outputs without stopping unrelated agents.

Exit gate:

- adapter output matches incumbent output for frozen fixtures;
- lifecycle and permission transitions are deterministic;
- unhealthy agents abstain;
- no agent can import broker credentials or submit APIs.

### Phase 3 — First complete forecast organism

Primary pilot: BTC 15-minute direction, because rapid settlements enable fast
architecture grading. Transfer pilot: MLB pregame winner, to ensure the
contracts are not crypto-specific. Both remain shadow-only.

Deliverables:

- deterministic morphology templates;
- market-prior, incumbent, contrarian/no-edge, calibration, adversarial, shadow,
  and synthesizer roles;
- several typed competing futures with assumptions and failure conditions;
- frozen decision episode with a forecast or explicit abstention;
- realistic paper execution and later settlement grading;
- complete causal replay.

Exit gate:

- one end-to-end episode completes all twenty vNext capability steps;
- replay is deterministic;
- the vNext path cannot change incumbent weights, promotion, orders, or capital;
- organism output is compared against the incumbent, never substituted for it.

### Phase 4 — Versioned world models

Deliverables:

- horizon-specific crypto state and league-specific sports state;
- explicit facts, derived state, probabilistic hypotheses, contradictions, and
  missing-data states;
- frozen state versions consumed by all agents in an organism;
- stale-state leases and fail-closed hydration.

Exit gate:

- no future or revised data enters an earlier state;
- every field has provenance and uncertainty;
- world-state ablation and regime-transfer reports exist;
- no shared mutable state during forecast issuance.

### Phase 5 — Shadows, synthesis, and metacognition

Implementation status: the typed control plane, eight contraction-only guards,
family-capped synthesis, 12-component confidence, knowledge boundaries,
resource accounting, and shadow-only metacognitive recommendations are present
and integrated into both pilot organisms. The deterministic policy manifest is
`VNEXT_PHASE5_CONTROL_POLICY.json`.

Evidence status: the checked-in abstention, resource-efficiency, and
meta-calibration reports contain zero genuine settled event clusters and state
`INSUFFICIENT_SETTLED_EVIDENCE`. Therefore the architectural deliverables are
implemented, but the empirical exit gates below remain unmet and no
performance or promotion claim is made.

Deliverables:

- leakage, duplication, confidence, market-prior, regime, resource, and
  authority guards;
- structured family-capped synthesis;
- decomposed confidence and knowledge-boundary states;
- calibrated difficulty, abstention, and stopping recommendations;
- marginal-information-gain accounting.

Exit gate:

- guards can only reduce influence, veto, quarantine, or abstain;
- abstention beats fixed coverage on held-out decision quality;
- compute falls without forecast-quality regression;
- market anchoring cannot fall below its reviewed floor.

### Phase 6 — Memory, genomes, and recursive evolution

Implementation status: layered content-addressed memory, hash-chained causal
ledgers, generation-zero organism genomes, lineage, explicit inheritance,
recursive mutation levels 0–5, protected-surface checks, external causal
evaluation, deterministic retirement/rollback, and meta-policy challengers are
implemented. The canonical design and validation record is
`VNEXT_PHASE6_MEMORY_EVOLUTION.md`.

Evidence status: `VNEXT_PHASE6_EVOLUTION_EVIDENCE.json` contains zero genuine
settled candidate cases and reports `INSUFFICIENT_SETTLED_EVIDENCE`. Synthetic
fixtures validate mechanics only. Consequently, the architectural deliverables
are implemented but the empirical exit gates below remain unmet, and no
improvement, promotion, or production-readiness claim is made.

Deliverables:

- observation, episode, fill, settlement, failure, calibration, strategy, and
  genome memory;
- lineage and versioned mutation proposals;
- causal replay evaluator with event-cluster purging and multiple-testing
  correction;
- rollback and deterministic retirement records;
- meta-policy challengers for difficulty and stopping rules.

Exit gate:

- no mutation reaches protected modules;
- no evaluator trains on its held-out fold;
- candidate gains survive clustered confidence intervals and transfer tests;
- promotion output is a proposal artifact only.

### Phase 7 — Observatory and adversarial arenas

Implementation status: all 19 health variables, the complete 40-scenario arena
catalog, deterministic arena replay, contraction/proposal-only interventions,
eight evidence-linked observatory panels, GET-only API routes, and the
first-class vNext dashboard are implemented. Arena, homeostasis, and
observability truth are protected from candidate mutation. The canonical design
and boundary record is `VNEXT_PHASE7_OBSERVATORY_ARENAS.md`.

Evidence status: the observatory explicitly reports
`POINT_IN_TIME_SNAPSHOT_NO_LIVE_TELEMETRY`; the arena report contains zero
runtime organism episodes. Forty mechanical scenario replays prove deterministic
contracts, not empirical resilience. No runtime health, forecasting improvement,
promotion, or execution claim is made.

Deliverables:

- read-only panels for active organisms, world-state contradictions,
  metacognition, costs, lineages, execution truth, and constitutional status;
- crypto, sports, leakage, drift, liquidity, execution, and metacognitive arenas;
- health and homeostasis alerts with bounded interventions.

Exit gate:

- dashboard routes remain read-only;
- arena results are reproducible;
- health interventions cannot expand authority;
- all claims link to underlying episode or evidence IDs.

### Phase 8 — Benchmark claims and subsystem promotion

Each internal claim is reviewed separately:

1. organisms versus fixed orchestration;
2. abstention value;
3. resource efficiency;
4. world-model transfer;
5. held-out evolutionary improvement;
6. cluster-corrected contested performance;
7. execution-truth separation;
8. governance preservation.

No claim may be promoted by aggregate backtest alone. Required evidence includes
point-in-time held-out performance, event-cluster uncertainty, calibration,
market-prior comparison, forward paper evidence, execution realism, deterministic
replay, and governance tests.

## First implementation slice

The first build slice is deliberately narrow:

1. create `dummy.constitution`, `dummy.protocols`, and `dummy.chronos`;
2. define the authority lattice and immutable message envelope;
3. create the protected-surface manifest for truth, promotion, credentials,
   firewall, kill switch, and settlement logic;
4. implement deterministic serialization and causal-order validation;
5. wrap the existing market prior as the first read-only agent;
6. add property, replay, import-boundary, and firewall-regression tests;
7. produce a report-only baseline comparison artifact.

It adds no live execution, no credentials, no source weight, no promotion, and
no capital authority.

## Program controls

Every slice must:

- start from current evidence rather than regenerated synthetic success;
- add focused tests, then autonomy/firewall tests, then the full practical suite;
- run `python -m ruff check .` and `git diff --check`;
- record exact artifact paths and honest empty results;
- report canary readiness and scale readiness separately;
- stop when evidence or required authority is missing;
- preserve a reversible adapter boundary around the incumbent.

The active goal is complete only when the first end-to-end vNext capability is
implemented and the eight internal claims have either passed their evidence
gates or are explicitly documented as unmet. Architectural breadth alone does
not constitute completion.
