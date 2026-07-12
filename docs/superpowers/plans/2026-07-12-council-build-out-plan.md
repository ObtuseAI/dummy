# Council Build-Out Plan — Every Sport, Every Layer

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Each Workstream below is one PR-sized unit: implement → full suite green → adversarial opus review → fix findings → re-verify → merge (standing auto-merge authorization applies to green PRs). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the council of specialists: custom-tailored engines for NBA/NHL/NCAAF/NCAAMB, the MLB Phase-2 deepening, the 3×3 conviction lattice + coherence engine, CLV grading, the player/rookie/mismatch layer, the situational engine, the trust surface, the propose-then-promote tuner, NFL/NCAAF weather, crypto CLV — everything specified in `docs/superpowers/specs/2026-07-12-council-of-specialists-design.md` (read it FIRST; sections cited throughout).

**Architecture:** In-process council (`autonomy/specialists/`), challenger-only signals graded by contested Brier, fail-closed at every feed, season auto-gated (`autonomy/specialists/seasons.py`). Specialists forecast; the core keeps sole capital authority. NOTHING in this plan touches allocator/executor/risk_brain/live-trading authority.

**Tech stack:** Python 3.14, httpx (keyless public GETs only), pytest (~4,930 tests, CI = windows-latest ~8-10 min), SQLite ledger (`runtime/autonomy/ledger.db`).

## Global Constraints (bind every task)

- Every new signal sets `features["challenger_only"] = True`; `forecaster.fuse()` excludes challengers from execution (autonomy/forecaster.py:45).
- Fail-closed: missing feed / thin data / degenerate horizon → return `None`; a run without the feature is byte-identical.
- Point-in-time honesty: models `update()` ONLY from `game.status == "post"` rows; live data never enters learning before settlement.
- When a distribution changes under a stable source name, add a `*_model_version` feature so grading regimes segment (precedent: `margin_model_version="nfl_key_number_kernel_v1"`).
- Hard, verifiable situational states may apply bounded mean adjustments; narrative-soft states widen uncertainty ONLY (spec §8b.3).
- New constants are static + auditable in code; auto-fitting goes through the propose-then-promote tuner (WS-9), never silently.
- Season gate: warmup paths check `self.seasons.active(league)`; `EspnClient.games()` SWALLOWS fetch errors — anything needing to distinguish feed-down from offseason must use `games_or_raise()` (this exact trap shipped a FIX_FIRST once).
- Integration-test through the REAL feature-mapping layer, not hand-built dicts (`swing_setup` veto was dead in production because unit tests used wrong key names — never again).
- Statistical evidence over correlated emissions uses per-event-cluster means, never per-row CIs; any mined/graded artifact discloses family size (`rules_tested`, `expected_false_positives`).
- Git: branch per workstream off fresh `origin/main`; commit messages end with the Claude co-author line; PR bodies list review verdict + testing.

## Shipped foundation (do not rebuild — wrap/extend)

| Piece | Where |
|---|---|
| Specialist protocol/registry/factory, season gate | `autonomy/specialists/{base,factory,seasons,mlb,team_leagues,crypto}.py` |
| MLB stack: PA sim, L/R, bullpen, rivalry, weather, injuries, live winner/total/spread, YRFI | `autonomy/sports/{baseball,mlb_pa_sim,mlb_matchups,ballpark_weather,injuries}.py`, `autonomy/signals/sports_intelligence.py` (`BaseballIntelligenceSignal`) |
| NFL key-number kernel + all-league spread parsing | `autonomy/sports/nfl_margin.py`, `_TEAM_SPREAD_SERIES` + spread branch in `sports_intelligence.py` |
| Generic team EWMAs (all 5 leagues) | `autonomy/sports/team_scores.py` (`TeamScoreModel`, `LEAGUE_SCORE_CONFIGS`) |
| Elo (all leagues, pitcher-aware MLB) | `autonomy/signals/sports_elo.py`, `autonomy/sports/elo.py` |
| Sportsbook consensus book + live ESPN-summary book | `autonomy/signals/sportsbook.py`, `autonomy/live_odds.py` |
| Mispricing triangulation + opportunist + monitor | `autonomy/{mispricing,opportunist,mispricing_monitor}.py`, `scripts/run_dummy_mispricing_monitor.py` |
| Crypto: champion lognormal, EWMA-tail, regime/technical/DVOL challengers, macro, equities/ETF, structure+swing, DVOL implied book, events, Kraken failover | `autonomy/signals/crypto_*.py`, `autonomy/{crypto_implied_book,crypto_events,crypto_structure}.py` |
| Strategy miner (walk-forward, cluster-honest) | `autonomy/strategy_miner.py`, `scripts/run_dummy_strategy_miner.py` |
| ESPN adapter (7 leagues, college per-day fallback, `games_or_raise`) | `autonomy/sports/espn.py` |

Kalshi series verified live 2026-07-12: `KX{NFL,NBA,NHL,NCAAF,NCAAMB}{GAME,TOTAL,SPREAD}` all exist; "alt lines" are multi-strike ladders INSIDE the SPREAD/TOTAL series (MLB spreads 1.5/2.5/3.5 per side; totals 2.5–9.5). Spread `floor_strike` arrives as the X.5 line itself.

---

## WS-1: Boxscore stat pipeline (foundation for NBA/NHL/mismatch layers)

**Why first:** pace (NBA), special teams (NHL), and unit mismatches (NFL) all need per-game team stats the scoreboard doesn't carry. One shared fetch/persist layer, built once.

**Files:** Create `autonomy/sports/boxscores.py`; Test `tests/test_autonomy_boxscores.py`.

**Interfaces (produces):**
```python
@dataclass(frozen=True)
class TeamBoxscore:
    game_id: str; league: str; team: str; opponent: str; is_home: bool
    stats: dict[str, float]   # flat, per-league keys listed below

def fetch_summary(league: str, event_id: str) -> dict          # keyless GET, raises on failure
def parse_team_boxscores(league: str, summary: dict) -> list[TeamBoxscore]  # [] when absent
class BoxscoreStore:                                            # JSON per league, idempotent by game_id
    def __init__(self, league: str, path: Path | None = None)   # default runtime/autonomy/boxscores_{league}.json
    def ingest(self, boxscores: list[TeamBoxscore]) -> int
    def recent(self, team: str, n: int = 20) -> list[TeamBoxscore]
```
- Summary endpoint: `https://site.api.espn.com/apis/site/v2/sports/{sport}/{esp_league}/summary?event={id}` (same host/pattern as `autonomy/live_odds.py::default_fetch_summary` — reuse its shape). Boxscore lives under `payload["boxscore"]["teams"][i]["statistics"]` as `{name, displayValue}` rows.
- **PROBE AT BUILD TIME** (mandatory first step): fetch one completed game's summary per league; record the exact statistic `name` keys. Expected per league (verify, don't trust):
  - NBA: `fieldGoalsAttempted`, `freeThrowsAttempted`, `offensiveRebounds`, `turnovers`, `points` → possessions = FGA − ORB + TO + 0.44·FTA.
  - NHL: `powerPlayGoals`, `powerPlayOpportunities`, `shotsTotal` (PK% derives from opponent's PP rows).
  - NFL: `netPassingYards`, `rushingYards`, `totalYards`, `turnovers`, plays if present.
- Fetch budget: warmup ingests boxscores ONLY for games newly seen as `post` (≤ ~16/day/league); wrap each fetch in try/except-continue; store is idempotent.
- Retention: cap per-team history at 30 entries (deque semantics on ingest).

**Steps:**
- [ ] Probe one real summary per league; paste the observed stat-key names into module constants (`_STAT_KEYS[league]`) with a comment naming the probed event id/date.
- [ ] Write failing tests from a captured fixture payload (commit a trimmed JSON fixture under `tests/fixtures/`): parse → expected stats dict; absent boxscore → `[]`; store idempotency; retention cap.
- [ ] Implement; tests green; commit.

**Acceptance:** parse fixtures hand-checked; zero network in tests; `python -m pytest tests/test_autonomy_boxscores.py -q` green.

---

## WS-2: NBA engine (spec §5.2) — pace × efficiency, heteroskedastic, rest-aware

**Files:** Create `autonomy/sports/nba_model.py`; Modify `autonomy/signals/sports_intelligence.py` (NBA branch mirroring the NFL kernel hook); Test `tests/test_autonomy_nba_model.py`.

**Model (produces `NbaModel`):**
- State per team (EWMA α=0.10, persisted `runtime/autonomy/nba_pace_model.json`): `pace` (possessions/game from WS-1), `ortg` (pts per 100 poss), `drtg` (opp pts per 100 poss). Cold prior: pace 99.5, ortg/drtg 114.0 (league scoring environment; cold teams regress like `TeamScoreModel._metric`, weight = min(0.85, games/25)).
- Matchup: `expected_pace = (pace_home + pace_away)/2`; `eff_home = (ortg_home + drtg_away)/2`, mirrored for away; `expected_home = expected_pace · eff_home/100 + home_edge/2` (home_edge 3.0 pts split as today); totals mean = sum.
- **Heteroskedastic sigmas:** `total_sigma = 19.5 · sqrt(expected_pace/99.5)` and `margin_sigma = 11.5 · sqrt(expected_pace/99.5)` (calibration targets for the tuner; document as such). Winner = Φ(margin/margin_sigma); spread rung = P(margin > k.5) via the same normal — winner and ladder share one distribution (lattice column coherent).
- **Garbage-time cap:** when ingesting a final, clamp margin influence: effective margin = sign(m)·min(|m|, 25) before updating ortg/drtg (blowout tails lie).
- **Rest engine (hard states, bounded):** from the schedule (games already fetched per day — track each team's last game date in model state): b2b → subject −1.5 pts; 3-in-4 → −1.0 (stack caps at −2.0); rest ≥ 3 days → +0.5. Constants in a module-level table with citations comment. Both features logged (`rest_days_home/away`, `rest_adjustment`).
- Fallback: if WS-1 store has < 5 games for either team, fall back to `TeamScoreModel` prediction wholesale (feature `nba_model_fallback=true`) — never half-blend.
- Signal integration mirrors the NFL hook exactly: `parsed.sport == "nba"` + winner/spread/total → `NbaModel` when warm; `margin_model_version="nba_pace_efficiency_v1"`.
- Live Brownian diffusion (in-play): `P(home wins | lead L, t_remaining) = Φ((L + drift·t)/ (sigma_live·sqrt(t)))`, `sigma_live = margin_sigma/sqrt(48 min)`, drift = expected_margin/48 per minute; gate exactly like MLB live (`game.status == "in"`, `current_period` present; ESPN NBA scoreboard carries period + clock — probe the clock field at build). Live totals/spread analogous. New sources `nba_live_winner`/`nba_live_total`/`nba_live_spread`.

**Key tests (write first, hand-computed):** pace math from fixed boxscores; heteroskedastic sigma ratio (pace 105 vs 94); garbage-time clamp (35-pt final updates as 25); b2b adjustment applied and logged; fallback below 5 games byte-identical to TeamScoreModel; winner==P(margin>0) consistency with the 0.5 rung; live Brownian: L=10, 12 min left, drift 0 → Φ(10/(σ_live·√12)) hand-value; settlement invariant (update refuses `status != "post"`).

- [ ] Steps: probe NBA summary clock/period fields → fixtures → failing tests → implement model → signal hook → live branch → suite → commit.

---

## WS-3: NHL engine (spec §5.3) — bivariate Poisson + OT/SO + goalie identity

**Files:** Create `autonomy/sports/nhl_model.py`; Modify `sports_intelligence.py` (NHL hook); Test `tests/test_autonomy_nhl_model.py`.

**Model:**
- Team goal-rate EWMAs (α=0.10, prior 3.05 GF/GA): `lambda_home = (gf_home + ga_away)/2 + home_edge/2` (home_edge 0.18 goals), mirrored away. Independent Poissons (bivariate correlation term deferred; document).
- **Regulation matrix:** P(reg score h,a) = Pois(λ_h)(h)·Pois(λ_a)(a) truncated at 12 (reuse `poisson_pmf` from `autonomy/sports/baseball.py` if exported, else local).
- **OT/SO branch:** `P(win) = P(reg win) + P(reg tie) · p_ot`, where `p_ot = 0.5 + 0.5·(win_prob_reg_normalized − 0.5)·OT_STRENGTH_TILT`, `OT_STRENGTH_TILT = 0.30` (near-coin, slight strength lean; auditable constant). Kalshi NHL winner includes OT/SO — VERIFY the market rules text at build (fetch one KXNHLGAME market's `rules_primary`).
- **Spread (puck line ±1.5):** covering −1.5 requires winning by ≥2 IN REGULATION or OT? — Kalshi settles on final score incl. OT (OT adds exactly 1 goal margin). P(home covers 1.5) = P(reg margin ≥ 2) + P(reg tie)·0 (OT win = margin 1) — VERIFY settlement source treats SO as 1-goal margin (it does officially; assert in rules probe). Totals: P(total > k.5) from the regulation matrix + P(tie)·P(OT goal counts?) — SO goals don't count toward totals; OT goal adds 1: P(total = reg_total + 1 | reg tie, OT goal scored before SO). Approximate: OT resolves ~70% pre-shootout → totals distribution = reg total + Bernoulli(0.7)·1 on ties. Constant auditable.
- **Goalie layer:** per-goalie save% EWMA from boxscores (WS-1 NHL keys include goalie rows — probe `boxscore["players"]` for saves/shotsAgainst); starter identity pre-game: probe ESPN NHL scoreboard `competitions[].competitors[].probables` — if absent keyless, goalie layer degrades to team GA EWMA only (fail-closed, feature `goalie_known=false`, uncertainty +0.03). Known elite/backup delta shifts λ_opponent by ±0.25 max.
- **Special teams mismatch:** PP% and PK% EWMAs from WS-1; mismatch feature = (PP_home − (1−PK_away)) − league mean; logged for the miner, shifts λ by ≤ 0.15 (bounded).
- **Rookie goalie flag:** roster experience probe; if unavailable keyless → flag only when goalie has < 10 tracked starts in our own store (self-derived rookie proxy; honest).
- Live: time-scaled Poisson remaining (like MLB `remaining_innings` → remaining minutes/60); **pulled-goalie inflation**: final 3 minutes with deficit ≤ 2 → trailing team λ ×1.8, leading team empty-net λ ×2.5 (constants auditable; only affects live totals/spread). Sources `nhl_live_*`.
- `margin_model_version="nhl_bipoisson_ot_v1"`.

**Key tests:** Poisson matrix vs hand-computed 2×2 cell; OT branch: λ equal → P(win)=0.5 exactly; puck-line: P(cover 1.5) < P(win) always; totals OT bump: P(total > reg mass boundary) increases on tie mass; goalie-unknown widens uncertainty not mean; pulled-goalie only in live+final-3; settlement invariant.

- [ ] Steps: rules + probables + boxscore probes → fixtures → tests → model → hook → live → commit.

---

## WS-4: NCAAF + NCAAMB engines (spec §5.4) — college reparameterizations

**Files:** Create `autonomy/sports/college.py`; Modify `sports_intelligence.py` (route ncaaf → college-NFL-kernel, ncaamb → college-NBA-model); Tests `tests/test_autonomy_college.py`.

- **NCAAF:** reuse `nfl_margin.margin_distribution` machinery with a COLLEGE base PMF (wider: key numbers 3/7 present but ~60% of NFL spike sharpness; mass extends to 60; encode a second auditable table `BASE_ABS_MARGIN_PMF_COLLEGE`). Expected margin from TeamScoreModel EWMAs + **talent-gap regression**: when `sample_games < 6` early-season, blend margin 50% toward prior-season Elo differential (`autonomy/sports/elo.py` state exists for ncaaf) — exact blend: `margin = w·ewma_margin + (1−w)·elo_margin_pts` where `elo_margin_pts = elo_diff/25.0`, `w = min(1.0, games/6)`. Home edge 3.0; **neutral-site flag**: ESPN event `competitions[].neutralSite` (probe; if true, home_edge=0, feature `neutral_site=true`).
- **NCAAMB:** NBA model class parameterized: prior pace 68, ortg/drtg 105, total_sigma base 17.0, margin_sigma base 10.5, home edge 3.5; 360+ teams fine (JSON store); tournament/neutral via same neutralSite flag; **freshman impact** deferred to WS-6 rookie layer (college rosters carry class year — probe).
- Both: `margin_model_version` = `ncaaf_college_kernel_v1` / `ncaamb_pace_efficiency_v1`.

**Key tests:** college PMF normalizes + spikes shallower than NFL (ratio assert); talent-gap blend at games=0 uses full Elo, at ≥6 full EWMA; neutral site zeroes home edge; ncaamb cold prior totals ≈ 141±sigma sanity.

- [ ] Steps: neutralSite + class-year probes → tables → tests → implement → hook → commit.

---

## WS-5: 3×3 conviction lattice + coherence engine (spec §3.0/§3.1)

**Files:** Create `autonomy/coherence.py`; Modify `autonomy/mispricing_monitor.py` (lattice section in report) + `scripts/run_dummy_mispricing_monitor.py` (assemble per-game groups); Test `tests/test_autonomy_coherence.py`.

**Interfaces:**
```python
@dataclass(frozen=True)
class LatticeCell:
    family: str            # "winner" | "spread" | "total"
    ticker: str; line: float | None
    model_prob: float | None; book_prob: float | None; kalshi_prob: float | None

@dataclass(frozen=True)
class GameLattice:
    game_key: str          # f"{sport}:{date}:{away}@{home}"
    sport: str
    cells: list[LatticeCell]

def ladder_violations(cells, family) -> list[dict]      # Kalshi monotonicity breaks beyond fee band
def cross_family_incoherence(lattice) -> list[dict]     # winner-implied vs spread-implied P(win) gaps
def lattice_conviction(lattice, assessments) -> dict    # cross-cell confirmation score

FEE_BAND = 0.03  # rung-gap must exceed combined fee/spread slack to count
```
- **Grouping:** monitor pass groups scanned markets by `parse_sports_contract` (sport, date, competitors) → one `GameLattice` per game; cells populated from the SAME `forecast_fn`/`book_fn` values the sweep already computed (no second fetch).
- **Ladder check (needs NO model):** within Kalshi's own quotes, for spread rungs k1<k2 of the same subject: require `P_kalshi(cover k1) ≥ P_kalshi(cover k2) − FEE_BAND`; violations emit `{game_key, family, rungs, gap, tier:"structural"}`.
- **Cross-family (needs model distribution):** each sport's engine exposes the winner prob implied at the 0.5 rung; compare Kalshi winner vs Kalshi spread-implied winner mapped through the MODEL's own distribution shape: `implied_win = model_win − model_cover(k) + kalshi_cover(k)` (first-order transport; document approximation). Gap > 2·FEE_BAND → incoherence row.
- **Conviction tiers (report + opportunist):** `structural` (ladder violation) > `cross_confirmed` (same-direction edge in ≥2 families with book agreement in both) > `model+book` > `model_only`. Extend `OpportunistEngine.observe` input: assessments gain optional `conviction_tier`; anchor threshold drops 0.02 for `cross_confirmed`, 0.04 for `structural` (constants top-of-file).
- Report: `"lattices": [...]` capped at 20 games, `"structural_count"`, `"cross_confirmed_count"`. Dashboard: extend `renderMispricing` with the two counts (small).

**Key tests:** synthetic lattice with planted rung inversion → violation flagged, fee-band suppresses small gaps; cross-family gap arithmetic hand-computed; conviction tier ordering; monitor integration: two fake markets same game produce one lattice; empty/partial lattices fail closed (no cells → no rows).

- [ ] Steps: tests-first on pure functions → monitor wiring → dashboard count → commit.

---

## WS-6: Player/rookie/matchup layer (spec §8b.2)

**Files:** Create `autonomy/sports/players.py`; Modify each engine's uncertainty path (NBA/NHL/NFL/college hooks) + `BaseballIntelligenceSignal` untouched (MLB injuries shipped); Test `tests/test_autonomy_players.py`.

- **Injuries all leagues:** generalize `autonomy/sports/injuries.py` pattern: `InjuryBook(league)` — endpoint `.../{sport}/{league}/injuries` (VERIFY per league at build; MLB verified; NFL/NBA/NHL expected same shape; college may 404 → book stays empty, fail-closed).
- **Position weights (hard availability deltas, bounded):** table `POSITION_IMPACT[league] = {position_group: points}` — NFL: QB Out −4.5 subject pts (THE special case), RB/WR −0.7, OL −0.5; NBA: player Out −1.8 default, scaled ×2 when our own store shows him top-2 in team minutes (WS-1 boxscore players); NHL: goalie handled in WS-3, skater −0.3; college halves of pro values. Status source: injuries feed `status in {"Out","Doubtful"}` = hard (mean adjust allowed); `Questionable/Day-To-Day` = soft (uncertainty widen only, +0.02 each capped +0.08). Every adjustment logged in features.
- **Rookie impacts:** roster endpoint probe (`.../teams/{id}/roster` — `experience.years == 0`); if keyless-verified: `rookie_start` flag for QB (NFL depth position 1 probe) and goalie; else self-derived proxy: first-N-appearances in our own stores (< 5 tracked games) → `rookie_proxy=true`. Effect: uncertainty +0.04 (NEVER mean), feature logged for the miner to grade.
- **Mismatch finder:** from WS-1 stats — NFL `pass_off_ewma vs opp pass_def_ewma` z-gap; NBA pace gap + rest gap; NHL special-teams gap (WS-3). Output bounded feature `mismatch_score ∈ [−1,1]` per game, logged on every signal for that game; shifts mean by ≤ 0.3·league_point_scale ONLY when |score| > 0.5 (constants table).

**Key tests:** QB-Out shifts NFL margin by exactly −4.5 with feature logged; Questionable widens only (mean byte-identical); rookie flag widens only; injuries feed absent → all zero effects; mismatch bounded and symmetric.

- [ ] Steps: endpoint probes per league (record results in module comment) → tests → implement → wire per engine → commit.

---

## WS-7: Situational engine (spec §8b.3)

**Files:** Create `autonomy/sports/situations.py`; wire into engines' expected-margin/uncertainty; Test `tests/test_autonomy_situations.py`.

- **Hard states (bounded mean adjust, per-league constants table):** rest differential (from each model's last-game-date state, shipped in WS-2 for NBA; generalize the tracker here for all leagues): NFL bye (+1.0) / Thursday short week (−1.5 road only); NHL b2b (−0.8, goalie-backup proxy); NBA covered in WS-2 (this module owns the shared tracker; WS-2 migrates to it if built first — coordinate: build the tracker HERE, WS-2 consumes).
- **Playoff context:** standings endpoint probe (`.../standings`? if not keyless, derive from our own results store: games-behind computation from tracked wins). States: `clinched` / `eliminated` late-season (uncertainty +0.05 both — motivation asymmetry is real but direction is narrative → widen only, deliberately conservative), `must_win` flag logged for the miner.
- **Suspensions:** injuries feed rows with `type/status` containing "suspension" → hard Out (WS-6 path handles impact).
- **Trades/coaching (soft, widen-only):** transactions/news endpoints are NOT reliably keyless — PROBE; if unavailable, proxy: roster-hash drift between cycles from WS-6 roster fetches (a large diff mid-season = roster event) → uncertainty +0.04, `roster_event=true` feature. NEVER a mean shift. Document honestly what's proxied.
- All states → features on every affected signal; the miner grades which situations pay (that loop already exists).

**Key tests:** bye/short-week constants applied on synthetic schedule; widen-only invariants (mean byte-identical for every soft state); no feeds → all-zero; feature logging complete.

- [ ] Steps: tracker → probes → tests → implement → wire → commit.

---

## WS-8: CLV grading (spec §3.2) + trust surface (spec §3.3)

**Files:** Create `autonomy/clv.py`; Modify `autonomy/mispricing_monitor.py` (book snapshot persistence + entry rows), `autonomy/backtest.py` (phase-keyed contested Brier), `autonomy/dashboard.py` (CLV per specialist in council/mispricing panel); Tests `tests/test_autonomy_clv.py`.

- **Capture:** every monitor pass appends `{ticker, ts, book_prob, kalshi_mid, close_time}` per assessed market to `runtime/autonomy/book_tape.jsonl` (cap: skip if unchanged from last row for that ticker; rotate at 50MB). The row nearest `close_time` (within 30 min) = the CLOSE.
- **Grading:** for every opportunist strike + shortlist entry (already in monitor report — persist entries to `runtime/autonomy/paper_entries.jsonl` at emission): `clv_bps = 10_000 · side_sign · (close_book_prob − entry_kalshi_prob)`. Nightly pass (extend `scripts/run_dummy_strategy_miner.py` or new `scripts/run_dummy_clv_grader.py` on the same schtask): join entries × tape closes → `runtime/autonomy/clv_report.json` aggregated per (specialist, market_type) with per-event-cluster CIs (REUSE `autonomy/stats.mean_ci95` + cluster rule).
- **Trust surface:** `autonomy/backtest.py` contested-Brier trackers gain a `phase` key: source features carry `live` bool already (`mlb_live_*` sources are distinct names — simplest correct: PHASE IS ALREADY ENCODED in source names for live; formalize by mapping source → (specialist, market_type, phase) in one table `SOURCE_TAXONOMY` in `autonomy/coherence.py` or new `autonomy/taxonomy.py`); retro/backtest reports add the phase-keyed breakdown. CLV is EVIDENCE (report), contested Brier stays the promotion gate — restate in docstrings.

**Key tests:** tape dedup; close selection nearest within window, else no grade (fail-closed); clv sign for YES vs NO side hand-computed; cluster CI on synthetic entries; taxonomy covers every registered source name (test iterates `build_brain(SHADOW)` registry and asserts mapping completeness — catches future source additions).

- [ ] Steps: tape → entries persistence → grader → taxonomy → backtest keying → dashboard field → commit.

---

## WS-9: Propose-then-promote tuner (spec §3.4)

**Files:** Create `autonomy/tuner.py` + `scripts/run_dummy_tuner.py` (+ schtask installer mirroring `install_strategy_miner_task.ps1`, nightly 09:45); Test `tests/test_autonomy_tuner.py`.

- **Tunable registry:** explicit list — `TUNABLES = [{"name": "nba_total_sigma_base", "current": 19.5, "grid": [17.5,18.5,19.5,20.5,21.5], "applies_to": "nba", "market_type": "total"}, ...]` for each engine's sigma/edge constants (NFL PMF stays fixed; only scalars tune).
- **Fit:** walk-forward on settled signal rows (REUSE `autonomy/strategy_miner.load_settled_rows` + `_purged_split`): re-price each settled forecast under each grid value (engines expose pure repricing helpers — add `reprice(features, constant_override)` static methods where needed; where features lack inputs to reprice, that tunable is skipped honestly), compare cluster-mean Brier train→test.
- **Artifact only:** `runtime/autonomy/tuning_proposals.json`: per tunable {current, best, train_delta, test_delta, test_ci95, n_clusters, verdict candidate/keep}. NEVER writes constants. Promotion = human edits the constant in a PR citing the artifact.

**Key tests:** planted miscalibration (synthetic rows generated at sigma 22 while current constant 19.5) → proposal finds 21.5±1 out-of-sample; noise → keep; artifact discloses family size; no source file mutated (assert file hashes unchanged after run).

- [ ] Steps: registry → repricing helpers → fit loop → artifact → schtask → commit.

---

## WS-10: NFL/NCAAF outdoor weather (spec §5.1)

**Files:** Create `autonomy/sports/football_weather.py` (+ static stadium table); Modify NFL/college hooks (totals only); Test `tests/test_autonomy_football_weather.py`.

- Static table: 32 NFL stadiums {team_abbr: (lat, lon, dome: bool)} — 8 domes/retractables get `dome=True` (no adjustment). College: top-40 programs only (honest coverage note; others unadjusted).
- Reuse `autonomy/sports/ballpark_weather.py` Open-Meteo fetch pattern (hourly forecast at kickoff hour). Adjustments (totals mean only, bounded): wind ≥ 20 mph → −2.5 pts; 15–20 → −1.5; temp ≤ 15°F → −1.5; heavy precip code → −1.0; stack cap −4.0. Features log raw wind/temp/precip + adjustment.
- Winner/spread untouched (wind hurts both offenses).

**Key tests:** dome bypass; wind tiers; stack cap; fetch failure → zero adjustment byte-identical; feature logging.

- [ ] Steps: table → tests → implement → hook → commit.

---

## WS-11: MLB Phase 2 (spec §4) — park factors, live base-out, TTO, rest

**Files:** Modify `autonomy/sports/baseball.py` (park factor on expected runs), `autonomy/signals/sports_intelligence.py` (live base-out consumption), Create `autonomy/sports/mlb_parks.py` (static table) + extend live parsing in `autonomy/live_odds.py` or new helper for `plays`; Tests extend `tests/test_autonomy_sports_intelligence.py` + `tests/test_autonomy_mlb_parks.py`.

- **Park factors:** static 30-park run-factor table (COL 1.28 … SD/SF ~0.90; encode full table with source comment) applied multiplicatively to expected_total_runs for totals/YRFI only (winner margin unaffected — both teams share the park); feature `park_factor`.
- **Live base-out:** game summary `plays`/`situation` carries `onFirst/onSecond/onThird`, `outs` (PROBE exact keys on a live game). Map (base_state, outs) → expected-runs-rest-of-inning table (static RE24-style 8×3 table, auditable) → adjust `live_total_probability`'s remaining-mean for the CURRENT inning only; feature `base_out_state`.
- **TTO fatigue:** live starter's times-through-order from plays count vs lineup position (batters faced //9): TTO≥3 → remaining-inning run rate ×1.12 while starter still in (pitcher-change detection from plays; if undetectable, apply only innings 5–6 as proxy — document).
- **Rest/travel:** day-game-after-night-game (start hour < 14 local after previous 19+ start, same teams' schedule from our stores) → uncertainty +0.02 (soft; direction narrative).
- `model_version` bump on BaseballRunModel outputs: `mlb_runs_v2_parks`.

**Key tests:** COL vs SD totals delta matches table; base-out RE hand-checked (bases loaded 0 out ≈ 2.3 vs empty 2 out ≈ 0.10); TTO multiplier windows; park factor absent for winner; live plays fixture parse.

- [ ] Steps: parks table → RE24 table → plays probe/fixture → tests → implement → commit.

---

## WS-12: Crypto completion — CLV + smile slot doc

- Crypto entries already flow through the WS-8 tape/grader (book_fn = DVOL implied): verify crypto rows appear in `clv_report.json`; add crypto close semantics (book at close = last DVOL-implied within 30 min of market close).
- Deribit option-chain smile book: DO NOT BUILD; add the governance-gated slot note to `autonomy/crypto_implied_book.py` docstring if not already present (it is — verify only).
- [ ] One test: crypto entry graded end-to-end through WS-8 fixtures.

---

## WS-13: Council dashboard panel + docs

**Files:** Modify `autonomy/dashboard.py` (+ embedded JS), README, `docs/AUTONOMY.md`, `docs/SPORTS_INTELLIGENCE.md`.
- Council panel: one row per specialist from `SpecialistRegistry.health_report()` + season snapshot (`SeasonMonitor.snapshot()`): status (ok/dormant/cold), in_season, model games seen, settled n + contested Brier (from taxonomy-keyed backtest summary), CLV (WS-8), open opportunities count.
- Docs: engines table, lattice explanation, season gating, CLV, tuner — mirror what shipped.
- [ ] Steps: state assembly → JS render → docs sweep → screenshot refresh (playwright route-interception recipe in scratchpad/shoot.py pattern) → commit.

---

## Sequencing & deadlines

```
WS-1 (boxscores) ──► WS-2 (NBA) ──► WS-4 (NCAAMB half)
        │                └────────► WS-3 (NHL)
        └──► WS-6 (players/mismatch)
WS-5 (lattice) — independent, high value NOW (MLB mid-season live validation)
WS-7 (situations) after WS-6 tracker
WS-8 (CLV/trust) — independent, start early (tape accrues history)
WS-9 (tuner) after ≥2 engines shipped
WS-10 (weather) with WS-4 NCAAF or standalone
WS-11 (MLB P2) — independent, in-season NOW
WS-12/13 last
```
**Season deadlines:** NFL/NCAAF complete before ~Aug 6 (first preseason); NBA/NHL before ~Sep 20 (camps/preseason); NCAAMB before Nov 1. MLB (WS-11, WS-5, WS-8) validates live IMMEDIATELY — prioritize those three alongside WS-1/2.

## Validation program (every workstream)

1. Hand-computed fixture tests written FIRST; zero network in tests; probes captured as committed fixtures.
2. Full suite green locally (exit code 0 — the summary line gets clipped by faulthandler dumps; trust the exit code) + CI green.
3. Adversarial opus review per PR (the review loop has caught a real blocker or Major in 4 of 8 council PRs — it is not optional): findings fixed, re-verified, verdict quoted in PR body.
4. Paper validation: engines emit challenger-only into the shadow brain from merge day; per-market-type contested-Brier accrues; NO promotion in this plan's scope.
5. Byte-identical checks wherever a feature can be absent (the doctrine test shape: build output with feed present-but-empty vs feature-disabled and assert equality).

## Data-probe appendix (verify at build, record results in module comments)

| Probe | Needed by | Expected |
|---|---|---|
| Summary boxscore stat keys per league | WS-1 | `boxscore.teams[].statistics[].name` |
| NBA scoreboard live clock field | WS-2 | `status.displayClock` + `period` |
| NHL probables (goalies) on scoreboard/summary | WS-3 | may be absent → degrade documented |
| KXNHLGAME rules_primary (OT/SO inclusion) | WS-3 | includes OT/SO |
| ESPN `neutralSite` flag | WS-4 | `competitions[].neutralSite` bool |
| Roster endpoint + experience/class year per league | WS-6 | `.../teams/{id}/roster` |
| Injuries endpoint per league (non-MLB) | WS-6 | same shape as MLB |
| Standings endpoint keyless | WS-7 | may need own-store derivation |
| MLB summary `situation` base-out keys | WS-11 | `onFirst/onSecond/onThird`, `outs` |

## Handoff state (as of this commit)

- Merged council PRs: #38 (skeleton+UFC/F1), #39 (crypto DVOL/failover/events), #40 (structure+miner), #41 (equities+spec v1.1), #42 (season gating+lattice spec), #43 (NFL kernel+spread ladders). Main green, ~4,930 tests.
- Live paper systems: shadow predator, paper twin, mispricing monitor (2-min), strategy miner (nightly) — all challenger/paper, zero capital authority changes throughout.
- Spec: `docs/superpowers/specs/2026-07-12-council-of-specialists-design.md` (§3.0 lattice, §8b directives) is the authority; this plan implements it.
