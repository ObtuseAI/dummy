# DUMMY vNext nested forecast autoresearch

## Status

The nested research architecture is **implemented, mechanically validated, and
running at ignition Level 0: autonomous experimentation**. The latest bounded
real-ledger campaign compiled 282 causally eligible BTC 15-minute settled
markets, ran five equal-budget private candidate trials, and rejected all five.
No candidate reached external evaluation or forward-paper eligibility. Dummy
therefore claims no net-positive self-improvement, improved improver, or
acceleration of improvement.

Every campaign and forward registry is bound to one exact prediction cohort:
`vertical | subject | market type | horizon/phase`. Evidence cannot transfer
between BTC and ETH, between leagues, between MLB winner and YRFI/NRFI, or
between pregame and live heads. Gate evaluation, evidence accrual, challenger
search, and safe demotion are autonomous per cohort. Promotion activation
remains the separate, constitutionally human-only decision.

## First real-ledger campaign

The compiler opens `runtime/autonomy/ledger.db` in SQLite read-only and
query-only mode. It selects the earliest pre-settlement decision for each
settled market, preserves exact witnessed fill truth only for the exact
recorded decision, and never invents fill or avoided-fill P&L for a
counterfactual candidate. A settlement receipt is used only as a conservative
upper bound for market close when an exact close timestamp is unavailable.

The frozen partition plan uses whole UTC dates and purges any event cluster
that would cross partitions:

- visible development: 179 markets from 2026-07-10 through 2026-07-13;
- private selection: 80 markets from 2026-07-14; and
- external generalization: 23 markets from 2026-07-15.

The five lineages were market-prior anchored, calibration first, abstention
first, crypto liquidity, and execution aware. Every trial received the same
starting genome, evaluator, and per-experiment compute ceiling. The private
evaluator rejected every mutation. Common failures were non-positive clustered
confidence bounds, non-positive multi-objective fitness, compute-normalized
quality regression, missing genuinely contested evidence, or abstention-gaming
guards. Item-level private feedback was never returned to the outer researcher.

The MLB simulation lineage was not run. The authoritative decision ledger does
not yet preserve the point-in-time plate-appearance simulator component output
across all three partitions, so reconstructing it from outcomes would violate
the causal boundary.

## Two systems, one hard boundary

`dummy.autoresearch` separates the object being improved from its improver:

```text
Outer evolution researcher (RECOMMEND maximum)
    -> proposes typed, unapplied genome or research-policy mutations
Inner forecast research organism (SIMULATE maximum)
    -> produces shadow forecasts for protected evaluation
External evaluators
    -> own hidden tasks, settlement truth, cost normalization, and gates
```

The outer researcher may change proposal-only research designs for agent
composition, feature and source selection, context construction, challenger
search, simulation allocation, uncertainty, calibration, abstention,
adversarial sequence, and mutation-selection policy. It cannot access
credentials; submit orders; change risk or capital; release quarantines;
rewrite settlement, fill, replay, or evaluator truth; apply source edits;
change a running organism; or promote itself. `dummy/autoresearch` is itself a
protected constitutional surface.

## Three sealed evidence partitions

Every task suite contains three group-disjoint partitions:

1. **Visible development** may return item-level replay and debugging feedback.
2. **Private selection** returns only aggregate fitness, accept/reject, failed
   gate identifiers, a metric digest, and coarse evidence-count buckets.
3. **External generalization** is never selection eligible. It is reserved for
   transfer and claim testing on future seasons, unseen cohorts, distinct
   regimes, alternative market types, or later forward-paper evidence.

Event clusters, selection keys (dates, strike families, teams, symbols), and
evidence IDs may not cross partitions. The outer researcher never receives
private case IDs, timestamps, probabilities, outcomes, teams, symbols, strikes,
item failures, or canary locations.

## Multi-objective private fitness

The protected evaluator combines contested Brier gain, log-loss gain,
calibration, useful sharpness, witnessed-fill performance, cross-regime
transfer, abstention quality, and information per cost. It subtracts drawdown,
complexity, source correlation, reward-hacking, and replay-instability costs.

The following are hard, non-tradeable gates:

- verified point-in-time settlement;
- no forced-coverage contamination;
- no reward-hacking canary trigger;
- private calibration no worse beyond tolerance;
- compute-normalized quality no worse than the incumbent;
- witnessed execution truth for fill claims;
- deterministic replay;
- complexity budget and zero dead code;
- abstention rate no greater than 50%;
- genuine contested evidence; and
- a positive event-cluster bootstrap interval and positive total fitness.

## Lineage search and context economy

Independent lineages are multi-armed-bandit arms. Allocation uses aggregate
private reward, uncertainty, novelty, stagnation, transfer potential, and
resource efficiency. Within the chosen lineage, parent selection is greedy.
An arm that fails to improve across its configured window produces an
**unapplied** proposal to fork the global champion into a distinct lineage with
a different strategy.

Forecaster, adversary, calibrator, and evolution-debugger contexts use separate
field allowlists and fixed character budgets. Current champion definitions are
preserved, while histories are reduced to recent relevant records, hashes, and
one-line outcomes. The policy targets 16x compression, but the measured ratio
is recorded per context and is not assumed.

## Reward-hacking and complexity pressure

The hidden evaluator implements eight canary families:

- leaked timestamp;
- duplicated source family;
- misleading midpoint fill;
- synthetic data presented as promotion evidence;
- market-prior agreement presented as contested edge;
- correlated clusters presented as independent;
- malformed book consumption; and
- future lineup consumption.

Any trigger rejects the candidate and records a case-redacted adversarial
lesson. Complexity is a first-class Pareto dimension beside forecast fitness
and resource cost. A candidate that survives selection must undergo semantic
distillation; the simplified candidate is retained only after an independent
private re-evaluation preserves every hard gate and the fitness gain within
tolerance while actually lowering complexity.

## Ignition levels

The ignition harness reports only the highest supported level:

- Level 0: autonomous experimentation;
- Level 1: net-positive self-improvement under fixed cost;
- Level 2: an evolved outer researcher beats the manual outer researcher;
- Level 3: improvement rate accelerates across generations under a fixed
  physical budget.

Level 2 requires at least three matched wins with identical mutation budget,
model access, evaluator, target systems, wall/compute budget, starting genomes,
and starting score. The evolved arm must achieve a better private score with no
more experiments, no worse external transfer, no more reward hacking, and no
more complexity. Level 3 additionally requires rising per-generation gains.
The checked-in campaign supports Level 0 only. Level 1 remains unsupported
because no challenger survived private selection and forward confirmation.
The matched Level 2 test is blocked until Level 1 and forward confirmation are
both established.

## Forward-paper operation

When a challenger eventually survives private and external gates, Dummy freezes
its genome and records predictions for newly observed, still-unsettled markets
in a separate hash-chained ledger. Issuance must precede settlement and grading
must reproduce the original deterministic forecast. Readiness for a human
promotion review requires at least 100 settled observations, 10 event clusters,
five verified settled fills, a passing external evaluation, and no late-issue
or replay-integrity failure. The forward system has no order, broker, execution,
promotion, or capital authority.

The optional Windows task installer schedules this local paper research loop;
it does not enable live execution:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_autoresearch_task.ps1
```

## Reproducibility

```powershell
python scripts/run_dummy_autoresearch.py
python scripts/run_vnext_autoresearch_audit.py
python -m pytest -q tests/test_vnext_autoresearch.py tests/test_vnext_autoresearch_ledger_pipeline.py tests/test_vnext_autoresearch_audit.py
```

The audit emits:

- `docs/VNEXT_AUTORESEARCH_POLICY.json`;
- `docs/VNEXT_AUTORESEARCH_EVIDENCE.json`;
- `docs/VNEXT_AUTORESEARCH_CAMPAIGN.json`;
- `docs/VNEXT_AUTORESEARCH_FORWARD_EVIDENCE.json`; and
- `docs/VNEXT_AUTORESEARCH_IGNITION.json`.

Experiment records use a duplicate-resistant, append-only JSONL ledger with a
SHA-256 hash chain. The candidate lifecycle remains proposal-only until genuine
private survival, external generalization, forward-paper confirmation, and
explicit human promotion review are all complete.
