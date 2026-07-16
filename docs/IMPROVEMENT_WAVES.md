# Autonomous-improvement waves (program summary)

Branch-first, fail-closed feature program on top of the autonomy layer. Every
wave: branch-only, shared venv, suite + coverage(≥85) + ruff green, an
integration branch after all features land. **`wave4-integration` is the
cumulative head** — a clean fast-forward over `main` (30 commits, 93 files).

## Verifying the suite (read this before trusting a run)

~244 "workstation-only" governance tests SKIP only when `artifacts/dummy`
(gitignored) is absent AND sibling `C:/src/engine/obtuse/blunder` is absent
(`tests/conftest.py` `_WORKSTATION_EVIDENCE`). A fresh worktree skips them; but
running the suite *creates* `artifacts/dummy`, so a second run in the same
worktree shows ~300 "failures". Separately, 13 canonical-path tests
(`test_dummy_canonical_identity_v*`, `canonical_rename`, `path_integrity`,
`proof_ledger`) always fail off the canonical root. **Clean signal = decompose:
failures ∖ `tests/workstation_only_tests.txt` must equal exactly those 13.** CI
mirrors the checkout to `C:\src\engine\dummy` and passes them; a local clean
coverage run deselects the 13 with `artifacts/dummy` absent.

## Waves

**Wave 1** — autonomous 2-stage promotion engine (≥300-cluster/7-day, Brier-CI>0,
beat≥55%, fee-adjusted P&L CI>0, CLV+, auto-demote, max-2/day, health-gated),
adverse-selection diagnosis, staleness gates + watchdogs, prune/SQLite guards,
FanGraphs projection.

**Wave 2** — execution-policy tournament (C0–C4 counterfactual cohorts,
`auto_switch=false`), sports CLV pre-game close anchor (drops MLB promotion bar
to 300 clusters), ESPN fantasy intake (`espn_flb_scratch`, `espn_fantasy_crowd`),
Polymarket cross-venue (`cross_venue_polymarket_crypto`/`_econ`, econ dormant).

**Wave 3** — event-driven live-game poller (`autonomy/live_poller.py`, off by
default behind `DUMMY_LIVE_POLLER`); empirical sports reliability curves
(`reliability.py`, winner+total × 6 leagues × pre/live, challenger-only);
player-prop plumbing (`player_props.py`, fixtures-first, governance-gated, no
key-bypass); intelligence-lab campaigns over the Wave-1/2 evidence
(`autoresearch/wave_streams.py`, point-in-time, honest family-size disclosure).

**Wave 4** — intelligence-lab campaign **sweep at scale**
(`autoresearch/campaign_sweep.py`): multi-cohort, visible-partition-only scoring,
Benjamini-Hochberg FDR control across the pooled (cohort×candidate) tests, honest
family-size + naive-vs-FDR-survivor disclosure. Plus: the Part-I pre-promotion
punch list was verified **already resolved** by PRs #76/#77 (NHL pulled-goalie
live winner, WS-6 post-shift evidence, WS-7 NFL bye repair, active mismatch
finder, NBA engine-specific uncertainty) — live sports-challenger promotion is no
longer blocked by those defects.

## Discipline held program-wide

Every new signal/source is challenger-only and fail-closed; none touches the
allocator/executor/risk; the poller is off by default; prop-lines stay behind an
unopened governance slot; the campaigns are research-only. Promotion to execution
authority remains a human-gated decision (`promotions.json`), unchanged by these
waves.

## Remaining (human-gated)

1. **Open the combined PR** `wave4-integration → main` — blocked on `gh` re-auth
   (`gh auth login`); the merge is a clean fast-forward.
2. **Run the promotion ladder / readiness report** against the live ledger now
   that sports challengers are hardened — an operator decision (touches capital
   authority), run from the canonical repo.
