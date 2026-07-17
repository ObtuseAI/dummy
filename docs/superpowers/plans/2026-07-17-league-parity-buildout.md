# League Parity Build-Out: NFL / NBA / NHL / NCAAF / NCAAMB to MLB-and-Crypto Depth

**Operator directive (2026-07-17, Chris):** build NHL/NFL/NBA/NCAAMB/NCAAF as
thoroughly and deeply architected as MLB and crypto are. *"If anything they
should have more data and analytics, since there are fewer games to go off
of."*

## 0. The fewer-games doctrine (governing principle)

MLB plays 2,430 regular-season games; NFL plays 272. A season of NFL
settlements can never reach the cluster counts crypto or MLB reach, so the
statistical machinery cannot be the only source of edge. The compensation is
**per-game information depth**: each game must carry an order of magnitude
more engineered, point-in-time context than an MLB game does, so the model's
prior is strong enough that fewer settlements are needed to validate it.

Concretely, for every league below:

1. **Depth over breadth** — more verified per-game inputs (participation,
   matchup, situational, environmental) rather than more parameters.
2. **Hierarchical pooling** — league-level effects estimated across teams and
   seasons (partial pooling), so 272 games/yr still yields tight estimates
   for shared structure (home-field, rest curves, weather betas).
3. **Cluster-bar realism** — promotion/calibration bars per league scale with
   settlement physics: the WS-14 ladder's CLV criterion (already instrumented,
   104 scopes) and the Wave-5 sports reliability bar (60 clusters / 6 bins)
   are the template; NFL scopes get season-aware accrual expectations, not
   crypto bars.
4. **Every claim preregistered** (Wave-7 `preregistration.py`) with a
   falsification condition, and every mined effect passes the negative-control
   battery before it is believed.

## 1. Current state (verified against deployed main, 2026-07-17)

Already shipped by the council/phenon/wave programs — the parity gap is
narrower than the roster suggests, but every league is missing its "MLB-grade"
final third:

| Capability | MLB | NFL | NBA | NHL | NCAAF | NCAAMB |
|---|---|---|---|---|---|---|
| Pre-game engine | PA-sim + structural | key-number margin kernel | pace×efficiency | bivariate Poisson + OT/SO | college kernel + talent Elo | pace model |
| Live engine | base-out RE + PA live | possession-aware OT | live diffusion | pulled-goalie λ | live grammar | live |
| Boxscore ingestion | ✔ | ✔ (WS-1) | ✔ possessions | ✔ special teams | partial | partial |
| Official-feed hydration | ✔ StatsAPI (lineups, splits, bullpen) | — | — | — | — | — |
| Player availability | ✔ injuries+scratches+fantasy | injuries only | injuries only | injuries only | injuries only | injuries only |
| Situational (rest/travel/bye) | ✔ | ✔ bye/short-week | ✔ b2b | ✔ b2b | partial | partial |
| Weather | ✔ (park/wind) | ✔ totals (WS-10) | n/a | n/a | ✔ | n/a |
| Park/venue factors | ✔ | — | — | — | — (altitude!) | — |
| Power-ratings ensemble | ✔ FPI/Elo/Massey/Colley | ✔ | ✔ BPI | ✔ | ✔ | ✔ |
| Reliability curves eligible | ✔ (60-cluster bar) | ✔ | ✔ | ✔ | ✔ | ✔ |
| CLV instrumentation | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |

## 2. Per-league workstreams

Each league gets the same five-layer stack MLB has: **official-feed hydration →
participation truth → matchup engine → situational/environment → live state**.
Bars: challenger-only, fail-closed, keyless-or-governance-gated sources,
preregistered mechanisms, negative-control-clean evidence.

### NFL (deadline: before 2026-09-10 kickoff) — the flagship

Fewest games → deepest per-game stack. Workstreams:

- **NFL-1 Participation truth.** ESPN depth charts + practice-report status
  (Wed/Thu/Fri designations are keyless on ESPN team pages/API) → per-position
  availability index. QB out ≠ WR3 out: position-weighted using the WS-6
  availability machinery. Starting-QB identity is the single largest line
  mover in sports; model it explicitly (QB-specific rating carried across
  teams, preseason snap tracking for rookie QBs).
- **NFL-2 Drive-grammar engine.** Upgrade the margin kernel's input mean from
  team-level scores to a drive-level compound model: plays/drive, EPA/play
  proxies from ESPN drive summaries (WS-1 boxscores already parse these),
  situational rates (3rd-down, red-zone TD%, turnover rates) with hierarchical
  shrinkage across the league. Output feeds the SAME key-number tilted PMF
  (spikes at 3/7/10 preserved — that kernel is already right).
- **NFL-3 Environment.** Extend WS-10 weather beyond totals: wind >15mph
  affects passing efficiency and FG make rates (spread-relevant, not just
  totals); dome/retractable flags; surface. Altitude (DEN) as venue factor.
- **NFL-4 Rest/travel matrix.** Bye (done), short-week (done), add: coast
  crossings with kickoff-time bucket (body-clock game), Thursday-after-MNF
  flag, London/international games.
- **NFL-5 Live upgrade.** Possession-aware OT model exists; add timeout state
  + two-minute-drill efficiency priors to the live win-prob, and 4th-down
  decision tendencies per coach (empirical, hierarchically pooled).
- **NFL-6 Market microstructure.** Key-number ladder coherence: the 3/7/10
  spikes imply exact relative prices across the KXNFLSPREAD ladder;
  violations are the structural-arb tier the lattice already defines — wire
  the NFL-specific checker.

### NBA (deadline: before 2026-10-20 opener)

- **NBA-1 Lineup/on-off engine.** Possession data exists (WS-2). Add per-game
  starting-lineup capture (keyless ESPN) + star on/off net-rating deltas with
  heavy shrinkage; rest-day star-sitting (load management) prediction from
  schedule structure (b2b, 3-in-4, national-TV flags).
- **NBA-2 Pace interaction model.** Current engine is team-pace ×
  team-efficiency; upgrade to matchup pace (harmonic-style interaction +
  possession-count variance by matchup style) — drives totals ladder pricing.
- **NBA-3 Garbage-time-aware live.** Live diffusion exists; blowout
  garbage-time scoring regime (bench units) biases live totals — regime-switch
  the diffusion when |lead| crosses a time-scaled threshold.
- **NBA-4 Ref/whistle totals factor.** Crew assignments are published pre-game
  (keyless); crew FT-rate tendencies as a totals feature, hierarchically
  pooled, preregistered before use.
- **NBA-5 Season-segment priors.** Early-season (roster churn) vs post-ASB vs
  tank-window (late-season motivation asymmetry) as regime features feeding
  uncertainty, not mean, until evidence earns mean shifts.

### NHL (deadline: before 2026-10-07 opener)

- **NHL-1 Goalie confirmation pipeline.** THE NHL line-mover. Morning-skate
  starter reports via ESPN game notes; model per-goalie save-quality (shrunken
  GSAx-style from boxscore shot data already ingested) with explicit
  confirmed/projected state — mirrors MLB's projected/confirmed lineup
  discipline.
- **NHL-2 Special-teams matchup depth.** PP vs PK unit rates exist (WS-3);
  add 5v5 shot-share (Corsi-proxy from boxscores) with score-state adjustment
  (trailing teams shoot more — raw shares are biased).
- **NHL-3 PDO regression engine.** Shooting% + save% luck regression — the
  classic NHL mean-reversion edge; teams riding unsustainable percentages get
  systematically mispriced by recency-biased books. Preregister the mechanism;
  it is the cleanest falsifiable NHL hypothesis.
- **NHL-4 Empty-net/late-state totals.** Pulled-goalie λ is live-correct
  (verified Wave-4 audit); extend to TOTALS ladder pricing late-game (6v5
  scoring bursts fatten the final-total tail — currently underweighted).
- **NHL-5 Schedule-density matrix.** 3-in-4s, travel legs, second-of-b2b
  goalie-swap prediction feeding NHL-1.

### NCAAF (deadline: before 2026-08-29 week 0)

- **NCAAF-1 Roster-continuity engine.** The college-specific problem: transfer
  portal + returning-production. Returning-production %, portal net-talent
  delta (247/On3 composites are scrape-restricted — use keyless proxies:
  returning starters counts from ESPN preview data; governance-gate anything
  else), blended into the talent-gap Elo prior that already exists.
- **NCAAF-2 Venue/altitude/crowd tiers.** True neutral-site handling exists;
  add venue tiers (crowd-size class), altitude (Air Force/Wyoming class
  effects), and rivalry-week variance widening (mirrors MLB rivalry work).
- **NCAAF-3 Tempo-variance kernel.** College margins have fatter tails +
  option/tempo teams change possession counts wildly; make total_sigma
  matchup-dependent (tempo interaction) instead of league-constant.
- **NCAAF-4 QB-dependency index.** Higher than NFL (no depth): starter-out =
  bigger swing, modeled via returning-production splits.
- **NCAAF-5 Ranked/letdown/lookahead spots.** Classic situational angles —
  preregister each as a falsifiable hypothesis; most will die in the battery
  (fine — that's the point of the no-edge map).

### NCAAMB (deadline: before 2026-11-03)

- **NCAAMB-1 Ratings-fusion depth.** Massey/Colley in-house solvers exist;
  add efficiency-margin ratings with schedule-strength iteration (KenPom-style
  from public boxscores — computed in-house from data we already ingest, no
  scraping) as the core prior.
- **NCAAMB-2 Three-point variance engine.** 3PA rate × opponent 3P% allowed →
  matchup-specific outcome variance (the dominant upset mechanism); feeds
  uncertainty and total_sigma.
- **NCAAMB-3 Home-court tiers.** Venue effects vary 2-8 points in college;
  hierarchical per-venue estimates with conference pooling.
- **NCAAMB-4 Conference-tournament/neutral handling** + March mode (single-elim
  variance regime, seed-line market biases — preregister the classic ones).
- **NCAAMB-5 Early-season information ramp.** November ratings are noise;
  explicit information-quantity curve controlling uncertainty until ~8 games.

## 3. Cross-league shared infrastructure (build once)

- **XL-1 Official-feed adapters framework.** Generalize the StatsAPI pattern
  (nullable fields, presence tracking, projected/confirmed states) into a
  per-league `LeagueContext` protocol so NFL-1/NBA-1/NHL-1 hydrators share
  harness, caching, and fail-closed discipline.
- **XL-2 Participation truth store.** One typed availability book across
  leagues (position-weighted, confirmed/projected/out states) extending the
  WS-6 machinery; consumed by every engine identically.
- **XL-3 Hierarchical shrinkage library.** Partial-pooling estimators
  (team|league, player|position|team, venue|conference) used by all
  workstreams — the statistical heart of the fewer-games doctrine.
- **XL-4 Negative-control + preregistration gates in CI for every new
  league mechanism** (Wave-7 machinery, made mandatory for this program).
- **XL-5 League-aware promotion expectations.** Readiness surfaces
  days-to-eligibility using each league's settlement calendar so a 300-cluster
  bar renders as honest dates, not false hope.

## 4. Sequencing and effort

Priority = season proximity × market volume: **NCAAF → NFL → NHL → NBA →
NCAAMB.** NCAAF/NFL share football infrastructure (build football first,
port). Each league lands as one wave (5 workstreams + shared XL pieces as
needed), branch-first, adversarially reviewed, suite-green — the same
discipline as waves 1-7. Rough order: XL-1/2/3 + NCAAF/NFL (August), NHL/NBA
(September), NCAAMB (October).

## 5. What is NOT in scope

- No scraping of ToS-restricted sources (247/On3 composites, PFF, Synergy);
  anything non-keyless routes through the governance slot like the Odds API.
- No new execution surface — everything ships challenger-only into the
  existing lattice/promotion machinery.
- No live-capital changes; promotion remains evidence-gated per WS-14.
