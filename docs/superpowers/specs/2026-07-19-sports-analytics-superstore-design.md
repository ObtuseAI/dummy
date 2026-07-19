# Sports Analytics Superstore, Recursive Sim Foundry & Performance Telemetry

**Date:** 2026-07-19
**Status:** Design — approved in shape (Chris, 2026-07-19: "yes to all of it, be aggressive and innovative"), pending spec review.
**Builds on:** Wave-55 (full sports roster + `scope_analytics`/dashboard, PR #165), the Phenon Harness power-ratings ensemble, the council-of-specialists layer, and the existing recursive sim lab.

## 1. Goal

Give every sports league Dummy trades (MLB, WNBA, NBA, NFL, NHL, NCAAF, NCAAMB) a **massive, state-of-the-art, recursively-improving analytics stack** built from as much free public data as we can reach, all of it pouring into the per-sport simulators to sharpen accuracy — and make that sharpening **visible**: track and display accuracy *improvement over time*, overall and sliced per crypto coin / per sports league / per **bet type** (winner, total, spread, props, …).

Three data/analytics layers plus a telemetry layer plus the recursive loop that ties them together:

1. **Historical Data Lake** — deep, point-in-time, multi-season store of everything free/public per league.
2. **Advanced Analytics Foundry** — SOTA public methods replicated/computed from the lake, as point-in-time sources.
3. **Recursive Sim Foundry** — every analytic flows into the simulators; grades feed a walk-forward tuning loop.
4. **Performance & Improvement Telemetry** — measure + display the sharpening (overall / scope / bet-type).
5. **Closing-Line History** — persisted closing prices + movement to ground CLV and the market-pressure pipeline.

## 2. Governance & data boundary (non-negotiable)

Chris's directive (2026-07-19): *"without paying I want as much as possible, even if scraping is required … applies to all sports leagues we trade."*

**In bounds:** any **free, public** data — open datasets (nflverse/nflfastR, Retrosheet, MLB StatsAPI, ESPN public JSON, NBA `stats.nba.com`, public college feeds) and **polite scraping** of free public pages (sports-reference family, box-score/PBP pages, free odds/line pages).

**Out of bounds (hard):** paid feeds or paywalled content; **no login/credential/paywall bypass**; **no CAPTCHA solving**; nothing that requires an account we'd have to create. If a source needs payment or auth, we **replicate the published method** from free results instead (as we already do for DVOA/KenPom/Massey).

**Polite-scraper contract (so we stay un-banned and sustainable):** per-host rate limiting + jitter, exponential backoff honoring `Retry-After`/429/503, a persistent on-disk response cache (so a backfill is idempotent and re-runs are cheap), a real descriptive User-Agent, `robots.txt` fetched and logged, conservative concurrency, and resumable/incremental checkpoints. All reads are GETs; nothing mutates a remote.

**Point-in-time discipline (non-negotiable, matches the rest of `autonomy/`):** every row carries an `as_of` timestamp and provenance; any feature computed for a game uses **only** data available strictly before that game's start; the backtest/warm-up harness can reconstruct the exact information set at any past instant. No future leakage, ever. Challenger-only + fail-closed remain in force: nothing here auto-trades; new sources enter as challengers and must earn promotion on contested-Brier as always.

## 3. Point-in-time architecture

```
   FREE PUBLIC SOURCES                  LAYER 1                 LAYER 2                LAYER 3
  (open data + polite scrape)      Historical Data Lake     Analytics Foundry      Recursive Sim
  nflfastR · Retrosheet · ESPN  →  sports_history.db     →  RatingSource/Signal →  per-sport sims
  StatsAPI · stats.nba.com ·        (games, boxscores,       (EPA, xG, RAPM-lite,   (mlb_pa_sim,
  sports-ref · free odds pages       PBP, players, lines,     four-factors, Glicko,  nba/nhl/nfl,
                                      injuries, weather)       xwOBA, Kalman, …)      unified harness)
                                          │  as_of + provenance      │                     │
                                          ▼                          ▼                     ▼
                                    LAYER 5 Closing-line ──────►  ensemble/trust ◄──── settlements
                                                                     │  graded
                                                                     ▼
                                             LAYER 4 Performance & Improvement Telemetry
                                        overall / per coin / per league / per bet-type + Δimprovement
                                                     (dashboard overview + scope views)
                                                                     │
                                                                     ▼
                                        walk-forward tuning loop → reweight/retune/promote (recursion)
```

Reuse existing machinery wherever it exists: the `RatingSource`/`Signal` interface, `SourceRegistry`, the trust surface, the promotion ledger + contested-Brier gate, `run_dummy_sports_*` scripts, the `Dummy*` scheduled-task durability, and the Wave-42 snapshot/contention rules (dashboard never opens a hot DB).

## 4. Phase decomposition & sequencing

Each phase is its own spec → plan → PR. Two phases can start immediately because they don't depend on the lake:

| Phase | Strand | Depends on | Why this order |
|------|--------|-----------|----------------|
| **1** | **Historical Data Lake + polite-scraper framework** | — | Foundation everything else reads. Spec'd in detail below. |
| **1b (parallel)** | **Performance & Improvement Telemetry** | existing ledger (Wave-55 scope_analytics) | Ships accuracy+improvement display **now** on current data; deepens later. Spec'd in detail below. |
| **2** | **Analytics Foundry** | Phase 1 | New sources computed from the lake. |
| **3** | **Closing-Line History + CLV grounding** | Phase 1 framework | Reuses the scraper; grounds CLV/market-pressure. |
| **4** | **Recursive walk-forward tuning loop** | Phases 1–3 | Backtests each analytic's marginal contribution; retunes/promotes; scheduled. Closes the flywheel. |

## 5. Phase 1 — Historical Data Lake (detailed)

### 5.1 Store
New `runtime/autonomy/sports_history.db` (SQLite, WAL-unsafe per repo policy → rollback journal + retention task, like the other stores). Tables (all with `as_of`, `source`, `fetched_at`, `provenance_url`):

- `games` — `game_id, league, season, start_time, home, away, home_score, away_score, status, venue, neutral, …`
- `boxscores` — per team/player per game (points/possessions/goals/shots/at-bats/…); superset of the current on-the-fly `boxscores.py` derivation, now persisted.
- `plays` — play-by-play where free (nflfastR NFL; ESPN PBP; `stats.nba.com` PBP; college via hoopR-style endpoints). Sport-specific columns namespaced or JSON-blobbed with a typed view per sport.
- `players` / `player_games` — rosters + per-game player lines (props grounding).
- `lines` — historical odds/closing lines per market (feeds Phase 3; schema defined here so the lake is line-aware from day one).
- `injuries`, `weather` — historical context (extend the existing ESPN/Open-Meteo adapters to persist).
- `ingest_log` — per (source, league, date-range) checkpoint: status, rows, http stats, cache hits → idempotent resumable backfills.

Indexes on `(league, season, start_time)` and `(game_id)`; a read API (`autonomy/sports/history_store.py`) exposing point-in-time queries (`games_before(as_of, league)`, `player_form(player, as_of)`, …) so models and the backtester never hand-roll SQL.

### 5.2 Polite fetch framework
`autonomy/ingest/fetcher.py` — one shared client: per-host token-bucket rate limiter, jittered backoff honoring `Retry-After`, on-disk cache keyed by URL+params (TTL + force-refresh), descriptive UA, `robots.txt` fetch/log, structured provenance on every response. Every source adapter is built on it.

### 5.3 Source adapters (per league, highest-value free first)
- **NFL / NCAAF:** nflverse/nflfastR (open parquet/CSV: PBP with EPA, rosters, schedules) — *use directly, no scraping*; ESPN archives for gaps.
- **MLB:** Retrosheet (multi-decade game/event logs, free+attribution) + MLB StatsAPI (have adapter; extend to historical) + Statcast/baseballsavant public CSV endpoints (pitch-level, xwOBA inputs) via the polite fetcher.
- **NBA / WNBA:** `stats.nba.com` public JSON (boxscores, PBP, lineups — needs correct headers, polite pacing) + ESPN.
- **NHL:** NHL public stats API (shots → xG inputs, boxscores) + ESPN.
- **NCAAMB / NCAAF:** ESPN + hoopR/cfbfastR-style public endpoints where free; sports-reference pages via polite scrape for gaps.

Backfill scripts (`scripts/run_dummy_sports_history_backfill.py --league … --seasons …`) are resumable via `ingest_log`. A scheduled `DummySportsHistory` incremental updater task appends newly-final games daily (existing durability pattern), bounded by a retention/VACUUM policy.

### 5.4 Tests & success criteria
- Adapters parse fixture payloads into typed rows; point-in-time query API proven leak-free (a `games_before(t)` never returns a game starting ≥ t) with unit tests.
- Fetcher: rate-limit/backoff/cache honored under a fake clock + fake transport (no network in tests).
- Backfill idempotency: re-running a range makes zero new HTTP calls (all cache hits) and zero duplicate rows.
- **Done when:** ≥3 prior seasons of games+boxscores land for every league that has them free, PBP for the leagues where it's free, and a model can pull point-in-time priors from the store.

## 6. Performance & Improvement Telemetry (detailed — Phase 1b)

### 6.1 Dimensions
Every metric is computed at three nesting levels, each split by **bet type**:
- **Overall** (whole organism) — on the dashboard overview.
- **Per scope** — each crypto coin (BTC/ETH/SOL/…) and each sports league.
- **Per bet type** within a scope — `bet_type_of(ticker)`:
  - Sports: the registry's `market_type` — `winner, spread, total, team_total, yrfi, prop:<family>, segment:<1H|2H|1Q…|F5>`.
  - Crypto: `parse_crypto_ticker().contract_family` — `ladder(above/below), between(range), 15m_direction, hourly, daily, weekly`.

### 6.2 Metrics per cell
`n`, `hit_rate`, `brier`, `market_brier`, `brier_edge` (contested), plus ROI/CLV where available — reusing `scope_analytics._summarize`, extended to group by `(vertical, label, bet_type)`.

### 6.3 Improvement (the new thing Chris asked for)
For each cell we compute a **trend**, not just a level:
- **Windowed delta:** recent window vs the immediately-prior window — `Δbrier = prior_brier − recent_brier` (positive = sharper), `Δhit`, `Δedge`. Windows are equal-count (comparable) or fixed-days, configurable.
- **Slope:** linear fit over the existing per-cell progression buckets → an improving/flat/declining classification with a magnitude.
- **Significance:** reuse the repo's cluster-bootstrap discipline for a CI on the delta where `n` allows; below a floor we show the number but mark it "thin."
- **Long-horizon record:** a persisted `runtime/autonomy/accuracy_history.jsonl` sidecar, appended by the snapshot writer each run — `{ts, active_weights_hash, cell, metrics}`. This survives ledger retention (settlements age out) so we can chart "are we getting better" across model versions and each recursive retune — the telemetry that proves Layers 1–4 are working. Rotation via the existing allowlisted log-rotation (line-cap, tail-preserve).

### 6.4 API + display (extends Wave-55)
- `build_scope_analytics` gains a `bet_types` breakdown per scope + a per-cell `improvement` block; `build_overview` gains an overall accuracy+improvement rollup and a scope×bet-type matrix. Served via existing `/api/overview` + `/api/scopes` (snapshot-backed, never the ledger).
- **Dashboard (autonomy/dashboard_ui.py):**
  - *Overview:* an "Accuracy & Improvement" hero — overall Brier/hit-rate with a big **Δ arrow** and an accuracy sparkline over time (from `accuracy_history`); a **scope × bet-type heatmap** (rows = coins+leagues, cols = bet types, cell colored by edge or Δimprovement) for at-a-glance "where are we sharp / getting sharper."
  - *Scope view:* a **bet-type breakdown table** (per bet type: n / hit / Brier / market Brier / edge / Δimprovement arrow) plus the progression chart optionally split by bet type.
- Reduced-motion + AA hold (Wave-55 conventions).

### 6.5 Tests
- `bet_type_of` classifies representative sports + crypto tickers correctly.
- Per-cell aggregation + improvement math verified on a synthetic ledger (known trend → known Δ/slope/classification).
- `accuracy_history` append is atomic, rotation is allowlisted (never blind-truncated), and the dashboard renders overall + per-scope + per-bet-type from a snapshot with zero ledger access.

## 7. Analytics Foundry (Phase 2 — strand overview)

Computed from the lake as fail-closed point-in-time sources on the existing interface; each is a challenger gated on contested-Brier. Candidate catalog (aggressive; final shortlist scored during Phase 2 spec):

- **Cross-sport ratings:** margin-of-victory Elo, **Glicko-2**, **Bradley-Terry / logistic** strength, **Kalman / state-space** dynamic team strength, market-implied power ratings, strength-of-schedule adjustment, injury-adjusted ratings (+ existing Massey/Colley/FPI/BPI).
- **NFL/NCAAF:** **EPA/play, success rate, opponent-adjusted DVOA-style** efficiency, QB adjustment, pace/pass-rate, from nflfastR PBP.
- **NBA/WNBA/NCAAMB:** **four factors** (eFG%, TOV%, ORB%, FT rate), **RAPM/APM-lite** (ridge regression on PBP stints), **KenPom-style adjusted efficiency**, pace, rest/travel.
- **MLB:** **xwOBA / xFIP / SIERA / xERA** (Statcast inputs), catcher framing, **Pythagenpat** expectation (+ existing log5/park/platoon/baserunning).
- **NHL:** **expected goals (xG)** from shot data, Corsi/Fenwick, PDO, goalie identity (existing).
- **Generic:** per-feature calibration/reliability, Bayesian shrinkage priors from the lake replacing cold priors.

Each source declares its inputs so the validation harness can attribute misses to missing data (the StatsAPI presence-tracking pattern).

## 8. Recursive Sim Foundry & tuning loop (Phase 4 — strand overview)

- Every foundry source feeds the per-sport simulators (`mlb_pa_sim`, `nba_model`, `nhl_model`, `nfl_margin`, and a unified harness) so all markets for a game stay coherent (one distribution → winner/spread/total/props).
- A **walk-forward tuning loop** replays the lake in chronological order (strict point-in-time), grades sim output vs settlements, measures **each analytic's marginal contribution** (ablation), replaces cold priors with historical priors, reweights the trust surface, and promotes/prunes by contested-Brier — self-scheduled as new games land (existing `Dummy*` durability + promotion ledger).
- The telemetry (Layer 4) is the read-out: each retune should show up as improvement in the per-cell trend.

## 9. Closing-Line History (Phase 3 — strand overview)

Reuse the Phase-1 fetcher to persist closing prices + line movement per market into `lines`, grounding CLV and the market-pressure/steam pipeline against real closes instead of live-only snapshots.

## 10. Risks & mitigations

- **Scraper bans / fragility:** polite contract (rate-limit, cache, backoff, UA), fail-closed adapters, prefer open datasets over scraping, per-source health in the dashboard. A dead source drops out silently; it never breaks a cycle.
- **Point-in-time leakage:** single source of truth for `as_of`; leak tests in the store API; backtester reconstructs information sets; no feature reads its own game's result.
- **Data volume / disk:** the ledger is already ~16 GB — the lake needs its own retention/VACUUM task and a bounded footprint from day one (reuse the retention machinery).
- **Compute:** pure-Python house style (no numpy/scipy) → RAPM ridge / Kalman need careful hand-rolled solvers (we already ship `solve_spd` Gauss-Seidel); heavy fits run in scheduled tasks, never on the request path.
- **Scope creep:** phased; each phase is independently shippable and gated. Telemetry (1b) delivers visible value immediately.

## 11. Success criteria

- Lake holds ≥3 free seasons/league (where available) with proven point-in-time integrity.
- Overview + every scope show accuracy **and improvement**, sliced by bet type, from a snapshot (zero ledger access), reduced-motion + AA clean.
- ≥1 new foundry analytic per league promoted on contested-Brier (Phase 2+).
- The walk-forward loop demonstrably lifts sim accuracy (telemetry trend turns positive after retunes).
- Boundary held: free/public only, polite, no paywall/auth/CAPTCHA; challenger-only + fail-closed intact.

## 12. Open questions

- Retention depth per league (how many seasons to keep hot vs archive)?
- Unified sim harness vs keeping the four bespoke per-sport models (likely: keep bespoke, add a shared feature-injection seam)?
- Telemetry improvement window defaults (fixed-days vs equal-count; the "thin sample" floor)?
