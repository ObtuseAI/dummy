# DUMMY vNext nested forecast autoresearch

## Status

The nested research architecture is **implemented and mechanically validated;
all empirical recursive-improvement gates remain open**. No genuine private
candidate trials, external generalization trials, or forward-paper candidate
settlements are checked in. Dummy therefore claims no autonomous forecasting
improvement, no improved improver, and no acceleration of improvement.

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
The checked-in empty evidence report supports no ignition level.

## Reproducibility

```powershell
python scripts/run_vnext_autoresearch_audit.py
python -m pytest -q tests/test_vnext_autoresearch.py tests/test_vnext_autoresearch_audit.py
```

The audit emits:

- `docs/VNEXT_AUTORESEARCH_POLICY.json`; and
- `docs/VNEXT_AUTORESEARCH_EVIDENCE.json`.

Experiment records use a duplicate-resistant, append-only JSONL ledger with a
SHA-256 hash chain. The candidate lifecycle remains proposal-only until genuine
private survival, periodic external generalization, forward-paper confirmation,
and explicit human promotion review are all complete.
