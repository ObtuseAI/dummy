# Ascendancy deltas (Wave-7)

Five disciplines adopted from the operator's "Dummy Ascendancy Protocol"
(2026-07-17) — the subset that was genuinely new to this codebase. Everything
else in that protocol (point-in-time discipline, market-implied baselines,
calibration, abstention, champion/challenger, decay/retirement, no-edge
honesty) was already load-bearing here.

| Delta | Module | What it guards |
|---|---|---|
| Negative-control battery | `autonomy/negative_controls.py` + `scripts/run_negative_controls.py` | A source whose "edge" survives a scrambled world (shuffled labels, random forecaster, placebo prior, miscalibrated benchmark) is contaminated, not skilled. The benchmark-calibration control is the standing tripwire for the 2026-07 fabricated-mid bug class. |
| Preregistration | `dummy/autoresearch/preregistration.py` | Hypothesis + mechanism + falsification condition committed (content-addressed, append-only) BEFORE results are observed. Enforcement is opt-in per campaign (prospective-only). |
| Sealed holdout | `dummy/autoresearch/sealed_holdout.py` | One-shot final evaluation with a query-budget ledger (`holdout_usage.jsonl`). A crashed evaluation still consumes the budget; a repaired candidate is a NEW candidate id. |
| NO_EDGE_MAP | `autonomy/no_edge_map.py` | First-class artifact classifying every graded scope: edge / no demonstrated edge / significantly negative / insufficient evidence. Stops re-litigating dead ideas. |
| Conservative advantage | `autonomy/conservative_advantage.py` | The decision-grade number: raw edge − cost − CI half-width × selection inflation (Sidak, family size) × correlation inflation (√group). |

Run the battery + map against the live ledger:

    python scripts/run_negative_controls.py

Evidence-only: nothing here gates or trades by itself; flags emit
`NEGATIVE_CONTROL_FLAG` alerts and feed operator review.
