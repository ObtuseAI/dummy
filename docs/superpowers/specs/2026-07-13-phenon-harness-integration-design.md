# Phenon Harness Integration — Design

**Date:** 2026-07-13
**Status:** Approved (brainstorming), pending implementation plan
**Author:** Opus (with operator Chris)
**Precedes:** implementation plan `docs/superpowers/plans/2026-07-13-phenon-harness-*.md`

## Goal

Fold the *sound* parts of the "Phenon Autopoietic Harness" concept into dummy
after Part I of the council build-out completed. Most of Phenon already exists
under different names; this adds the two genuinely-missing pieces and documents
the third. All work is challenger-only, fail-closed, and propose-then-human-
promote. **Perpetuals and scraping are rejected. No autonomous self-rewrite of
execution logic — the one place Phenon's "self-evolution" appears (an LLM
narration layer) is declawed to human-read commentary that never auto-acts.**

## Concept → component mapping (Phenon vocabulary → dummy)

| Phenon layer | Dummy reality | This design |
|---|---|---|
| L1 "Ontological Market Manifold" (per-market reality state) | `SpecialistRegistry` routes each market to one specialist by vertical/league; crypto vs sports already run different governing logic | **Component C**: document it (docs only) |
| L2 "Athletic Quant" (ensemble of external power ratings colliding vs Kalshi) | Not built — net-new alpha | **Component A**: external-power-ratings ensemble challenger + divergence flag |
| L3 "Evolution Engine" (deconstruct losses → propose → integrate) | Miner *discovers* winning edges (WS-1c); tuner *proposes* params (WS-9); promotion registry *integrates* (WS-14) — but nothing deconstructs LOSSES | **Component B**: deterministic loss-attribution + LLM narration, feeding the tuner/readiness loop |

## Global constraints (inherited from Parts I/II — bind every task)

- **Challenger-only.** Every new signal sets `features["challenger_only"]=True`;
  `forecaster.fuse()` excludes challengers from execution until a human
  promotion via `PromotionRegistry`. Nothing here reaches the live
  allocator/executor unpromoted.
- **Fail-closed.** Missing feed / thin data / offseason → abstain (`None`),
  byte-identical to the feature being disabled. Doctrine test:
  feature-present-but-empty == feature-disabled.
- **Point-in-time honesty.** Models/analysis learn only from settled
  (`status == "post"`) rows; live/current data never enters learning.
- **Per-event-CLUSTER means, never per-row CIs** (correlated emissions);
  disclose mined family size (multiple-comparisons honesty).
- **Propose-then-human-promote.** Deconstruct → propose params → **human**
  promotes; auto-demotion is the only automatic transition. No component
  mutates constants, promotions, or execution logic.
- **No perps. No scraping.** External data only via first-party keyless or
  license-vetted public-domain feeds.

---

## Component A — External Power Ratings Ensemble

**Files:** Create `autonomy/sports/power_ratings.py` (pure fetch + consensus,
no signal emission); modify the sports signal hook in
`autonomy/signals/sports_intelligence.py` (two emissions); Test
`tests/test_autonomy_power_ratings.py`.

### A.1 Source adapters (pluggable, each fail-closed independently)

Each adapter maps a team name → a numeric rating for a league, or `None` when
the feed is down/missing/offseason.

- `EspnFpiSource` — football (nfl, ncaaf). Confirmed keyless endpoint:
  `https://site.web.api.espn.com/apis/fitt/v3/sports/football/{nfl|college-football}/powerindex?limit=1000`.
  Payload: `teams[].team.abbreviation` + `teams[].categories[]` values; top-
  level `glossary`/`categories` name each metric (FPI, projected wins, etc.).
  The exact FPI value field is captured as a committed trimmed fixture at build
  (data-probe appendix below).
- `EspnBpiSource` — basketball (nba, ncaamb). Same shape at
  `.../basketball/{nba|mens-college-basketball}/powerindex`.
- `EloSource` — wraps the existing `autonomy/sports/elo.py::EloModel.rating(team)`
  as a rating source (already point-in-time, already warm every cycle).
- **Slot** for additional vetted keyless/public-domain sources (e.g. a public-
  domain Massey ratings CSV *if its license permits* — verified before adding;
  never scraped). Documented, not built in the first pass.

Rating provenance and per-source availability are logged in features so the
miner/loss-engine can grade which sources actually pay.

### A.2 Consensus core (pure, unit-testable)

`consensus_margin(home, away, league, sources) -> ConsensusMargin | None`:

- Each available source: `rating_diff = rating(home) - rating(away)`; convert to
  an implied expected margin via a per-league `POINTS_PER_RATING_UNIT[league]`
  scale (FPI/BPI are already in points-favored terms per game for many ESPN
  metrics — the scale is a calibration constant, a propose-then-promote tuner
  candidate, not independently fit).
- `ensemble_margin = median(available implied margins)`; `dispersion =` spread
  of the implied margins (e.g. max−min or IQR).
- Missing sources drop out; **zero available → `None` (abstain)**.
- Returns `{ensemble_margin, dispersion, n_sources, per_source}`.

### A.3 Emission 1 — standalone challenger (sports hook)

`ensemble_margin` → winner + full spread ladder from ONE distribution via the
existing machinery: `nfl_margin.margin_distribution` (football) / normal-margin
(basketball). `challenger_only=True`; `margin_model_version =
"power_ratings_consensus_v1"`; graded per `(specialist, market_type)` on
contested Brier through the existing CLV/backtest path. **High dispersion
(sources disagree) → widen uncertainty only** (soft), never a silent suppress.
Pre-game only where the hosting engine is pre-game-only; if emitted for a live
market, gate consistently with the WS-6/7 pre-game gate to avoid double-count.

### A.4 Emission 2 — opportunistic divergence flag

When `|ensemble_margin − our_engine_margin|` (or the consensus-implied
probability vs the Kalshi mid) exceeds a per-league threshold **AND** dispersion
is low (sources agree with each other), log a bounded `power_divergence` feature
into the existing opportunist/mispricing layer. Sparse, high-conviction;
challenger-only evidence like everything else. High dispersion suppresses the
flag (we do not act on a disagreement the sources themselves don't share).

### A.5 Fail-closed & point-in-time

Any source down → dropped from consensus; all down → abstain, byte-identical to
feature-off. `SeasonMonitor` already gates offseason. Ratings are read at
emission and **never** fed into any model's `update()`.

### A.6 Tests (hand-computed, zero network)

- Consensus math: fixed source ratings → expected implied margin → expected
  winner/spread-ladder probabilities (hand-computed).
- Fail-closed: one source down → dropped; all down → `None` and a signal
  byte-identical to feature-disabled.
- Dispersion widens uncertainty, does not shift the mean.
- Divergence flag fires only on (large gap AND low dispersion); high dispersion
  suppresses it.
- `challenger_only=True` on every emission; version stamp present.
- Real FPI/BPI probe captured as committed trimmed fixtures.

---

## Component B — Evolution Engine (loss-deconstruction)

**Files:** Create `autonomy/loss_engine.py` + `scripts/run_dummy_loss_engine.py`
(nightly, chained in the existing miner/tuner/grader schtask); modify the tuner
to read the loss-priority list and the dashboard/readiness to surface it; Test
`tests/test_autonomy_loss_engine.py`.

### B.1 Deterministic attribution (reuses miner plumbing)

Reuse `autonomy/strategy_miner.py`: `load_settled_rows`, `_brier_edge`,
`_purged_split`, cluster-mean aggregation, and `autonomy/stats.py::mean_ci95`.
No new statistics engine.

For each grading scope `(specialist, market_type, phase)` whose **cluster-mean
contested-Brier edge is negative** (we trail the market):

- Decompose the shortfall into buckets: feature-regime terciles (which logged
  feature values coincide with the worst losses), market_type, pre-vs-live,
  horizon.
- Per scope, surface the buckets with the largest negative edge, **cluster-
  level with `mean_ci95`**, and disclose the family size (number of
  scopes × buckets evaluated) so a reader can judge multiple comparisons.
- Respect `MIN_CLUSTERS`; a scope/bucket below it → `insufficient_data`, never a
  confident claim.

### B.2 Artifact

`runtime/autonomy/loss_attribution.json`: per scope
`{scope, n_clusters, cluster_edge, worst_buckets:[{bucket, edge, ci95, n}],
verdict}` plus a top-level family-size disclosure block and a `narration` field
(B.4).

### B.3 Loop wiring (no gate change)

- **Tuner priority (WS-9):** the loss artifact yields a *prioritized target
  list* — a tunable whose scope/regime is bleeding is evaluated first / flagged.
  It does **not** alter the tuner's walk-forward CI gate or its
  candidate/keep verdict logic; it only orders/annotates.
- **Readiness + dashboard:** a "where we bleed" line per specialist on the
  council panel and in the nightly readiness report.

### B.4 LLM narration layer (commentary only)

An optional pass over the deterministic artifact produces per-scope
"what went wrong + a hypothesis to try" text, written to the artifact's
`narration` field. Reuses the codebase's existing verified-LLM signal
infrastructure (no new dependency/model). **Commentary only** — it never
mutates params, constants, promotions, or execution logic; a human reads it and
decides. Fail-closed: LLM unavailable/errors/times out → the deterministic
attribution is still produced and `narration` is empty. The narration is the
sole appearance of Phenon's "self-evolution" idea, deliberately bounded to
human-read text.

### B.5 Discipline

Pure read-only analysis; zero capital/pricing/promotion mutation (assert
source-file + promotions-file hashes unchanged after a run, mirroring the WS-9
no-mutation test). Cluster-level, family-size disclosed, point-in-time (settled
rows only).

### B.6 Tests

- Planted-loss fixture: a scope seeded to bleed in one feature tercile →
  attribution names that bucket, cluster-level, CI-disclosed.
- Noise → no confident bucket (insufficient_data / keep).
- No-mutation: only `loss_attribution.json` written; source + promotions files
  hash-identical after a run.
- LLM-down → deterministic artifact still produced, `narration` empty.
- Family-size disclosure present and accurate.
- Tuner-priority consumption: a bleeding scope raises the matching tunable's
  priority without changing its walk-forward verdict.

---

## Component C — L1 market-state routing documentation (docs only)

**Files:** Create `docs/MARKET_STATE_ROUTING.md`; link from `docs/AUTONOMY.md`.
No code, no tests (verified truthful against code in review).

Content: make explicit the Phenon L1 "Ontological Market Manifold" already
implemented as council routing —

- `SpecialistRegistry` maps each market to exactly one specialist by
  vertical/league (`specialist_for` / registry routing).
- Per-vertical governing logic differences: crypto (DVOL-implied book,
  lognormal price model, event/FOMC windows, 15m/hourly/daily horizons) vs
  sports (per-league margin distributions, live-gating, season windows, pre/live
  phases).
- `SeasonMonitor` wake/sleep gating; the 3×3 conviction lattice + coherence
  engine sitting on top of the routed forecasts.
- A mapping table: Phenon L1/L2/L3 vocabulary → the real dummy modules
  (including where Components A and B land).

All claims verified against the code; nothing overstated (same docs-truthfulness
bar the WS-13 review applied).

---

## What is explicitly NOT built (rejected from the Phenon concept)

- **Perpetual futures** volume/funding/basis ingestion — standing operator law
  "it should not be doing perpetuals" (WS-17 already cancelled the funding/basis
  half). Out.
- **Scraping** DRatings/KenPom/Massey/Dimers/OddsShark or any paid ratings site
  — ToS/evasion. The ensemble uses only first-party keyless (ESPN FPI/BPI) or
  license-vetted public-domain sources.
- **Autonomous self-rewrite** of execution/pricing logic. The evolution engine
  deconstructs and proposes; a human promotes. The LLM narration is commentary,
  never auto-acted.

## Rollout

Three workstreams (A, B, C), each: hand-computed fixture tests, full suite green
(trust exit code), adversarial opus review per PR (findings fixed + verdict
quoted in the PR body), merge. All challenger-only — nothing promoted in this
plan's scope; paper evidence accrues from merge day. Build order chosen by
least-risk-to-merge as work proceeds (C and B are independent of A; A is
largest). Component A may split into fetch/consensus and emission workstreams if
the single PR grows too large.

## Data-probe appendix (verify at build, commit trimmed fixtures)

| Probe | Needed by | Expected |
|---|---|---|
| ESPN FPI payload (`.../fitt/v3/sports/football/{nfl,college-football}/powerindex`) | A | `teams[].team.abbreviation` + `teams[].categories[]` FPI value; keyless 200 (confirmed) |
| ESPN BPI payload (`.../basketball/{nba,mens-college-basketball}/powerindex`) | A | same shape; keyless 200 (confirmed nba/nba, verify ncaamb) |
| Settled-row feature coverage for loss buckets | B | existing ledger features (per WS-15 taxonomy scope axes) suffice for tercile buckets |
| Existing verified-LLM client entrypoint | B | reuse the codebase's LLM signal path; confirm the call/timeout/fail-closed contract |
