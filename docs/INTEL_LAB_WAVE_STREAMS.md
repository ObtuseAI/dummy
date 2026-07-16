# Intelligence-Lab campaigns over Wave-1/2 evidence

`dummy/autoresearch/wave_streams.py` points the Loop-1 autoresearch machinery at
the four settled evidence streams Wave-1/2 instrumented, without weakening any of
its discipline.

## The four streams → canonical evidence

Each stream has an adapter that maps its records into the content-addressed
`LedgerEvidenceRow` (so every downstream invariant applies unchanged):

| stream | adapter | source family | incumbent vs prior |
|---|---|---|---|
| Sports CLV | `clv_evidence_row` | `sports_clv` | our forecast vs pre-game close |
| Execution tournament | `tournament_cohort_evidence_row` | `execution_tournament::C0…C4` | cohort prob vs market prior |
| ESPN fantasy | `fantasy_evidence_row` | `espn_fantasy_crowd` | crowd prob vs market prior |
| Cross-venue Polymarket | `cross_venue_evidence_row` | `cross_venue_polymarket_{crypto,econ}` | Kalshi vs Polymarket (component) |

Each cohort/venue is a **distinct source family**, so a mined edge is
attributable and never silently pools with an unrelated source.

## Point-in-time discipline (no lookahead)

- `LedgerEvidenceRow` rejects any row whose `decision_at` is not strictly before
  `settlement_received_at`.
- `build_stream_partition_plan` delegates to the canonical builder: one cohort
  per plan, each event cluster frozen to its **earliest** decision date, later
  observations dropped (`excluded_late_cluster_observation_ids`), and the
  chronological visible/private/external split fixed before any mining.
- `run_stream_campaign` mines **only** on the `VISIBLE_DEVELOPMENT` partition.
  Private/external evidence is never read while proposing candidates.

## Honest family-size disclosure

The standing lesson: reporting a survivor while hiding the family it was selected
from is dishonest. `disclose_mined_family` reports:

- `family_size_searched` — every candidate searched, not just the survivors,
- `complexity_passed` / `kept`,
- `expected_false_positives_under_null = family_size × alpha`, and
- a warning that marks survivors **UNPROVEN** when `kept ≤ expected_false_positives`
  (indistinguishable from multiple-comparisons noise), or demands out-of-sample
  confirmation otherwise.

Every candidate is gated by the existing complexity budget before it can be
kept. Nothing here reaches execution (`reaches_execution: false`).
