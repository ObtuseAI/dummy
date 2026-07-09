# Dummy Autonomy Layer

Shipped 2026-07-08. The predator loop: scan → signal → forecast → allocate →
risk → execute → reconcile → learn. Operator surface is start/stop only;
everything between is decided by the system inside the risk brain's survival
constraints.

## Operator dashboard + alerts

```bash
python scripts/run_dummy_dashboard.py --port 8787   # open http://127.0.0.1:8787/
```

Read-only page: liveness/heartbeat, live-canary gate + blockers, risk state,
per-source calibration scoreboard, recent cycles, bankroll curve, and alerts.
Alerts (`autonomy/alerts.py`) fire once per episode on SELF_STOP, drawdown
ladder deepening, evidence-gate-green, and cycle-error streaks — written to
`runtime/autonomy/alerts.jsonl` and surfaced on the dashboard.

## Continuous shadow + going live (Tier 1)

```bash
# Continuous shadow (durable): register the scheduled task ONCE, elevated.
scripts\install_shadow_task.bat        # 10-min cycles, survives reboot
# ...or run the loop yourself:
python scripts/run_dummy_shadow_daemon.py --loop --interval 600

# Watch liveness + history:
type runtime\autonomy\heartbeat.json
type runtime\autonomy\cycles.jsonl

# When settlements have accrued, grade + pre-rank, then check readiness:
python scripts/run_dummy_backtest.py --bootstrap
python scripts/run_dummy_autonomous.py canary        # evidence gate report

# First live canary — BLOCKED until the gate passes: >=20 settled markets,
# bootstrapped weights, and at least one source with a CONTESTED market-beating
# record (>=20 settled markets where it disagreed with the market prior by
# >=5c AND was right more than 55% of the time). Agreeing with the market and
# being right qualifies nothing. Enable the LLM panel for the session with the
# env var. This is the one irreversible step; it's yours.
set DUMMY_DEBATE_LIVE=1
python scripts/run_dummy_autonomous.py start --live --hours 6 --ack "<exact ack>"

# Stop everything, instantly:
python scripts/run_dummy_autonomous.py stop
```

The evidence gate (`autonomy/canary.py`) is fail-closed: a LIVE start returns
`started: false` with exact blockers until the shadow record proves earned
calibration. `--override-evidence-gate` exists but is deliberate operator
intent only.

## Commands

```bash
# Shadow session (default): full pipeline on live public data, orders recorded
# in the shadow book only. This is the calibration bootstrap — run it early,
# run it often.
python scripts/run_dummy_autonomous.py start

# One cycle (cron-able):
python scripts/run_dummy_autonomous.py once

# Status (session, kill switch, performance summary, risk state):
python scripts/run_dummy_autonomous.py status

# LIVE session: requires the exact typed acknowledgement.
python scripts/run_dummy_autonomous.py start --live --hours 24 --ack \
  "I authorize an autonomous Dummy trading session with self-managed risk under the LiveBrokerFirewall, LIMIT orders only, until I stop it"

# Stop: writes runtime/autonomy/KILL and disarms the session. Instant.
python scripts/run_dummy_autonomous.py stop
```

## Architecture

| Module | Role |
|---|---|
| `autonomy/scanner.py` | Series-targeted sweep of live Kalshi markets (watchlist of weather cities + crypto ladders); normalizes the dollars-string field schema |
| `autonomy/signals/weather_openmeteo.py` | Multi-model Open-Meteo ensemble (GFS/ECMWF/ICON) vs KXHIGH* temperature strikes; metadata-driven strike semantics with integer-reading continuity corrections |
| `autonomy/signals/crypto_spot.py` | Coinbase public candles → realized vol → driftless lognormal strike probabilities for KXBTC*/KXETH* |
| `autonomy/signals/market_prior.py` | The book's own mid as a Bayesian anchor, weight decaying with thinness |
| `autonomy/signals/sports_elo.py` + `autonomy/sports/` | ESPN public feeds + persistent per-league Elo (home edge, K per sport); win-probability for single-game moneylines; self-retrains from finished games each cycle. **MLB is pitcher-aware**: the probable starters' ERAs (from the scoreboard) shift each team's effective Elo, so an ace can overcome a road disadvantage |
| `autonomy/signals/sportsbook.py` | De-vigged sportsbook moneyline (both sides, vig removed) from the scoreboard's embedded book odds, plus **steam**: the open→current line movement in probability space. The sharpest public game forecast, and the trap detector when Elo fights the book |
| `autonomy/signals/crypto_spot.py::CryptoEwmaTailSignal` | Challenger crypto model beside the champion: EWMA (RiskMetrics) volatility + a variance-matched two-regime fat-tail mixture. Champion/challenger under separate source names — the contested record decides who earns fusion weight; models evolve by selection, not faith |
| `autonomy/tape.py` | Tape reader: momentum / volume-surge / range-position / spread from 1-minute candlesticks, fed as context to the LLM debate panel on top-K markets |
| `autonomy/exchange_status.py` | Venue awareness: exchange down (maintenance) → the cycle skips with an honest `CYCLE_SKIPPED_EXCHANGE_MAINTENANCE`; trading paused (overnight halt) → the full learning loop runs but zero orders are placed; status probe failure → proceed (unknown is not down) |
| `autonomy/signals/cross_venue.py` | Polymarket Gamma API implied probability as an independent voice; fail-closed exact team-set+date matching |
| `autonomy/live_book.py` | Signed Kalshi WebSocket orderbook (snapshot+delta state machine) + synchronous pre-submit fresh-quote guard that skips a maker quote that has crossed |
| `autonomy/debate.py` | Five-model LLM panel (distinct providers × temperatures) with a revision round; adjudicates only the top-K edge markets per cycle, injected as a trust-weighted signal |
| `autonomy/weather_calibration.py` | Historical-forecast backfill: per-city bias + sigma from past Open-Meteo forecasts vs ERA5 actuals, pre-training the weather signal |
| `autonomy/signals/commodities_spot.py` | WTI/natgas/gold spot + realized vol (keyless Yahoo Finance) → lognormal strike probabilities for KXWTI/KXNATGAS/KXGOLD |
| `autonomy/correlation.py` + risk brain group caps | Collapses correlated markets (adjacent strike buckets, one city-day, both game sides) into one cluster; per-cluster exposure + position-count caps stop the bankroll piling onto one underlying |
| `autonomy/backtest.py` | Offline replay of the ledger vs settlements: per-source Brier / log-loss / calibration curve, realized decision P&L, and derived trust weights that `--bootstrap` writes back so live starts pre-ranked |
| Phantom grading (`ledger.unsettled_forecast_markets` + `reconciler.reconcile_forecast_settlements`) | Settles and grades EVERY market the machine forecasted (~1000/cycle), not just the handful it traded — one settled-markets listing per watchlist series per cycle. Calibration evidence accrues from the whole forecast surface at hundreds of settlements/day |
| `autonomy/retro.py` | Retro evidence engine: point-in-time replay against markets that already settled. Market prior from Kalshi candlesticks at the historical decision moment; crypto spot/vol from historical Coinbase candles fully closed before it; weather from the Open-Meteo historical-forecast API (the day's own model runs). Signals land in the ledger as `mode='retro'` with historical timestamps; fail-closed (no contemporaneous quote -> market skipped) |
| `autonomy/signals/market_debias.py` | Empirical price->outcome curve mined from settled-market history (the exchange's own measured miscalibration, longshot bias included). Opines only where a 5-cent price bucket has >=100 observed outcomes; the retro engine never writes retro signals for this source, so its trust weight is earned on live settlements only |
| `autonomy/forecaster.py` | Inverse-variance fusion scaled by ledger trust weights |
| `autonomy/allocator.py` | Fee-aware EV, maker-first pricing, symmetric YES/NO evaluation |
| `autonomy/risk_brain.py` | Self-set dynamic caps: quarter-Kelly, stage ladder (SHADOW→CANARY→RAMP→CRUISE), drawdown ladder (-10% half size, -20% demote, -30% self-stop), stage close-horizon (CANARY 7d / RAMP 30d / CRUISE uncapped) so scarce early-stage slots never freeze on far-dated markets |
| `autonomy/executor.py` | Shadow book, or live through `KalshiLiveBrokerFirewallAdapter` (LIMIT only, per-order validation, transport-witnessed truth) |
| `autonomy/reconciler.py` | Fills + settlement detection; stale maker quotes expire via order-level `expiration_ts` (the no-direct-cancel-bypass gates forbid cancel calls) |
| `autonomy/learner.py` | Brier-scored multiplicative trust weights (reward = beating the market prior), Reflexion lessons via ModelRouter |
| `autonomy/ledger.py` | SQLite: signals, decisions, outcomes, settlements, trust, bankroll curve, lessons |

## Recursive improvement loops

1. **Calibration**: every settlement scores every source's logged signal
   (Brier vs the market-prior baseline) and updates trust multiplicatively —
   globally AND per-vertical (`source@VERTICAL` rows), so authority is
   domain-scoped. Sources gain influence only by beating the market.
0. **Metabolic recalibration**: every ~6h the daemon re-runs the backtest
   bootstrap and refits the market-debias curve from the full settlement
   history — the machine re-derives its own trust with no operator.
   Failing sources trip a circuit breaker (quarantine + auto-retry), so an
   upstream outage degrades coverage instead of wedging the loop.
2. **Risk**: realized P&L per contract is the only currency for stage
   promotion; drawdown demotes instantly with a 24h cooloff.
3. **Reflexion**: losing decisions are periodically distilled into structured
   lessons through the model router and stored in the ledger.
4. **Rejection avoidance**: broker rejections carry classifier categories
   (kalshi/rejection_classifier.py) back into decision filters.

## Enabling the LLM debate panel

The five-model panel is wired but gated off by cost control. To activate:

1. Set `live_model_calls_enabled: true` in `configs/model_routing.json`.
2. Ensure `OPENROUTER_API_KEY` is set (it is, in `.env`).

The panel then adjudicates the top-5 edge markets each cycle using five
distinct models — deepseek-v3, minimax-01, llama-3.3-70b, gemini-2.0-flash,
qwen-2.5-72b — each estimating a probability, then a revision round where each
sees the others' numbers. Result is injected as one `llm_debate` signal and
graded by the calibration ledger like any source. With live calls off (the
default), the panel returns cleanly with no effect (mock votes are ignored),
so the loop runs pure-quant.

Add or swap panel models by editing `provider_configs` in the routing config —
any `route_mode: "openrouter"` entry is picked up automatically (no code
change), courtesy of the generic `OpenRouterProvider`.

## Pre-live checklist (bootstrapping calibration)

```bash
python scripts/run_dummy_weather_backfill.py            # pre-train weather (done: 8 cities)
python scripts/run_dummy_sports_warmup.py --league mlb  # warm Elo (done: 590 games)
python scripts/run_dummy_sports_warmup.py --league nfl  # NFL preseason (KXNFLGAME live from Aug)
python scripts/run_dummy_autonomous.py start            # shadow — accumulate settlements
# Evidence accrues two ways, both honest:
#  - phantom grading: every forecasted market is graded when it settles
#    (runs inside every cycle automatically)
#  - retro replay: grade the recent PAST with point-in-time reconstruction
python scripts/run_dummy_retro_backfill.py --bootstrap  # replay history + weights + gate report
python scripts/run_dummy_backtest.py --bootstrap        # re-grade any time
python scripts/run_dummy_autonomous.py status           # review weights + ROI, then go live
```

## Doctrine inheritance

- **Rainman**: fail-closed, honest status enums (`CYCLE_OK`,
  `HALTED_KILL_SWITCH`, `HALTED_SELF_STOP:*`, `CYCLE_DEGRADED_*`), gates only
  added or hardened.
- **Blunder inflow**: source trust is earned from realized outcomes only;
  untrusted evidence is quarantined, never promoted.

## Safety invariants (unchanged by autonomy)

- Every live order goes through the hardened adapter: LIMIT only, price 1-99,
  idempotency key required, per-order notional from the risk brain.
- Live sessions expire; the executor re-validates session + kill switch at
  the moment of every submit.
- Broker contact is claimed only on transport witness.
- `stop` (or the -30% drawdown ladder) halts everything unconditionally.
