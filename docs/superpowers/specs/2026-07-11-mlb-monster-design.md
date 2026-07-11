# The MLB Monster — a recursively self-improving, market-beating baseball model

**Date:** 2026-07-11
**Status:** Design approved (brainstorm); pending spec review before implementation plan.

## Goal

Turn Dummy's MLB prediction from market-parity into a system that measurably
beats the closing market on baseball. "Better than anything" is defined by a
three-headed validation bar (below), not a vibe.

Current state: `autonomy/sports/baseball.py` is a deliberately simple team-level
EWMA runs Poisson model with a season-ERA starter adjustment and a linear
temperature term. Measured on the live paper ledger (2026-07-10 slate, 170
settled forced decisions) its Brier is 0.1722 vs the market's 0.1700 — parity,
a hair behind. It is blind to lineups, platoon splits, bullpen, true park
factors, pitch-level rates, and wind. The market prices all of those, so parity
is the expected ceiling of the current inputs.

## Success bar — three validation heads

An engine is only "better" when all three heads agree, and it only becomes a
champion when Head 1 is positive:

1. **Beat the close (primary, money bar).** Cluster-robust, out-of-sample
   Brier skill positive versus the Kalshi/sportsbook *closing* price on the
   **contested population** (games where the engine disagrees with the market
   by >= 5c). Beating the market on the games you'd actually trade is the only
   edge that pays. This is the optimization target.
2. **Beat a public benchmark (sanity).** Accuracy / Brier versus a named public
   model (ESPN win probability or a 538-style Elo). A guard against overfitting
   to the market's noise; not sufficient alone.
3. **Paper P&L (operational).** Simulated P&L on forced + policy MLB paper
   trades. The operational outcome, weakest as a truth signal (rewards
   variance), used only to confirm the edge converts to money.

## Architecture — three layers

### Layer A — Data foundation (`autonomy/sports/statsapi.py`)

Keyless, official ingestion from `statsapi.mlb.com` (same public-read-only
discipline as the weather/Elo/cross-venue feeds). Point-in-time captured with
receipt-time provenance so retro replay stays lookahead-free.

Fields, by signal value:
- **Confirmed starting lineups** — the 9 batters actually playing, batting
  order, and late scratches (not just the probable pitcher). The single largest
  gap versus the current model.
- **Batter/pitcher handedness platoon splits** — per-batter vs L/R pitching,
  per-pitcher vs L/R batting.
- **Bullpen fatigue** — recent-usage / back-to-back appearances / pitches
  thrown, per reliever.
- **True park factors** — run/HR environment per venue, not the current
  venue-EWMA proxy.
- **Per-pitcher rate stats** — K%, BB%, HR/9, and an xERA-adjacent estimate,
  for starters and the projected bullpen.
- **Live wind and temperature** — direction and speed, not just temperature.

Contract: a `MlbGameContext` dataclass with every field nullable and a
`fields_present` provenance map, so an engine can degrade gracefully and the
validation harness can attribute misses to missing inputs. The existing ESPN
feed remains the fallback when StatsAPI is unavailable.

**Two-snapshot lineup-delta edge (the timing novelty).** Confirmed lineups
finalize ~1-2h before first pitch, and that is when the market reprices. The
data foundation captures two point-in-time snapshots per game: an early
**projected** context (probable pitcher + projected lineup) and a locked
**confirmed** context the moment real lineups post. The delta between the two
forecasts — a scratched star, a platoon-heavy lineup against a same-handed
starter — is itself a tradeable signal captured before the market fully
adjusts. Cadence: poll each game's lineup status roughly every 10 minutes
inside a 3-hour pre-game window; lock the confirmed snapshot on finalize. Both
snapshots are graded independently by the validation harness so the timing edge
is measured, not assumed.

### Layer B — Three model heads (each a graded source)

Each head registers under its own source name and earns trust independently.
They do **not** vote equally; the existing ensemble forecaster fuses them by
contested-Brier trust, so a head rises or starves on its own merit.

1. **`mlb_pa_sim` — plate-appearance Monte Carlo (champion).** Simulates the
   actual game one plate appearance at a time: this batter vs this pitcher,
   platoon- and park-adjusted, inning by inning, swapping to the bullpen on a
   fatigue rule. A single simulation yields win / total (any threshold) /
   YRFI-NRFI / first-5-innings / run-line probabilities coherently. Reuses the
   existing `SportsMonteCarloSimulator` scaffold. Deterministic with a seed.
2. **`mlb_gbm` — online gradient-boosted trees (challenger).** Engineered
   features (lineup wOBA, pitcher rates, park, weather, bullpen) into an
   **online** boosted model that updates game-by-game via `river` (existing
   `analytics` extra — no new runtime dependency). An online learner is the
   state-of-the-art fit here: it streams with the season, never refits from
   scratch, and cannot overfit a short season the way a deep batch tree does.
3. **`mlb_bayes` — conjugate hierarchical model (challenger).** Pure-Python
   Gamma-Poisson priors over team/player run rates and Beta-Binomial over event
   rates, with team-to-league shrinkage, updated as the season progresses. No
   PyMC/Stan: deterministic, fully explainable for the ledger. Principled
   uncertainty; lands last.

### Layer C — Validation harness (`autonomy/sports/mlb_validation.py`)

Computes the three heads for any engine over settled evidence: contested-Brier
skill vs close (cluster bootstrap, event-purged walk-forward, no lookahead),
public-benchmark accuracy, and paper P&L. Built before the engines so every
head is graded from birth. Writes plain-language attributions to the ledger.

## The recursive / meta layer — what makes it self-improving

Four loops, each closing on measured contested truth, no operator in the loop:

1. **Head-level self-tuning (dynamic).** Each engine carries a bounded genome
   (park/platoon/bullpen coefficients for the sim; hyperparameters for the GBM;
   priors for the Bayesian). An hourly read-only curriculum (the
   `simulation_training` pattern) searches genomes on settlement-lagged,
   event-purged walk-forward and proposes a bounded challenger — never mutates
   the champion blind.
2. **Ensemble self-weighting (cohesive).** The three heads fuse by
   contested-Brier trust — the existing forecaster mechanism. The ensemble *is*
   the meta-model; its weights move on their own as heads prove or fail.
3. **Feature-discovery critic (meta).** A periodic pass asks which unused
   StatsAPI field would most reduce residual error on the games the system got
   wrong, and ranks the next feature to ingest — the system names its own next
   upgrade from its own misses.
4. **Regime-drift guard (dynamic).** ADWIN (existing `river` extra) on each
   head's contested-Brier stream; a head whose edge decays (trade deadline,
   injury wave, September call-ups) auto-decays in trust and triggers a re-fit.

Every recursive move writes to the ledger with an explanation, so the whole
organism is auditable.

## Build sequence — independently shippable sub-projects

Too large for one spec; decomposed in dependency order. Each stage lands green
and proves itself on real MLB games before the next builds on it.

- **S1 — Data foundation** (`statsapi.py`). Ships when live-verified against a
  real slate, all fields populated, retro replay lookahead-clean. Everything
  depends on this; **first spec.**
- **S2 — Validation harness** (`mlb_validation.py`). Built before the models so
  every engine is graded from birth. Ships when it reproduces the current
  model's parity number as the baseline.
- **S3 — Head 1 PA-sim** (`mlb_pa_sim`). Ships when contested-Brier vs close is
  measurably positive out-of-sample.
- **S4 — Heads 2 & 3** (GBM + Bayesian challengers). Fuse by earned trust; each
  ships when it clears Head 1 or starves honestly.
- **S5 — Recursive layer.** Genome curriculum, feature-discovery critic, ADWIN
  drift guard. Ships when a genome improvement is demonstrated on walk-forward
  without touching the champion blind.

The ensemble fusion, contested-trust weighting, forced-coverage ledger, and
canary gate already exist; the heads plug into them. Real games are the
validator — build against the live slate, never blind.

## Non-goals

- No paid data feeds; StatsAPI is official and keyless.
- No live-execution or capital authority changes; this is forecasting quality.
  MLB paper/forced-coverage and canary discipline are unchanged.
- No new heavy runtime dependency without a measured justification (GBM/Bayes
  prefer existing optional extras).
- Not a rewrite of the current `baseball.py` — it remains the fallback and the
  parity baseline until a head beats it on Head 1.

## Resolved design decisions

- **GBM library:** `river` online gradient-boosted trees (existing `analytics`
  extra). No new runtime dependency; online learning is the correct SOTA fit
  for a streaming season.
- **Bayesian library:** none — pure-Python conjugate hierarchical model
  (Gamma-Poisson / Beta-Binomial). Deterministic and ledger-explainable.
- **Lineup timing:** two-snapshot (projected + confirmed) design, ~10-minute
  polling inside a 3-hour pre-game window, both snapshots graded independently.
