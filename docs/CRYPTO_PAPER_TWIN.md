# Always-on crypto and commodities paper twin

Dummy's market-horizon paper twin is a permanent, public-read-only digital twin that
runs independently beside both normal shadow operation and any future
authorized live session. It has no broker adapter, credentials, production
ledger writes, execution authority, or capital authority.

## Live cohorts

Every five minutes the twin scans an exact allowlist and freezes the current
public source and Kalshi state:

- `15m`: native `KXBTC15M`, `KXETH15M`, and `KXSOL15M` direction contracts
  with minute momentum, volume, and microstructure inputs;
- `1h`: BTC, ETH, and SOL hourly price ladders with hourly-only technical state;
- `1d` and `1w` crypto: BTC, ETH, and SOL only, using directly compatible
  terminal-price markets when listed;
- `1d` and `1w` commodities: WTI, natural gas, and gold only, using the existing
  public continuous-future spot/volatility proxy.

When no directly model-compatible market is listed, the cohort records an
explicit abstention. It never substitutes max-price, head-to-head, or synthetic
contracts for a requested daily/weekly terminal-price horizon.

The allowlist is intentionally closed:

| Vertical | Horizon | Assets | Compatible series |
|---|---|---|---|
| Crypto | 15m | BTC, ETH, SOL | `KXBTC15M`, `KXETH15M`, `KXSOL15M` |
| Crypto | 1h | BTC, ETH, SOL | Mixed-cadence `KXBTCD`/`KXBTC`, `KXETHD`/`KXETH`, `KXSOLD`/`KXSOLE` events with listing duration at most 6 hours |
| Crypto | 1d | BTC, ETH, SOL | The same mixed-cadence series with listing duration over 6 and under 120 hours; legacy `BTCD`/`BTC` and `ETHD`/`ETH` aliases remain accepted |
| Crypto | 1w | BTC, ETH, SOL | The same mixed-cadence series with listing duration of at least 120 hours |
| Commodities | 1d | WTI, natural gas, gold | `KXWTI`, `KXNATGASD`, `KXGOLDD` |
| Commodities | 1w | WTI, natural gas, gold | `KXWTIW`, `KXNATGASW`, `KXGOLDW` |

Kalshi can publish hourly and weekly events inside the same crypto series. Dummy
therefore routes each market from its own `open_time` to `close_time` duration,
not from the series-level frequency label. Missing or invalid listing timestamps
fail closed instead of being guessed into a horizon.

Series availability is evaluated from the public API every cycle. Other crypto
assets and horizons are outside policy even if the exchange lists them.

Each vertical and timeframe has three isolated lanes:

- `incumbent`: current production forecast and production selection
  thresholds;
- `recursive`: a frozen evolution-lab genome blended with the timeframe model;
- `exploratory`: a permissive positive-EV paper-only lane that accumulates
  outcomes even when production correctly abstains. It can diagnose threshold
  and timing mistakes but never counts as promotion evidence.

Crypto `1h` additionally runs `hourly_calibrated`, a market-anchored research
lane created after the raw hourly model underperformed the market across BTC,
ETH, and SOL. It freezes the earliest forecast per asset/expiry and scores it
even when no paper trade is selected. The lane fits incremental model weight
only from already-settled forward rows using expanding-window validation. Its
model share remains zero until at least 20 forecasts and ten event clusters
exist, at least ten genuinely later forecasts are scored, and the
event-cluster-bootstrap lower-95% Brier advantage is positive. Even after
activation, model share is capped at 50% and the lane remains paper-only.

Only one paper position may be opened per strategy, vertical, timeframe, asset, and
expiry. Adjacent strike ladders therefore cannot manufacture independent
trades or pyramid one event.

For every BTC, ETH, and SOL terminal-price event, Dummy now evaluates the full
nearest-expiry Kalshi target ladder available to its models: above-threshold,
below-threshold, and bounded-price buckets. It computes the best YES or NO side
for each target after taker fees and a probability-uncertainty haircut, then
chooses the highest conservative-EV target that clears all lane gates. An
eligible lower-EV target outranks a spectacular-looking but blocked target, so
one invalid strike cannot incorrectly turn the whole asset/expiry into an
abstention. Missing, non-finite, or malformed strikes fail closed.

The 15-minute products remain one direction contract per expiry rather than a
price ladder. Their exchange-provided opening reference is validated and
recorded; it is never guessed from the ticker. The audit persists the selected
target, target-type and boundary coverage, total targets evaluated, eligible
count, and the top twelve rejected alternatives. It ranks every compatible
target in memory but bounds persisted alternatives to avoid unbounded database
growth on very large ladders.

Target choice maximizes fee- and uncertainty-adjusted expected value, not raw
win rate. Buying a very expensive favorite can raise win rate while losing
money after price and fees. Settled win rate, P&L, and Brier skill are therefore
tracked together by horizon and target type. Those target-type summaries are
diagnostic only until enough independent forward evidence exists; small or
selection-biased samples cannot automatically alter target preference.

The inventory separately counts every listed target and every target with a
complete two-sided quote and forecast. Thin, one-sided targets remain visible
but cannot be scored or selected because Dummy will not invent the missing
market-probability anchor or executable opposite-side quote.

Every scored candidate is frozen at its earliest clean snapshot, not just the
rank-selected contract. Once Kalshi settles the event, Dummy scores each
unselected alternative against its original quoted side, fee, model
probability, and market probability. The resulting rejection-regret ledger
groups quote-counterfactual outcomes by target type and blocker (uncertainty,
edge, entry price, conservative EV, or calibration activation). It is a
diagnostic for later cluster-purged walk-forward gate research—not fill
evidence, not an automatic threshold tuner, and never an authority to trade.

## Decision explanations

Every lane writes a plain-language and structured explanation containing:

- market ticker, asset, timeframe, strategy, and action;
- model and market probabilities, uncertainty, and absolute edge;
- timeframe-specific model probability and signal features;
- quoted entry, fee, conservative probability, and conservative EV;
- selected price-target semantics, targets evaluated, eligible-target count,
  and the ranked alternative-target audit;
- exact eligibility or abstention rule;
- frozen market, source-weight, public-source state, and policy payloads;
- explicit paper-only and no-broker-contact language.

Observations and trades are stored in
`runtime/autonomy/crypto_paper_twin.db`. Timestamped reports and an atomic
latest report are written under `artifacts/dummy/crypto_paper_twin/`.

## Phase 1: parallel paper books

The twin books a one-contract simulated taker entry only at the live public
top ask. This is quote-executable counterfactual evidence, not a witnessed
fill. It also creates a separate one-minute maker diagnostic with a captured
public queue snapshot.

## Phase 2: frozen forward selection

The recursive genome is frozen in an epoch. A newly proposed genome cannot
replace it merely because another hourly trainer run occurs. Research-only
rotation requires at least 30 settled trades across five clusters and a
statistically negative current epoch. Forward gates require independent
clusters, positive lower-confidence P&L, positive Brier skill, and stress
survival. Explicit main-shadow review requires 100 forward settled trades,
ten clusters, positive paired cluster-bootstrap advantage over the incumbent,
and a safe severe-stress fraction. The exploratory lane is permanently
ineligible for promotion.

The hourly calibration report also exposes a selected-trade bootstrap
diagnostic from the older exploratory record. That evidence explains the
initial zero model weight but is explicitly selection-biased and never counts
toward activation. Only the dedicated earliest-forward calibration ledger can
unlock hourly model influence, after which the normal forward, execution, and
stress gates still apply.

## Phase 3: execution learning

Maker fills require a public standard-book print strictly through the limit or
enough exact-price volume to consume captured queue depth plus the simulated
contract. Missing queue state and unresolved orders remain explicit
weaknesses. Taker and maker results are reported separately.

The twin also searches a 256-policy execution grid across uncertainty, EV,
entry price, and queue depth. A policy cannot be proposed for a bounded main-
shadow review until it has 30 settled trades across ten clusters, positive
lower-95% P&L, and 20 public-print maker fills. It never applies the policy.

## Phase 4: canary decision

A paper lane needs at least 30 settled trades, ten event clusters, positive
net and lower-95% mean P&L, positive Brier skill versus market, and a surviving
compounding stress fraction to become `paper_research_ready`.

Even then `live_canary_ready=false`. Paper fills never satisfy the production
canary gate. A later bounded main-shadow experiment must earn witnessed fills,
and live operation still requires separate explicit operator authorization.

## Phase 5: controlled compounding

Settled paper trades are resampled by event cluster at 0.25%, 0.5%, 1%, and 2%
bankroll fractions under 0, 2, 5, and 10 cents of adverse slippage. A fraction
is only stress-safe with at least 30 trades and ten clusters, fifth-percentile
capital preservation, at most 10% 95th-percentile drawdown, and at most 25%
loss probability.

The report always sets `recommended_live_fraction=null`,
`capital_authority=false`, and `live_application=false`. Negative drift or a
10% drawdown proposes immediate demotion to zero; it never applies capital.

## Operation

```powershell
python scripts/run_dummy_crypto_paper_twin.py --summary
powershell -ExecutionPolicy Bypass -File scripts/install_crypto_paper_twin_task.ps1
Get-ScheduledTask -TaskName DummyCryptoPaperTwin
```

The scheduled task runs every five minutes, does not inspect the autonomy
session or kill switch, and therefore continues independently during an
authorized live session without inheriting its authority. It writes the full
audit artifact separately, keeps a compact dashboard summary, and appends one
bounded JSONL health record per cycle to a rotating log. Overlapping runs are
ignored, missed starts are recovered, and a cycle that exceeds the four-minute
execution ceiling cannot strand the scheduler behind a thirty-minute lock.
