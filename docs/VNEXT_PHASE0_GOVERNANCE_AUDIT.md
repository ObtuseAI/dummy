# DUMMY vNext Phase 0 governance audit

Status: **PASS_WITH_NOTES** for the constitutional foundation; **NOT READY**
for canary or scale.

This report freezes the governance boundary used by every vNext slice. It does
not reinterpret historical performance, grant execution authority, promote a
challenger, or change capital.

## Authority and protected truth

The machine authority lattice is monotonic. Research stops at `SIMULATE`;
automatic mutation proposals stop at `RECOMMEND`. `PAPER_ALLOCATE`,
`LIVE_PROPOSE`, and `EXECUTE` are not reachable through the research package.
Promotion is a reviewed human action. Automatic demotion and quarantine may
only reduce authority.

The canonical protected-surface artifact is
`docs/VNEXT_PROTECTED_SURFACES.json`. Its canonical payload digest is
`b75897f315bc44731ef72b4e9e39e758f8dfbb6b9e1552df5b0101775786adf9`.
The fail-closed mutation guard rejects protected paths, traversal, unknown
roots, and mutation proposers above `RECOMMEND`.

Phase 6 extends this same boundary to vNext causal memory, clustered truth and
multiple-testing logic, genome identity and lineage, the external evolution
evaluator and archive, and promotion, retirement, and rollback rules. These
are evaluator protections, not new evolvable capabilities or authority.

Phase 7 further protects adversarial arena definitions and their judge,
homeostasis thresholds and intervention authority, and observatory evidence
projections. Candidates cannot rewrite stress tests, manufacture healthy state,
or alter what the read-only observatory reports.

## Governance contradiction resolved

`autonomy/ontology.py` previously described the risk stages as a system that
“graduates itself.” That wording contradicted the human-only implementation in
`autonomy/promotion.py`. The stage is now documented as a risk ladder whose
advancement requires explicit human promotion. No promotion mechanics changed.

## Dummy identity and legacy isolation

Dummy is its own entity. vNext contains no legacy identity, namespace, or
authority inheritance. The live firewall previously loaded a secret scanner
directly from `core/inherited_blunder`; it now uses the independent,
Dummy-owned `live_firewall/secret_sentinel.py` with regression coverage.

A source search after that change finds no production runtime import of the
legacy subtree outside the subtree itself. Remaining references are limited to
historical validation/report scripts, separation tests, archived reports, and
the hash-pinned copy. The copy remains immutable in this slice because current
repository validation explicitly verifies its manifest. Retirement requires a
separate mechanical migration of those validators and historical-report
contracts; it is not an input to vNext and cannot be imported by `dummy/`.

## Frozen benchmark cohorts

### Primary: BTC 15-minute direction

- Universe: native `KXBTC15M` contracts only; ETH, SOL, hourly, daily, ladder,
  and synthetic contracts are excluded.
- Grain: one event/market decision at the last causally valid forecast before
  close; duplicate contracts for the same event are one event cluster.
- Evidence: provider/exchange event time, verified local receipt, frozen
  decision time, scheduled close, and verified settlement are mandatory.
- Comparison: vNext organism, unchanged incumbent, and market prior on the same
  covered decisions. Forced-coverage and retrospectively hydrated rows are
  reported separately and cannot influence promotion.
- Metrics: Brier, log loss, calibration error, abstention/coverage, market-prior
  advantage with event-cluster uncertainty, paper execution realism, and cost.
- Lane: forward shadow only for promotion evidence.

### Transfer: MLB pregame winner

- Universe: `KXMLBGAME` winner contracts with regime `pre`; spreads, totals,
  first-inning, and live forecasts are excluded.
- Grain: one game cluster; multiple team-side contracts cannot count as
  independent events.
- Evidence: verified schedule/game identity, team mapping, lineup/injury state
  when available, local receipt, frozen decision, market close, and settlement.
  Missing or contradictory required state produces abstention.
- Comparison and metrics: the same incumbent/market-prior/organism comparison
  and event-cluster scoring used for BTC, plus lineup-state coverage and source
  latency. No cross-league pooling is allowed.
- Lane: forward shadow only for promotion evidence.

## Baseline blockers preserved verbatim

The read-only canary probe ran from `2026-07-14T21:02:15.333822Z` through
`2026-07-14T21:04:23.042181Z` and returned `ready=false`:

- verified shadow PnL is not positive: **-380 cents**;
- fill-conditioned Brier is **0.242447** versus market **0.208959**;
- fill-conditioned Brier skill versus market is **-0.1603**;
- scale is also blocked by detected negative forecast drift;
- data quality is `WARN` because 382,813 historical signals predate current
  receipt-time/feature provenance.

These are floors, not targets to explain away. vNext begins with zero execution
authority and remains a challenger until forward evidence clears the reviewed
gates.
