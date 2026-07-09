# Dummy

Autonomous, recursively self-improving prediction-market trading agent for
Kalshi. Operator surface is **start / stop** — everything between is decided
by the system inside its own survival constraints, and every decision traces
back to graded evidence in a ledger.

## The loop

```
scan → signal → fuse → allocate → risk → execute → reconcile → learn
```

Every cycle (10-minute cadence via a scheduled task) the predator sweeps the
watchlist series, prices every market with every applicable source, fuses
opinions by earned trust, ranks opportunities by capital velocity
(edge per √hour-to-settlement), sizes with quarter-Kelly under a stage
ladder, places maker-first LIMIT orders, reconciles settlements, and grades
every source against reality.

## Signal sources (all fail-closed)

| Source | Edge basis |
|---|---|
| `weather_openmeteo` | Multi-model NWP ensemble (GFS/ECMWF/ICON) vs temperature strikes, bias/sigma calibrated per city from historical-forecast-vs-ERA5 backfill |
| `crypto_spot_vol` | Driftless lognormal from realized vol (Coinbase candles) vs BTC/ETH strike ladders |
| `crypto_ewma_t` | Challenger model: EWMA volatility + fat-tail mixture — runs beside the champion; the contested record selects |
| `sports_elo` | Per-league Elo from ESPN results, pitcher-aware for MLB (probable starters' ERA shifts effective rating) |
| `sportsbook_consensus` | De-vigged book moneyline (both sides) + steam: open→current line movement in probability space |
| `cross_venue` | Polymarket implied probability as an independent voice |
| `commodities_spot_vol` | WTI/gold/natgas spot + realized vol vs price thresholds |
| `market_debias` | The exchange's own measured miscalibration: empirical price→outcome curve from thousands of graded settlements |
| `market_prior` | The book's mid as a Bayesian anchor, weight decaying with thinness |
| `llm_debate` | Five-model panel (distinct providers) with a revision round, adjudicating only top-K edge markets, fed live tape features |

## Recursive improvement

- **Calibration**: every settlement Brier-scores every source that opined —
  globally and per-vertical (`source@VERTICAL`) — and updates trust
  multiplicatively. Influence is earned by beating the market, nothing else.
- **Contested truth**: trust and the live gate key on the *contested* record
  (markets where a source disagreed with the market prior by ≥5¢ — the
  population it would actually trade). Agreeing with the market and being
  right proves nothing.
- **Phantom grading**: every forecasted market (~1,000/cycle) is settled and
  graded when it closes, not just the handful traded — evidence accrues at
  hundreds of settlements per day.
- **Retro replay**: point-in-time reconstruction against already-settled
  markets (historical candles + historical forecasts + contemporaneous
  market quotes from candlesticks), no lookahead.
- **Metabolic recalibration**: every ~6h the daemon re-runs the backtest
  bootstrap and refits the debias curve. No operator in the loop.
- **Model evolution**: challengers run beside champions under their own
  source names and earn their way in or starve.
- **Reflexion**: losing decisions distilled into structured lessons via the
  model router.

## Self-managed risk

- Quarter-Kelly sizing under a stage ladder (SHADOW → CANARY → RAMP →
  CRUISE); promotion strictly on realized settled P&L, demotion instant.
- Drawdown ladder: −10% half size, −20% demote, −30% hard self-stop.
- Correlation clustering: adjacent strikes / city-days / both game sides
  collapse into one cluster with its own caps.
- Stage close-horizon: early stages only hold near-dated markets so
  position slots recycle.
- Exchange-enforced order TTL (20min crypto / 45min elsewhere) instead of
  cancel loops.

## Safety invariants

- **Evidence gate**: a LIVE session refuses to start until ≥20 settled
  markets, bootstrapped weights, and a source with a contested
  market-beating record exist. Overridable only by explicit operator intent.
- Live orders go through a hardened firewall adapter: LIMIT only,
  per-order validation, transport-witnessed truth (broker contact is
  claimed only on HTTP evidence).
- Maintenance awareness: exchange down → cycle skips cleanly; trading
  paused → learning continues, zero orders.
- Circuit breakers quarantine failing sources; errors are eaten as
  evidence, never stalls.
- The kill file stops everything, instantly and unconditionally.

## Operator surface

```bash
python scripts/run_dummy_autonomous.py start          # shadow session
python scripts/run_dummy_autonomous.py canary --live  # evidence gate + balance
python scripts/run_dummy_autonomous.py start --live --ack "<exact ack>"
python scripts/run_dummy_autonomous.py stop           # instant, unconditional
python scripts/run_dummy_dashboard.py --port 8787     # read-only dashboard
python scripts/run_dummy_retro_backfill.py --bootstrap
```

Details: [docs/AUTONOMY.md](docs/AUTONOMY.md).
