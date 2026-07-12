# Alt Lines + Live In-Play + Buy-Low Monitor — Arsenal Design

**Goal:** Extend Dummy's arsenal with alternate spreads (runlines) / alternate
totals, live in-play re-pricing, and a fast "buy-low" dislocation monitor —
across sports and crypto — each intelligent, recursively graded, and
non-destructive.

**Operator answers (2026-07-12):** sequencing left to Claude ("make it state of
the art, whichever way"); **all new models challenger-only until a
settlement-backed promotion review**; buy-low via a **dedicated fast monitor
loop** (not by tightening the 10-min full scan).

## Grounding (verified against the live public Kalshi API + the codebase)

- **Alt totals already work.** `KXMLBTOTAL` lists every strike as its own market
  (5.5/6.5/7.5/8.5…). `BaseballIntelligenceSignal` already prices each at its own
  `floor_strike` via `BaseballRunModel.total_probability(prediction, threshold)`.
  Nothing to build for MLB alt-totals; team-sport totals likewise price per-strike.
- **Spreads/runlines are new and the market exists.** `KXMLBSPREAD` is live —
  e.g. `KXMLBSPREAD-…AZLAD-AZ8` = "Diamondbacks win by over 7.5 runs?",
  `strike_type=greater`, `floor_strike` = the margin threshold, ladder
  4.5/5.5/6.5/7.5. The sim's Monte Carlo already produces per-sim
  `home_runs`/`away_runs`, so the run-**margin** distribution is nearly free —
  it is simply never exposed. (`KXMLBRUNLINE`/`MARGIN`/`WINBY` are empty; the
  real ticker is `KXMLBSPREAD`.) Team sports (`team_scores.py`) already carry a
  Gaussian `margin` + `margin_sigma`, so their spreads are a normal-CDF away.
- **Live in-play is feasible with keyless data.** `autonomy/sports/espn.py`
  already returns `status` ("pre"|"in"|"post"), live `home_score`/`away_score`,
  and per-inning linescores — NOT governance-gated (unlike statsapi.mlb.com).
  The MLB sim can be conditioned on current inning + score and simulate only the
  remaining innings. The intelligence signals currently hard-gate on
  `status == "pre"` (sports_intelligence.py:218) — that guard is the live hook.
- **Buy-low foundation exists.** `tape.py` already turns Kalshi 1-minute candles
  into microstructure features (momentum, volume surge, range position, spread).
  A dislocation monitor keys off price-below-fair-value, not model drift.

## Discipline (applies to every phase)

- **Challenger-only:** new sources set `features["challenger_only"]=True`; the
  forecaster's `fuse()` (forecaster.py:45) excludes them from the execution
  ensemble. Graded by contested-Brier **per market-type** (`source@VERTICAL`,
  extended with the market_type feature) so a spread model earns trust
  independently of the winner/total models.
- **Non-destructive / fail-closed:** no ESPN/live data, no margin coverage, or a
  degenerate state → the source abstains (returns None). Pre-game and existing
  markets are byte-identical to today.
- **No new live-execution authority.** The monitor and live models produce
  evidence and paper decisions only; promotion to shadow/live stays a separate,
  explicit, settlement-gated review.

## Phase 1 — Alternate spreads / runlines (this build)

Expose the margin distribution and price the `KXMLBSPREAD` ladder (and team-sport
spreads), challenger-only, per-market-type graded.

- `mlb_pa_sim`: add a run-margin distribution to the simulate result (empirical
  from the same sims — no extra cost) and a `margin_probability(dist, k)` =
  P(home_margin > k); expose the symmetric away side.
- `baseball.py`: `BaseballPrediction` carries the margin distribution;
  `BaseballRunModel.spread_probability(prediction, subject_team, threshold)` =
  P(subject wins by > threshold).
- `team_scores.py`: `spread_probability` from the existing Gaussian margin.
- `sports_intelligence.py`: parse `KXMLBSPREAD` (and team-sport spread series if
  listed) → `SportsContract(market_type="spread", subject=favored team,
  threshold=margin)`; price it; source `mlb_run_spread` etc.
- `scanner.py`: add the spread series to the watchlist (classifier already tags
  `KXMLB*` as SPORTS).

## Phase 2 — Buy-low dislocation monitor (sports + crypto)

A dedicated lightweight loop (own scheduled task, ~1–2 min cadence, fail-closed)
that re-checks top-edge targets, open paper positions, and (later) in-progress
games. It compares the current best executable price against the most recent
model fair value and flags a "buy-low" when price has dislocated below fair by
an edge threshold — reading `tape.py` microstructure to distinguish a genuine
dip from a stale quote. Crypto included (fast-moving). Evidence + paper only.

## Phase 3 — Live in-play re-pricing (sports)

Condition the MLB sim on current game state (inning, score) from ESPN `in`
games; simulate remaining innings → live winner/total/spread probabilities.
Relax the `status == "pre"` guard for a live-conditioned prediction path.
Challenger-only, graded as its own live market-type. Team sports follow via a
remaining-time Gaussian on the live margin.

## Recursive improvement

Every new model grades per market-type on settled evidence and earns fusion
weight only by beating the market on that type — winner, total, spread, and live
each stand on their own contested-Brier record. The monitor's flagged entries
are logged with the dislocation magnitude and the subsequent settlement so the
retro engine can learn which dislocations actually carried edge.
