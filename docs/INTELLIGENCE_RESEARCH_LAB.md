# Dummy Intelligence Research Lab

## Mission

The Intelligence Research Lab is the protected layer above Dummy's forecasting
autoresearch. Its subject is not a market, sport, coding task, or security task.
Those are experimental domains. Its subject is the evidence-backed discovery of
better ways to discover, reason, create, research, plan, evaluate, and solve.

It optimizes methods of thinking—not confident-looking answers. The operating
loop is:

```text
observe -> represent -> understand -> research -> imagine -> generate
        -> challenge -> evaluate -> decide -> learn -> improve -> repeat
```

The first registered adapter is `dummy.forecasting`. It converts the real
multi-cohort autoresearch, forward-paper, and ignition artifacts into scientific
observations. Future domains must implement the same evidence contract; they do
not get to weaken it.

## Constitutional boundary

The lab may propose and simulate changes to cognitive methods:

- reasoning and problem-decomposition strategies;
- research and search methods;
- computational creativity operators;
- planning and evaluation methods;
- scientific-memory and context policies; and
- cognitive-role organization.

It can never mutate authority, permissions, truth, settlement, fill evidence,
private evaluators, promotion law, credentials, the execution firewall, or
capital controls. The entire `dummy/intelligence_lab` package is included in the
protected-surface manifest. Automatic negative actions may reject, quarantine,
contract, or demote a candidate. Positive promotion remains human-only.

## Seven connected pillars

1. **Discovery** turns explicit bottlenecks, contradictions, failures, and
   missing evidence into ranked research opportunities.
2. **Research** converts each opportunity into a question, hypothesis,
   prediction, falsifier, preregistered protocol, and fixed budget.
3. **Computational creativity** uses named operators—analogy, inversion,
   morphological search, cross-domain transfer, constraint relaxation and
   inversion, recombination, counterfactual reasoning, first-principles
   reconstruction, and abstraction. Every output must be testable.
4. **Multi-strategy problem solving** competes bounded strategies against the
   frozen champion instead of trusting one chain of thought.
5. **Scientific method** requires protected private evidence, external
   generalization, deterministic replay, independent replication, cost
   normalization, and reward-hacking review.
6. **Recursive cognitive improvement** evolves cognitive genomes while its
   constitution and evaluator remain fixed outside the mutation surface.
7. **Theory building** stores reusable conditional claims only after replication;
   a successful prompt or isolated benchmark result is never called a law.

## Scientific world model and memory

The lab maintains connected knowledge, problem, hypothesis, theory, failure,
capability, unknown, opportunity, and research graphs. Every node is linked to
a content-addressed record. The append-only `scientific_memory.jsonl` ledger is
SHA-256 hash chained and verifies record identity, sequence, ancestry, and
tamper evidence on every append.

The observatory explicitly describes only ingested evidence. It does **not**
claim to contain everything humanity knows. Unknowns remain first-class graph
nodes rather than being filled with model guesses.

The cognitive genome inherits:

- reasoning strategies;
- research methods;
- creative operators;
- evaluation methods;
- scientific-memory policies; and
- cognitive-role organization.

It contains no authority, truth, execution, or promotion genes.

## Thinking roles

The generation-zero organization declares bounded roles for problem analysis,
research science, invention, systems thinking, statistics, mathematics,
optimization, skepticism, devil's advocacy, simplification, architecture,
simulation design, experimentation, theory building, knowledge curation, and
metacognition. Roles are cognitive functions, not sovereign agents. They share
artifacts through typed records and receive only the context required for their
task.

## Scientific and theory gates

Every generated hypothesis includes a measurable prediction and a condition
that would falsify it. Its experiment compares a preregistered intervention to
the frozen current champion using identical point-in-time evidence, fixed
compute, visible development, private selection, external generalization, and
forward validation.

A replication is valid only when its effect lower bound is positive, calibration
is noninferior, replay is deterministic, fixed-cost performance is noninferior,
and the reward-hacking audit is clean.

- A **provisional theory** requires at least three independent valid
  replications across two experimental domains.
- A **general law** requires at least six independent valid replications across
  three experimental domains.

These thresholds are floors, not automatic deployment rules. Human promotion
review still applies to any downstream system that wants to use a validated
method.

## Recursive levels

The observatory reports the highest experimentally supported level and keeps a
separate evidence gate for each:

0. bounded problem solving exists;
1. problem solving improves under replicated, equal-cost evidence;
2. research methods improve under a matched budget;
3. creativity methods improve on held-out tasks;
4. reasoning improvement transfers across domains;
5. an evolved improver beats the frozen improver;
6. improved discovery yields independently replicated value; and
7. intelligence evolution accelerates under a fixed physical budget.

The current checked-in evidence supports Level 0 only. The lab has generated a
real research queue from forecasting evidence, but it has completed zero lab
experiments and validated zero cognitive theories. That is an operational
starting point, not a self-improvement claim.

## Dynamic operation

`scripts/run_dummy_autoresearch.py` runs forecasting autoresearch first, then
feeds its exact-cohort, forward-paper, and ignition receipts into the lab. The
cycle writes:

- `runtime/autonomy/autoresearch/intelligence_lab/observatory_report.json`;
- `runtime/autonomy/autoresearch/intelligence_lab/scientific_memory.jsonl`;
- `runtime/autonomy/autoresearch/intelligence_lab/research_queue.json`; and
- a compact checked-in `docs/INTELLIGENCE_RESEARCH_LAB_EVIDENCE.json` through
  `scripts/run_vnext_autoresearch_audit.py`.

This sequencing preserves the evidence hierarchy: reality and settlement
produce observations; observations produce research questions; research can
eventually produce a cognitive method. A generated idea never flows backward
and rewrites the truth used to judge it.

## Reproducibility

```powershell
python scripts/run_dummy_autoresearch.py
python scripts/run_vnext_autoresearch_audit.py
python -m pytest -q tests/test_intelligence_research_lab.py
```

The implementation lives in `dummy/intelligence_lab/`. Its contracts are
domain-agnostic; `forecast_domain.py` is the first adapter rather than a hidden
forecasting dependency in the scientific core.
