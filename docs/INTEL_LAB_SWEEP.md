# Intelligence-Lab campaign sweep at scale (Wave-4)

`dummy/autoresearch/campaign_sweep.py` runs the Wave-3 campaign across **many
cohorts at once** and controls the multiple-comparisons risk that scale creates.

## Why scale needs FDR control

Wave-3 runs one campaign over one cohort. Searching every
`stream × subject × market_type × phase` the ledger carries means hundreds of
(cohort × candidate) tests — at `q=0.05`, dozens of "edges" survive by chance
alone. Reporting the naive survivor count at scale is the multiple-comparisons
trap the Intelligence-Lab is built to avoid.

## What the sweep does

1. **Group** a stream's records into cohorts by `cohort_scope` (the same key the
   partition plan enforces).
2. **Skip and disclose** cohorts too small to partition (≥3 decision dates
   required) or with too few visible rows — every skip carries a reason; nothing
   is dropped silently.
3. **Score** each complexity-passing candidate on the cohort's
   `VISIBLE_DEVELOPMENT` partition only (no lookahead), with a paired-Brier
   statistic vs the market prior → a one-sided p-value per (cohort, candidate).
4. **FDR-control** the pooled p-values with Benjamini-Hochberg at level `q`, so
   the disclosure reports the **family size searched**, the **naive** significant
   count, and the **FDR-survivor** count.

The paired-Brier gain is `(prior − y)² − (candidate − y)²` per row; positive
means the candidate beat the market prior. Rows are independent event-cluster
snapshots (the partition plan purges cross-partition clusters), so paired-by-row
is a defensible cluster-independent test.

`SweepResult.to_dict()` is the reviewable artifact. `reaches_execution` is always
`false` — this is research evidence, never an execution path.
