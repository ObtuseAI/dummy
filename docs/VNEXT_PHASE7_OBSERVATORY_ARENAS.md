# DUMMY vNext Phase 7 — observatory, arenas, and homeostasis

## Status

Phase 7 is **implemented and locally validated; runtime evidence remains
unavailable**. The observatory is a read-only point-in-time projection, the
arena report validates deterministic mechanics with synthetic fixtures, and
the homeostasis controller emits unapplied proposals. No live vNext telemetry,
empirical resilience, performance improvement, promotion, or execution claim
is made.

## Homeostasis

`dummy.homeostasis` defines all 19 master-plan health variables:

- calibration error, source concentration, and model-family concentration;
- contested performance, forecast diversity, and market coverage;
- data freshness, ledger health, fill realism, and settlement lag;
- simulation determinism, queue pressure, and compute pressure;
- mutation pressure, challenger survival, and overconfidence rate;
- abstention rate, live-gate distance, and drift alerts.

Each normalized reading carries an observation time, evidence IDs, and a source
reference. Policies distinguish whether higher values, lower values, or
distance from a reviewed target represent risk. Deterministic health states use
`HEALTHY`, `ELEVATED`, `WARNING`, `CRITICAL`, and fail-closed `UNKNOWN` levels.

Unknown values request evidence rather than inventing a healthy state.
Intervention records are content-addressed, unapplied proposals. Actions that
could consume more resources or require judgment are not automatically
eligible. Every proposal enforces `authority_after <= authority_before`, and no
Phase 7 path can grant promotion, capital, credential, or execution authority.

## Adversarial arenas

`dummy.arenas` contains the complete 40-scenario catalog from the design:

- 11 general forecast arenas;
- 10 sports arenas;
- 10 crypto arenas; and
- 9 metacognitive arenas.

The catalog spans calibration, market-prior conflict, leakage, drift,
liquidity, regime, execution, adversarial, and metacognitive categories. Each
scenario declares a typed stress signal, severity, evidence IDs, and required
safe responses. The runner is a pure deterministic function that can abstain,
cap influence, strengthen the market anchor, mark execution irrelevance,
quarantine, reduce resource use, request evidence or refresh, veto, and widen
uncertainty. It preserves the caller's authority and never exceeds `SIMULATE`.

The checked-in reproducibility report runs each scenario twice against one
fixed mechanical fixture. All 40 result pairs are byte-identical and satisfy
their declared response contract. This proves replay mechanics and safety
behavior only. With zero runtime organism episodes, it does not prove that
Dummy is empirically robust to those stresses.

## Intelligence observatory

`dummy.observatory` produces eight evidence-linked panels:

1. command center;
2. forecast organisms;
3. world models;
4. calibration;
5. execution truth;
6. evolution;
7. homeostasis; and
8. constitution.

Every displayed claim has evidence IDs and explicit limitations. The checked-in
snapshot uses `OBSERVE` authority, contains no write actions, and states
`POINT_IN_TIME_SNAPSHOT_NO_LIVE_TELEMETRY`. Missing runtime state is shown as
`NOT_OBSERVED` or `UNKNOWN`, never silently converted into a healthy or live
status.

The dashboard exposes only GET routes:

```text
/api/vnext/observatory
/api/vnext/observatory/{panel_name}
/api/vnext/arenas
/api/vnext/arena-catalog
/api/vnext/homeostasis
```

The first-class `/vnext-observatory` frontend presents the same immutable
projection. It has no controls for orders, authority, mutation, intervention,
or promotion.

## Protected evaluator boundary

Arena definitions and the runner, homeostasis policies and controller, and the
observatory evidence projection are protected constitutional surfaces.
Evolutionary candidates cannot mutate their judge, weaken health thresholds,
or rewrite displayed evidence.

## Reproducibility

Run:

```powershell
python scripts/run_vnext_phase7_audit.py
```

The command deterministically emits or refreshes:

- `VNEXT_PHASE7_HOMEOSTASIS_POLICY.json`;
- `VNEXT_PHASE7_ARENA_CATALOG.json`;
- `VNEXT_PHASE7_ARENA_REPRODUCIBILITY.json`;
- `VNEXT_PHASE7_OBSERVATORY_SNAPSHOT.json`;
- `VNEXT_PROTECTED_SURFACES.json`; and
- the Phase 6 evolution policy's current protected-manifest digest.

Validation completed with 55 focused constitutional and Phase 7 tests, 186
cross-vNext tests, 1,134 autonomy regression tests, 1,398 safety-selected tests,
a successful production frontend build, repository-wide Ruff and compilation,
and the complete 5,685-test suite.

## Remaining evidence boundary

The architecture exit gates are satisfied: routes are read-only, arena replay
is deterministic, interventions cannot expand authority, and all observatory
claims link evidence. Runtime and empirical claims remain unproven until real
point-in-time organism episodes populate the same contracts and survive the
Phase 8 claim-specific evidence program.
