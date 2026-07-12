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
