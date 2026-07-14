# Multi-sport intelligence and recursive simulation lab

Dummy now maintains a public-read-only sports research stack across MLB, NFL,
NCAAF, NHL, NBA, and NCAAB (UFC and Formula One retired 2026-07-12; their
markets are no longer scanned or forecast). It produces paper picks and
settlement evidence; the new challengers are explicitly excluded from the
execution ensemble until their own league and market-type scope passes the
forward promotion gates.

Every ten-minute cycle now freezes two distinct paper lanes. `policy` records
only predictions that clear the normal sample, price, uncertainty, and edge
gates. `coverage_probe` forces a one-contract quote-simulated decision for
every real listed, signal-compatible designated market so cold models, losing
types, and abstention gates produce inspectable forward evidence. Every forced
trade includes a plain-language explanation and is permanently excluded from
champion selection, readiness, execution, and capital evidence. If a designated
type has no real model-compatible listing, the report records an explicit gap;
Dummy never fabricates a sports market or synthetic trade.

Coverage status is deliberately stricter than listing visibility. NFL winner
remains an explicit coverage gap while its visible contracts continue through
the forced paper lane; it does not become covered merely because listings were
observed. The gap closes only after scope-specific forward settlements and
calibration support a later, reviewed change.

## Contract coverage

| Sport | Winner | Total | Specialized markets |
|---|---|---|---|
| MLB | `KXMLBGAME` | `KXMLBTOTAL` | `KXMLBRFI` YES=YRFI, NO=NRFI |
| NFL | `KXNFLGAME` | `KXNFLTOTAL` | League-isolated score model |
| NCAAF | `KXNCAAFGAME` | `KXNCAAFTOTAL` | League-isolated score model |
| NHL | `KXNHLGAME` | `KXNHLTOTAL` | League-isolated goal model |
| NBA | `KXNBAGAME` | `KXNBATOTAL` | League-isolated score model |
| NCAAB | `KXNCAAMBGAME` | `KXNCAAMBTOTAL` | League-isolated score model |

The MLB run model learns exponentially weighted offense, prevention,
first-inning scoring and prevention, venue environment, announced-starter ERA,
and outdoor temperature. It derives winner, total-run, and YRFI probabilities
from one internally coherent run distribution.

The generic team model keeps independent score distributions for NFL, NCAAF,
NHL, NBA, and NCAAB.

## League engines

Each league's kernel is purpose-built to that sport's real scoring shape
(all challenger-only, fail-closed on missing feeds):

| Engine | Module | Mechanism |
|---|---|---|
| MLB PA-sim + parks | `autonomy/sports/mlb_pa_sim.py`, `autonomy/sports/mlb_parks.py` | Plate-appearance Monte Carlo: each batter vs. the current pitcher via the Bill James log5 odds ratio against league average, with platoon and park adjustments; many simulated games aggregate into winner/total-run/YRFI/first-five-innings probabilities. Park factors are a static multiplicative scalar on expected total runs (e.g. Coors ~1.28, Petco/Oracle ~0.90), fail-closed to 1.00 for any unmapped team. |
| NFL key-number margin kernel | `autonomy/sports/nfl_margin.py` | NFL margins are not normal — field goals (3) and touchdowns (7) create real spikes (~10% of games land exactly on 3, ~7% on 7). An auditable base PMF over absolute margins is exponentially tilted (`P_mu(m) ∝ base(m) * exp(lambda*m)`, lambda solved by bisection) so the mean matches the matchup's expected margin while preserving the key-number spikes. Winner/spread rungs derive from the same distribution; totals price from a separate normal. |
| NBA pace × efficiency | `autonomy/sports/nba_model.py` | Per-team EWMA offensive/defensive rating per 100 possessions plus a shared pace EWMA (from boxscore-derived possession estimates). Expected score = pace × efficiency/100; dispersion is heteroskedastic, scaling with `sqrt(pace/99.5)` so fast games carry more variance. A bounded rest engine and a garbage-time cap protect the rating EWMAs from blowout distortion. Falls back to the generic team model below a minimum-games threshold. |
| NHL goal model + goalie identity | `autonomy/sports/nhl_model.py` | Home/away goals modeled as independent Poisson processes (true bivariate correlation is a documented, deferred gap) over one regulation goal matrix, with an explicit OT/shootout branch since Kalshi settles on final score including overtime. Goalie identity (starts-weighted save percentage) shifts the matchup. |
| NCAAF kernel + talent-gap Elo | `autonomy/sports/college.py` | Reuses the NFL margin kernel wholesale with a shallower college key-number PMF (spikes ~40% shallower than the NFL table). The margin itself blends season EWMA form with an Elo-derived talent-gap prior, weighted toward Elo early season and toward observed form as games accumulate. |
| NCAAMB pace model | `autonomy/sports/college.py` | Reuses the NBA pace × efficiency engine wholesale via a college parameter set (different cold-start constants) — same classes, same math, no duplication. |
| NFL live state | `autonomy/sports/live_team_models.py` | Conditions the pre-game team scoring means on ESPN's observed score and regulation clock through an NFL-specific compound-Poisson scoring-event mix. Winner, spread, and total share the same discrete final-score distribution. |
| NCAAF live state | `autonomy/sports/live_team_models.py` | A separate compound-Poisson model with a college-specific scoring-event mix and model version; it does not alias the NFL distribution. |
| NCAAMB live state | `autonomy/sports/live_team_models.py` | A separate 40-minute/two-half residual model with NCAAMB margin/total dispersion. It never reuses NBA's 48-minute/four-quarter clock. |
| Crypto DVOL | `autonomy/signals/crypto_indicators.py`, `autonomy/crypto_implied_book.py` | The crypto analog of a sports sharp book: Deribit's DVOL implied-volatility index (forward-looking) prices an independent P(YES), triangulated against the champion's realized-vol model (backward-looking) and the Kalshi price. Fail-closed to `model_only` on missing or stale (>6h) DVOL data; challenger-only, excluded from the execution ensemble pending promotion. |

Every live-state model is point-in-time and stateless: it learns only from the
settled-game pre-game engine, then conditions on the current ESPN observation.
Missing/invalid scores, period, or clock produce an abstention. NFL/NCAAF
overtime also abstains until possession-aware overtime rules are modeled.

## 3×3 conviction lattice

`autonomy/coherence.py` builds a nine-cell lattice for every game: three
estimators (the league's own model, the de-vigged sharp book, the Kalshi
crowd price) crossed with three market families (winner, spread ladder, total
ladder). Two independent checks feed conviction: **ladder violations** (the
exchange's own rung prices should be monotonic within one family — no model
opinion needed, gated by a small fee-band slack) and **cross-family
incoherence** (the winner price and the spread ladder should reconcile
through the model's own joint distribution — a first-order linear
transport). `lattice_conviction` combines both into a tier —
`TIER_STRUCTURAL` (an exchange-internal contradiction, needs no forecast to
trust), `TIER_CROSS_CONFIRMED` (model, book, and market-internal structure
all agree), `TIER_MODEL_BOOK`, or `TIER_MODEL_ONLY` — and grouping is
subject-aware so opposite sides of the same spread are never mistaken for
confirming each other. The mispricing monitor surfaces `structural` and
`cross_confirmed` counts every pass as the highest-conviction subset of its
shortlist.

## Player availability, injuries, rookies, and mismatches

`autonomy/sports/players.py` (WS-6, all engines) enforces a hard split
between two kinds of availability signal: **HARD** statuses (Out, Doubtful,
and — since WS-7 — suspensions) shift the expected margin via a bounded,
position-weighted point delta; **SOFT** statuses (Questionable, Day-to-Day,
Probable) and rookie flags widen uncertainty only, leaving the mean
byte-identical. MLB's older, narrower `autonomy/sports/injuries.py` (ESPN's
keyless MLB injuries feed) is left independently in place rather than folded
in — it turns a count of currently-questionable players into a bounded
uncertainty-only burden (long-term IL excluded, saturating past six
players) and was not touched by the newer, richer layer.

Live ejections are intentionally separate from those pre-game availability
adjustments. `autonomy/live_odds.py::parse_ejection_events` accepts only
explicit ESPN `summary.plays` events, preserving the play's wall-clock time,
period/clock, score, team ID, and participant IDs. The mispricing sweep adds a
local receipt timestamp and surfaces the observation on shortlist and
opportunist rows. It never applies a second mean/uncertainty adjustment after
the live score has already reflected the player's absence. If ESPN publishes
an ejection only later in article prose, Dummy abstains rather than backfill
future knowledge into a live decision.

## Situational engine

`autonomy/sports/situations.py` (WS-7) applies the same HARD/SOFT discipline
to game context: verifiable rest states (byes, short weeks, back-to-backs)
produce a bounded mean adjustment on the expected margin, while soft/
narrative states (playoff motivation, roster or coaching churn) widen
uncertainty only. It builds a generic rest tracker for NFL and NHL
specifically — NBA already has its own tested rest engine inside
`nba_model.py` that this layer deliberately leaves untouched. Every input is
fail-closed: a missing feed or an offseason gap yields zero adjustment,
byte-identical to the layer being disabled.

NFL cycle warmup requests a separate 21-day settled-game lookback for the rest
tracker, so a daemon outage across a prior game or bye does not silently erase
the verifiable rest state. Mismatch inputs are normalized in their native
domains (basketball rest points and NHL goal-rate shifts) before the `tanh`
gate; point/goal conversion remains a separate bounded output step. This keeps
the gate reachable without increasing the existing maximum margin adjustment.

## Football weather

`autonomy/sports/football_weather.py` (WS-10) adjusts NFL/NCAAF game
**totals only** — never winner or spread — for outdoor wind, cold, and
precipitation, using the same keyless Open-Meteo pattern MLB's ballpark
weather already uses. Coverage is intentionally partial: all 32 NFL stadiums
but only the top-40 college programs; anything outside that list, or any
fetch/parse failure, resolves to a zero adjustment with empty features —
indistinguishable from "uncovered" by design.

## Game-engine mechanics

The simulator uses game-design concepts as disciplined research controls:

- **Replay buffer:** the first point-in-time observation per ticker and source
  is retained for training; later near-settlement updates cannot overwrite it.
- **Elo/MMR:** team, fighter, weight-class, and driver strength updates only
  after completed events. Research genomes receive a report-only MMR.
- **Curriculum:** scopes progress through `ROOKIE`, `VETERAN`, `ELITE`, and
  `BOSS` tiers based on settled observations and independent event clusters.
- **Skill tree:** temperature and bias mutation unlock first; market blending
  and uncertainty controls unlock at Veteran; edge and entry-policy mutation
  unlock only at Elite. Code rewriting never unlocks.
- **Adversarial arenas:** every prediction is replayed under `REGULATION`,
  `FOG_OF_WAR`, `META_SHIFT`, and `BOSS_CHAOS` uncertainty regimes.
- **Self-play tournament:** bounded genomes compete on event-purged
  chronological folds. A research champion advances only when paired
  event-cluster bootstrap confidence is positive and paper P&L does not fall.
- **Deterministic seeds:** every scenario can be replayed exactly for debugging
  and failure analysis.

## Deep analytics

Each league and market type is evaluated separately. The lab reports Brier
score, log loss, ECE, MCE, AUC, sharpness, mean probability, paper trade count,
win rate, mean trade P&L, Sortino ratio, net P&L, maximum drawdown, event-cluster
count, paired-bootstrap confidence, and adversarial-arena probability bounds.

Chronological folds are grouped by event. Different sides, totals, or round
contracts from the same game/fight/race can never land on both sides of a
train/test boundary. The initial research advancement gate requires at least
40 settled observations and 20 event clusters in the exact sport/market scope.

## Running it

```powershell
python scripts/run_dummy_sports_simulation.py
powershell -ExecutionPolicy Bypass -File scripts/install_sports_simulation_task.ps1
```

Evidence is stored at `runtime/autonomy/sports_simulation.db`. Models and
research champions stay under `runtime/autonomy/`. Timestamped reports and the
atomic latest report are under `artifacts/dummy/sports_simulation/`.
The operator dashboard at `http://127.0.0.1:8787/` shows sports scheduler
health, designated-type coverage, active papers, separate lane P&L, settlement
progress, explanations, and paper-only Start/Stop controls.

## Authority boundary

The lab uses public GET requests, loads no credentials, contacts no broker,
places no order, and has no production weight, risk, deployment, execution, or
capital authority. Recursive improvement means bounded parameter selection
under forward evidence—not autonomous source-code rewriting.
