# Phenon Harness Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fold the sound parts of the Phenon Autopoietic Harness into dummy — an external-power-ratings ensemble challenger, a loss-deconstruction evolution engine, and L1 market-state routing docs — all challenger-only, fail-closed, human-gated.

**Architecture:** Three workstreams. WS-A (split A1 pure fetch+consensus core, A2 emissions) adds a power-ratings ensemble that prices a standalone challenger ladder and an opportunistic divergence flag. WS-B adds a deterministic Brier-shortfall loss-attribution artifact (+ LLM narration commentary) that feeds the WS-9 tuner's target priority and the readiness/dashboard surface. WS-C documents the already-built L1 routing.

**Tech Stack:** Python 3.14, existing autonomy stack (ESPN keyless feeds, `EloModel`, `nfl_margin` machinery, `strategy_miner`/`stats` plumbing, verified-LLM router), pytest.

**Spec:** `docs/superpowers/specs/2026-07-13-phenon-harness-integration-design.md` (authoritative).

## Global Constraints

Every task's requirements implicitly include these (verbatim from the spec):

- **Challenger-only.** Every emitted `Signal` sets `features["challenger_only"]=True` and `features["promotion_eligible"]=False`; `forecaster.fuse()` excludes challengers from execution until a human promotion. Nothing here reaches the live allocator/executor unpromoted.
- **Fail-closed.** Missing feed / thin data / offseason / LLM-down → abstain (`None` / empty), byte-identical to the feature being disabled. Doctrine test: feature-present-but-empty == feature-disabled.
- **Point-in-time.** Analysis/learning use only settled (`status=="post"`) rows; ratings/live data never enter `update()`.
- **Per-event-CLUSTER means, never per-row CIs.** Disclose mined family size.
- **Propose-then-human-promote.** No component mutates constants, promotions, or execution logic. Auto-demotion is the only automatic transition. The LLM narration is human-read commentary, never auto-acted.
- **No perps. No scraping.** External data only via first-party keyless (ESPN FPI/BPI) or license-vetted public-domain feeds.
- **Per-PR adversarial opus review is mandatory** (caught a real blocker/Important in the majority of Part I PRs). Findings fixed + verdict quoted in the PR body. Full suite green (trust the exit code).

**Recommended build order (least-risk-to-merge, flexible):** WS-C → WS-A1 → WS-B → WS-A2. C is docs-only; A1 is a pure new module (zero blast radius on the live hook); B is a new module + a read-only artifact + a non-gating tuner annotation; A2 touches the live sports hook last, with the grading loop already in place to evaluate it.

---

## WS-C: L1 market-state routing documentation (docs only)

**Files:**
- Create: `docs/MARKET_STATE_ROUTING.md`
- Modify: `docs/AUTONOMY.md` (add a link to the new doc)
- Test: none (docs; verified truthful against code in review)

**Interfaces:**
- Consumes: reads (does not change) `autonomy/specialists/base.py::SpecialistRegistry`, `autonomy/taxonomy.py::specialist_for`, `autonomy/specialists/seasons.py::SeasonMonitor`, the crypto/sports specialist modules, `autonomy/coherence.py` (3×3 lattice).
- Produces: documentation only.

**Content (every claim verified against code — do not overstate):**
- How `SpecialistRegistry` routes each market to exactly one specialist by vertical/league (`specialist_for` + registry routing).
- Per-vertical governing-logic differences: crypto (DVOL-implied book, lognormal price model, event/FOMC windows, 15m/hourly/daily horizons) vs sports (per-league margin distributions, live-gating, season windows, pre/live phases).
- `SeasonMonitor` wake/sleep gating; the 3×3 conviction lattice + coherence engine sitting on the routed forecasts.
- A mapping table: Phenon L1/L2/L3 vocabulary → real dummy modules, including where WS-A (L2) and WS-B (L3) land.

**Steps:**
- [ ] Read each referenced module; draft `docs/MARKET_STATE_ROUTING.md` mirroring the module docstrings (they are accurate).
- [ ] Add a one-line link from `docs/AUTONOMY.md`.
- [ ] Commit: `docs: L1 market-state routing (Phenon manifold) documentation (WS-C)`.

**Review focus:** docs-truthfulness only — no sentence may claim a feature not in the code, imply autonomous promotion, or misstate the human-gate/fail-closed doctrine (same bar as the WS-13 review).

---

## WS-A1: Power-ratings fetch + consensus core (pure module)

**Files:**
- Create: `autonomy/sports/power_ratings.py`
- Test: `tests/test_autonomy_power_ratings.py`
- (No hook edit in this task — pure module + tests only.)

**Interfaces:**
- Consumes: `autonomy/sports/elo.py::EloModel.rating(team) -> float`; ESPN keyless HTTP (mirror the fetch pattern in `autonomy/sports/ballpark_weather.py::default_fetch_hourly_weather` — `httpx` GET, defensive parse).
- Produces (later tasks rely on these exact signatures):
  - `class RatingSource` protocol: `.name: str`, `.rating(league: str, team: str) -> float | None`.
  - `EspnFpiSource`, `EspnBpiSource`, `EloSource(elo_model)` implementing it.
  - `@dataclass ConsensusMargin: ensemble_margin: float; dispersion: float; n_sources: int; per_source: dict[str, float]`.
  - `consensus_margin(home: str, away: str, league: str, sources: list[RatingSource]) -> ConsensusMargin | None`.
  - `POINTS_PER_RATING_UNIT: dict[str, float]` (per-league calibration; tuner candidate).
  - `default_fetch_powerindex(league: str) -> dict` and `parse_powerindex(payload, league) -> dict[str, float]` (team-abbr → rating).

**Data probes (do REAL keyless probes at build; commit trimmed fixtures; fail-closed if offseason/unreachable):**
- FPI: `https://site.web.api.espn.com/apis/fitt/v3/sports/football/{nfl|college-football}/powerindex?limit=1000` — confirmed keyless 200; `teams[].team.abbreviation` + `teams[].categories[]`; find the FPI/rating value field (inspect `glossary`/`categories`), record the exact JSON path in a module comment, commit a trimmed fixture.
- BPI: `.../basketball/{nba|mens-college-basketball}/powerindex` — same shape; verify ncaamb returns data in-season (offseason → empty → fail-closed).

**Algorithm:**
- `parse_powerindex`: defensive — missing team/rating/array → that team absent (never crash); returns `{team_abbr: rating}`.
- Each source's `rating()` maps team → its rating or `None` (feed down/team missing).
- `consensus_margin`: for each source with both teams present, `implied = (rating(home) - rating(away)) * POINTS_PER_RATING_UNIT[league]`; collect implieds; `ensemble_margin = median(implieds)`; `dispersion = max(implieds) - min(implieds)` (or IQR); `n_sources = len(implieds)`. **Zero implieds → return `None`.** No side effects; ratings never enter learning.

**Test targets (hand-computed, zero network):**
- Consensus: fixed source ratings + scale → exact `ensemble_margin` (median) and `dispersion`.
- One source returns `None` for a team → dropped from consensus; result uses the rest.
- All sources `None` → `consensus_margin` returns `None`.
- `parse_powerindex` on a malformed/short payload → empty dict, no exception (fail-closed).
- `EloSource` wraps `EloModel.rating` and never calls `.update()`.
- Committed FPI/BPI fixtures parse to non-empty rating maps.

**Steps:** probes → fixtures → tests first → implement → full suite green → commit `feat: power-ratings fetch + consensus core (WS-A1)`.

**Review focus (opus):** consensus math (median + dispersion), every fail-closed path (`None`/empty), no learning leak, keyless-only sources (no scraping).

---

## WS-A2: Power-ratings emissions — challenger ladder + divergence flag

**Files:**
- Modify: `autonomy/signals/sports_intelligence.py` (new power-ratings block in the sports hook, mirroring the WS-2/3/4 engine hook pattern)
- Modify: `autonomy/taxonomy.py` (SOURCE_TAXONOMY / `_SPECIALIST_PREFIXES` entry so `specialist_for` routes the new source to the right per-league specialist scope)
- Test: `tests/test_autonomy_power_ratings_emit.py` (+ extend `tests/test_autonomy_sports_intelligence.py`)

**Interfaces:**
- Consumes: WS-A1 `consensus_margin` / `ConsensusMargin`; `autonomy/sports/nfl_margin.py::margin_distribution(expected_margin, base_pmf=None)`, `win_probability`, `spread_cover_probability`, `normal_over_probability`; `autonomy/ontology.py::Signal(source, market_ticker, probability_yes, uncertainty, features={...})`; the existing per-league engine's own expected margin (for the divergence gap) and the Kalshi mid from `MarketView`.
- Produces: a challenger `Signal` (`source="power_ratings_<league>"` or similar, routed by taxonomy) with `margin_model_version="power_ratings_consensus_v1"`; a `power_divergence` feature on the opportunist/mispricing path.

**Emission 1 — standalone challenger:** `ensemble_margin` → winner + full spread ladder from ONE distribution: `margin_distribution` (football) / normal-margin (basketball, reuse the WS-2 normal helper). `features["challenger_only"]=True`, `features["promotion_eligible"]=False`, version stamp, `per_source`/`n_sources`/`dispersion` logged. **High `dispersion` → widen `uncertainty` only** (bounded add, cap it), never a silent suppress or a mean shift. If emitted on a live market, gate the same way WS-6/7 gate (`not (nba_live or nhl_live)`) — but the first pass may emit pre-game-only (simplest; state which in the report).

**Emission 2 — opportunistic divergence flag:** compute `gap = ensemble_margin - our_engine_margin` (and/or consensus-implied prob − Kalshi mid). Emit a bounded `power_divergence` feature into the opportunist/mispricing path **only when** `abs(gap) > DIVERGENCE_THRESHOLD[league]` **AND** `dispersion < DISPERSION_CEILING[league]` (sources agree). High dispersion suppresses the flag. Challenger-only evidence; never a capital action.

**Taxonomy:** add the new source name(s) to `SOURCE_TAXONOMY` (or a `_SPECIALIST_PREFIXES` prefix like `("power_ratings_", <league-routing>)`) so `specialist_for` resolves the CLV/backtest `(specialist, market_type)` scope. Collision-free (mirror the 7 WS-8 self-mappings).

**Test targets:**
- Challenger: fixed consensus margin → expected winner + spread-ladder probabilities (hand-computed via `margin_distribution`); version stamp + `challenger_only` present.
- High dispersion widens uncertainty, mean byte-identical.
- Divergence flag: fires only on (large gap AND low dispersion); high dispersion or small gap → no flag.
- Consensus `None` (all sources down) → no signal, byte-identical to feature-disabled.
- `specialist_for("power_ratings_<league>")` routes to the intended scope (real taxonomy path, not hand-built).

**Steps:** tests first → implement hook + taxonomy → full suite green → commit `feat: power-ratings challenger ladder + divergence flag (WS-A2)`.

**Review focus (opus):** ladder coherence (winner/spread from one distribution), dispersion widens-not-shifts, divergence gating correct, challenger gate + taxonomy routing, no live double-count.

---

## WS-B: Evolution engine — loss-deconstruction + narration

**Files:**
- Create: `autonomy/loss_engine.py`, `scripts/run_dummy_loss_engine.py`
- Modify: the tuner (`autonomy/tuner.py`) to read a loss-priority list (annotate/order only — NOT the walk-forward gate); the dashboard council panel + readiness report to surface a "where we bleed" line; the nightly schtask installer to chain the loss engine (mirror `scripts/install_strategy_miner_task.ps1`)
- Test: `tests/test_autonomy_loss_engine.py`

**Interfaces:**
- Consumes: `autonomy/strategy_miner.py::load_settled_rows(...)`, `MinedRow` (fields: event_cluster, probability_yes, market_probability, features, result_yes, source, ticker, created_at), `_brier_edge(row)`, `_purged_split(rows, train_fraction=0.6)`, `_cluster_mean_edges(rows)`, `MIN_CLUSTERS`; `autonomy/stats.py::mean_ci95(values)`; `autonomy/taxonomy.py::specialist_for` / `grading_scope`; the verified-LLM router used by `autonomy/signals/llm_analyst.py::LlmAnalystSignal` (construct/`_get_router()`, fail-closed via its `_router_failed` flag).
- Produces: `runtime/autonomy/loss_attribution.json`; `build_loss_attribution(rows, now_iso) -> dict`; `narrate_losses(attribution, router) -> dict` (fills the `narration` field, fail-closed to `{}`); a `loss_priority(attribution) -> list[str]` the tuner consumes.

**Algorithm (deterministic, cluster-level):**
- Group settled rows by grading scope `(specialist, market_type, phase)`. For each scope, `cluster_edge = mean(_cluster_mean_edges(rows))` (positive = we beat market). Scopes with `cluster_edge < 0` and `n_clusters >= MIN_CLUSTERS` are "bleeding."
- For each bleeding scope, bucket its rows by: feature-regime terciles (per candidate feature), market_type, pre/live, horizon. Per bucket, `edge = mean(_cluster_mean_edges(bucket_rows))` with `mean_ci95` over its clusters; keep the buckets with the most-negative edge and `n_clusters >= MIN_CLUSTERS` (else `insufficient_data`).
- Artifact: per scope `{scope, n_clusters, cluster_edge, worst_buckets:[{bucket, edge, ci95:[lo,hi], n_clusters}], verdict}` + top-level `family_size` (scopes × buckets evaluated) + `narration` field.

**LLM narration (B.4):** `narrate_losses` sends the deterministic attribution to the router → per-scope "what went wrong + a hypothesis" text into `narration`. **Commentary only** — never mutates params/constants/promotions. Fail-closed: router unavailable/raises/times out → attribution still written, `narration = {}`.

**Loop wiring:** `loss_priority` returns the tunables/scopes to evaluate first; the tuner reads it to ORDER/annotate its run — it must NOT change the walk-forward CI gate or candidate/keep verdict. Dashboard/readiness show the bleeding scopes.

**Test targets:**
- Planted loss: rows seeded so one feature tercile bleeds → attribution names that bucket, cluster-level, CI present.
- Noise rows → no confident bucket (insufficient_data / no bleeding scope).
- **No-mutation:** run the script; assert only `loss_attribution.json` is written and every `autonomy/**/*.py` + `promotions.json` hash is unchanged (mirror the WS-9 SHA-256 test).
- LLM-down (router raises) → deterministic artifact still produced, `narration == {}`.
- Family-size disclosure present + accurate.
- Tuner-priority: a bleeding scope raises the matching tunable's order without changing its walk-forward verdict (assert the verdict is identical with/without the priority list).

**Steps:** tests first → implement attribution → narration (fail-closed) → tuner-priority read (non-gating) → dashboard/readiness line → schtask chain → full suite green → commit `feat: loss-deconstruction evolution engine + narration (WS-B)`.

**Review focus (opus):** no-source-mutation safety (highest priority — same as WS-9), cluster-level not per-row, family-size honesty, narration truly commentary (cannot reach params/promotions), tuner gate unchanged, LLM fail-closed.

---

## Self-review (writing-plans)

**Spec coverage:** A.1 source adapters → WS-A1; A.2 consensus core → WS-A1; A.3 challenger emission → WS-A2; A.4 divergence flag → WS-A2; A.5 fail-closed/point-in-time → WS-A1+A2 tests; A.6 tests → WS-A1/A2. B.1 attribution → WS-B; B.2 artifact → WS-B; B.3 loop wiring → WS-B; B.4 narration → WS-B; B.5 discipline/no-mutation → WS-B tests; B.6 tests → WS-B. C → WS-C. Rejected-list + data-probe appendix → Global Constraints + WS-A1 probes. No gaps.

**Placeholder scan:** no TBD/TODO; every task carries real signatures, algorithm, constants-as-named (calibration constants explicitly flagged tuner candidates, not placeholders), and concrete test targets. Probe field-paths are captured at build (the established council pattern) — a build-time probe step, not a plan placeholder.

**Type consistency:** `consensus_margin`/`ConsensusMargin` (A1) consumed verbatim in A2; `RatingSource.rating(league, team)` consistent A1→A2; `build_loss_attribution`/`narrate_losses`/`loss_priority` consistent within B; `MinedRow`/`_purged_split`/`mean_ci95`/`specialist_for` signatures match the merged code confirmed this session.
