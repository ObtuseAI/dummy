# Takeover Report — Phenon Harness Integration (2026-07-13)

Handoff for whoever picks this up next. Everything below is on `main`; the suite
is 5420 green (`python -m pytest -q --timeout=300` — use 300, see the flake note).

## What shipped

The "Phenon Autopoietic Harness" concept was folded into dummy as three
components, all challenger-only, fail-closed, and human-gated (no perps, no
scraping, no autonomous self-rewrite of execution logic). Spec + plan: PR #65
(`docs/superpowers/specs/2026-07-13-phenon-harness-integration-design.md`,
`docs/superpowers/plans/2026-07-13-phenon-harness-integration.md`).

| WS | PR | Merge | Deliverable |
|---|---|---|---|
| WS-C | #66 | `2f760b6` | `docs/MARKET_STATE_ROUTING.md` — L1 "who governs this market" routing docs |
| WS-A1 | #67 | `00c9555` | `autonomy/sports/power_ratings.py` — rating-source fetch + consensus core |
| WS-A1-fix | #70 | `929b097` | Critical scale correction (see below) |
| WS-B | #68 | `e9f1b24` | `autonomy/loss_engine.py` — loss-deconstruction evolution engine |
| WS-A2 | #69 | `7dedb46` | power-ratings emissions in `autonomy/signals/sports_intelligence.py` |
| WS-A1b | #71 | `8960d0c` | `autonomy/sports/ratings_solvers.py` — in-house Massey + Colley |

## Architecture

### Power-ratings ensemble (WS-A1 / A1-fix / A2 / A1b)
- **Sources** (`RatingSource` protocol: `name`, `rating(league, team) -> float|None`,
  `points_per_unit(league) -> float|None`):
  - `EspnFpiSource` / `EspnBpiSource` — keyless ESPN powerindex (`power_ratings.py`).
  - `EloSource` — wraps the already-warm `EloModel` (read-only; membership-checked so
    it never fabricates `BASE_RATING` for unknown teams).
  - `MasseyRatingSource` / `ColleyRatingSource` — in-house, computed from public
    settled scores via pure-Python Gauss-Seidel (`ratings_solvers.py`).
- **Consensus** (`consensus_margin`): each source converts its rating diff to an
  expected **point margin** via its own `points_per_unit`, and the ensemble takes the
  **median** of the implieds (dispersion = max−min). FPI/BPI → 1.0 (already point-scale),
  Elo → `1/ELO_POINTS_PER_MARGIN[league]`, Massey → 1.0 (native points), Colley →
  `COLLEY_POINTS_PER_UNIT[league]`.
- **Emission** (`PowerRatingsSignal` in `sports_intelligence.py`): a challenger
  winner + full spread ladder from ONE distribution (`margin_distribution` football /
  NBA normal helper basketball) so winner and spread stay coherent; plus a
  `power_divergence` feature when `abs(ensemble − kernel) > DIVERGENCE_THRESHOLD[league]`
  AND `dispersion < DISPERSION_CEILING[league]`. High dispersion widens uncertainty only
  (capped), never shifts the mean. Pre-game-only (no live double-count). Registered in
  `autonomy/session.py::build_brain`; challenger-only, excluded from `forecaster.fuse()`.

### Loss-deconstruction evolution engine (WS-B)
- `autonomy/loss_engine.py`: `build_loss_attribution(rows, now_iso)` groups settled rows
  by grading scope, finds scopes with negative cluster-level Brier edge (`n_clusters ≥
  MIN_CLUSTERS`), buckets each by feature regime / market type / phase / horizon, and
  writes a **read-only** `runtime/autonomy/loss_attribution.json` with per-scope worst
  buckets, 95% CIs, verdicts, and top-level `family_size`.
- `narrate_losses(attribution, router)` adds LLM prose commentary (`ModelTask.CALIBRATION_NOTE`),
  fully fail-closed: router down / import broken / malformed → artifact still written,
  `narration == {}`.
- `loss_priority(attribution)` feeds the WS-9 tuner a **non-gating** ordering (the
  walk-forward CI gate and candidate/keep verdict are byte-identical with/without it).
- Nightly script `scripts/run_dummy_loss_engine.py`; dashboard/readiness show a
  "where we bleed" line. Mutates no source, param, or promotion (SHA-256 no-mutation test).

## The Critical bug (WS-A1-fix, PR #70) — read this

WS-A1's `consensus_margin` multiplied **every** source's rating diff by one per-league
constant `{nfl:25, ncaaf:25, nba:28, ncaamb:28}`. Two compounding errors:
1. `25`/`28` are Elo-points-**per**-margin-point (FiveThirtyEight) — expected margin is
   `elo_diff / 25`, not `× 25`. An Elo diff of 75 → intended 3.0 pts, code produced **1875**.
2. FPI/BPI are already point-scale (ESPN "expected point margin vs average opponent"),
   so their diff ≈ the spread (unit ≈ 1.0) — the `×25` inflated a 2-pt edge to 50.

Median of those → hundreds of points → the WS-A2 challenger ladder win-prob pinned at
~1.0 on every game. **No capital was at risk** (challenger-only, out of `fuse()`), but the
challenger's CLV/Brier record was meaningless — which defeats building a challenger you
intend to eventually promote.

**Why every review missed it:** each per-WS opus pass checked fail-closed / gating /
*formula* coherence, and WS-A2's hand-check assumed `margin=6.0` as an input rather than
deriving it from real ratings. WS-A1's own tests validated the multiply *mechanism* with a
synthetic scale — which passes in any direction.

**Lesson (recorded in memory):** challenger-only status + abstract-mechanism tests hid a
dimensionally-broken live output. When combining sources on different native scales, add a
**realistic-magnitude sanity test** (the fix added one: KC−DEN Elo → 3.0, would be 1875
under the old code). Fix = per-source `points_per_unit(league)` contract.

## Deferred follow-ups (logged, non-blocking)

1. **`power_divergence` unconsumed.** It's emitted into the challenger `Signal.features`
   but `opportunist.py` / `mispricing.py` don't read it yet. Wire it into the opportunist
   path to actually act on ensemble-vs-kernel divergence as buy-low evidence.
2. **Massey/Colley freeze at construction.** The solve runs once at `PowerRatingsSignal`
   construction and is cached; unlike Elo/TeamScoreModel it doesn't refresh on
   `on_cycle_start`. Fine only if `PowerRatingsSignal` is periodically reconstructed —
   confirm the daemon's reconstruction cadence, or add a periodic re-warm.
3. **Colley tie handling.** `Game.home_won` collapses ties to a home win upstream
   (`espn.py`), so Colley can't see true ties. Near-zero impact for the 4 Colley leagues
   (rare NFL ties only); fix at the feed layer if it ever matters.
4. **NCAAF uses the college key-number table** now (matches WS-C doctrine), but still
   reuses the NFL margin kernel wholesale otherwise — a shallower college-specific kernel
   is a future fidelity improvement.

## Pre-promotion punch list (from Part I whole-branch review — separate from Phenon)

Logged in memory `dummy-council-of-specialists`; not Phenon scope, but these block
promoting the sports challengers to capital:
1. WS-3 NHL live winner omits pulled-goalie λ (winner/cover incoherent final 3 min).
2. WS-6 expected-score display fields pre-shift while prob is post-shift.
3. WS-7 NFL bye gap-detect fails open (+1.0 mean) on daemon-missed games.
4. Mismatch finder inert (tanh gate never crossable, sources hard-capped ≤ 1.5).
5. NBA WS-2 lone engine still reading generic uncertainty (consistency).

## How to resume / process notes

- **Ledger:** `.superpowers/sdd/progress.md` (git-ignored scratch) records every WS with
  commit ranges and review verdicts. Trust it + `git log` over memory after a compaction.
- **Suite flake:** `test_no_secret_leak_v3.py` scans ~2 GB `artifacts/` and times out under
  the default 60s. Always run the full suite with `--timeout=300`; a clean run is 5420 passed.
- **Subagent stall pattern (recurring):** implementer subagents repeatedly backgrounded the
  test suite and yielded before committing. Mitigation that worked every time: take over —
  check the tree (`git status`), run the full suite in the FOREGROUND yourself, verify, then
  commit manually. Dispatches now say "run suite FOREGROUND, do NOT yield," but expect it.
- **Per-source scaling contract:** any NEW `RatingSource` MUST implement `points_per_unit`
  returning its rating diff → point-margin multiplier (or `None` to drop for a league).
  Do NOT reintroduce a shared per-league multiplier. Add a realistic-magnitude test.
- **Discipline for the next component:** branch per WS off `main`; challenger-only
  (`features["challenger_only"]=True`, `promotion_eligible=False`); fail-closed (missing feed
  → `None`, byte-identical to disabled); per-PR adversarial opus review with the verdict
  quoted in the PR body; full suite green before merge.
