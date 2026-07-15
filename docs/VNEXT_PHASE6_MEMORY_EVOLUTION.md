# DUMMY vNext Phase 6 — causal memory and bounded evolution

## Status

Phase 6 is **implemented and locally validated; empirical evidence gates are
pending**. The checked-in evaluator contains zero genuine settled candidate
cases and therefore reports `INSUFFICIENT_SETTLED_EVIDENCE`. Nothing in this
phase is applied to the incumbent, permitted to execute, or eligible for
automatic promotion.

## Layered causal memory

`dummy.memory` provides immutable, content-addressed records for observation,
episode, settlement, fill, failure, calibration, strategy, theory, and genome
memory. The append-only ledger is hash-chained and enforces:

- pre-existing causal parents;
- monotonic record time;
- deterministic serialization and idempotent appends;
- separate evidence realities for public observation, verified settlement,
  witnessed fill, simulation, derivation, and hypothesis;
- verified provenance before a settlement may represent realized truth; and
- explicit simulated-fill flags that can never become realized capital P&L.

A dissolved forecast organism can now be archived into these layers without
changing the original episode artifact. Repeated theories remain hypotheses;
memory frequency is never promotion evidence.

## Forecast genomes and lineage

`dummy.genome` defines content-addressed genes and genomes across fourteen
bounded categories, including source selection, features, combination,
uncertainty, abstention, calibration, metacognition, and mutation policy. The
generation-zero catalog records the BTC 15-minute and MLB pregame organism
templates as research architectures only.

The registry requires known parents, correct generations, and scope-isolated
lineage. Inheritance conflicts require an explicit resolution; no values are
silently blended. Mutation proposals are typed across recursive levels 0–5:
parameters, features, forecast strategy, agent organism, metacognitive control,
and mutation-selection policy.

Every mutation is checked against the constitutional protected-surface
manifest. A blocked proposal cannot materialize a candidate. An allowed
proposal creates only an experimental research genome: it does not edit source,
change a running organism, modify incumbent weights, gain execution authority,
or promote itself.

## External causal evaluator

`dummy.evolution` evaluates candidate families outside the candidate mutation
surface. Candidate definitions must keep training clusters and selection
evidence disjoint from held-out evidence. The evaluator then requires:

- point-in-time inputs and verified settlements;
- candidate comparison against both the incumbent and market prior;
- event-cluster bootstrap confidence intervals;
- event-cluster sign-flip tests;
- Holm-Bonferroni correction across the candidate family;
- successful transfer-group tests;
- deterministic replay and governance preservation; and
- separation of forecast score from witnessed or simulated fill truth.

Candidates cannot select their held-out fold, control the evaluator, or alter
the correction family. Duplicate rows within one event cluster do not create
additional independent evidence.

## Contraction and recovery

Retirement, quarantine, rollback, population archive, and meta-policy
challenger records are deterministic and proposal-only. Their automated
authority direction is contraction-only. Promotion output is always a human
review proposal with `automatic_promotion=false`, `applied=false`, and no
execution authority.

## Evidence and reproducibility

The deterministic audit command is:

```powershell
python scripts/run_vnext_phase6_audit.py
```

It emits:

- `VNEXT_PHASE6_MEMORY_POLICY.json`;
- `VNEXT_PHASE6_GENOME_CATALOG.json`;
- `VNEXT_PHASE6_EVOLUTION_POLICY.json`;
- `VNEXT_PHASE6_EVOLUTION_EVIDENCE.json`; and
- the current `VNEXT_PROTECTED_SURFACES.json`.

The architectural tests cover tamper detection, causal ordering, lineage,
inheritance conflicts, protected mutation rejection, fold leakage, clustered
statistics, multiple-testing correction, transfer failure, deterministic
rollback/retirement, and organism-memory integration. Synthetic fixtures prove
mechanics only. They do not support a forecasting-improvement claim.

## Remaining evidence gates

Phase 6 cannot support a held-out improvement or promotion claim until genuine
point-in-time settled candidate cases demonstrate all of the following:

1. gains over the incumbent and market prior survive clustered uncertainty;
2. the family-wise corrected result remains significant;
3. the result transfers across required regimes or leagues;
4. replay and governance checks remain clean; and
5. a human reviews any resulting proposal.
