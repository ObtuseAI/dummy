# Dummy recursive evolution lab

The evolution lab is Dummy's autonomous, quarantined scientific loop. It
improves research candidates every hour without granting the loop permission
to change production code, forecast weights, risk caps, orders, or capital.

It also retains a small quality-diversity archive of out-of-sample research
genomes. Candidates are preselected only from settled training data, measured
on a purged future fold, and retained one-per-niche across model anchoring,
risk posture, edge selectivity, and activity. Archive elites seed only the
next bounded research population. Adaptive mutation pressure changes only
after new settled evidence, and each candidate records parent lineage plus its
evidence fingerprint. None of these mechanisms selects production policy.

## Recursive loop

1. Fingerprint immutable point-in-time decisions and settlements.
2. Advance a generation only when the evidence fingerprint changes.
3. Preserve the current research genome as the mutation parent.
4. Generate up to 96 bounded local mutations and broad lattice challengers.
5. Select candidates only on settlements available before each test fold.
6. Purge test markets whose event cluster appeared in training.
7. Replay the selected candidate on later folds under baseline, wide-spread,
   edge-decay, and severe-liquidity scenarios.
8. Compare candidate and incumbent P&L with a paired event-cluster bootstrap.
9. Keep one active research epoch and grade it only on decisions created after
   that epoch began.
10. Rotate the report-only research candidate only after the current epoch has
    at least 30 forward trades across five clusters, has failed its forward
    gate, and a new candidate passes the retrospective gate.

Repeated hourly runs with unchanged evidence do not create fake generations.
The active epoch start is preserved, so a new run cannot erase unfavorable
forward evidence by silently resetting its clock.

## Forward gate

An active research genome needs all of the following before the lab reports
`READY_FOR_EXPLICIT_SHADOW_REVIEW`:

- 100 genuinely later trades;
- 10 event clusters;
- positive lower-95% mean P&L after fees and one-cent slippage;
- positive lower-95% paired event-cluster P&L advantage over the incumbent.

That status is only a proposal for explicit review of a bounded shadow
experiment. It is not canary evidence and never changes execution.

## Stress chamber

The report includes four deterministic scenarios:

- `baseline`: one cent of slippage and current fees;
- `wide_spread`: five cents of slippage;
- `edge_decay`: only half the estimated edge survives, uncertainty rises 25%,
  and slippage rises to three cents;
- `severe_liquidity`: ten cents of slippage, 1.5x fees, only 75% edge
  retention, and 1.5x uncertainty.

Synthetic stress remains simulation evidence. It never counts as a witnessed
fill or settled-trade result.

## Trace replay

Every run also hashes the canonical witnessed shadow-order record and reports
missing queue snapshots, unresolved orders, fills, settlements, losses, and
any settlement-without-fill anomaly. Execution optimization fails closed when
the trace is incomplete.

## Authority boundary

The evolution report always declares:

- `code_mutation_authority=false`;
- `deployment_authority=false`;
- `weight_write_authority=false`;
- `risk_write_authority=false`;
- `execution_authority=false`;
- `capital_authority=false`.

It automatically rotates only a JSON-described research candidate. Production
promotion always requires an explicit reviewed change and later verified
settled-fill evidence.

Each run also rebuilds a deterministic improvement queue from current crypto
fill skill, execution P&L, trace completeness, forecast diversity, forward
genome evidence, and compounding stress. The queue can direct only read-only
replay, bounded mutation, stress simulation, research rotation, and reporting.
Its forbidden actions include production rewrites, weight/risk writes, order
submission, and capital allocation.

## Operation

The existing hourly trainer runs the lab automatically:

```powershell
python scripts/run_dummy_simulation_training.py --summary
Get-ScheduledTask -TaskName DummySimulationTrainer
```

Full timestamped reports and the atomic latest pointer are under
`artifacts/dummy/simulation_training/`. The compact dashboard state is written
to `runtime/autonomy/simulation_training_latest.json`.
