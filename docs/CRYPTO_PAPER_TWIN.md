# Always-on crypto paper twin

Dummy's crypto paper twin is a permanent, public-read-only digital twin that
runs independently beside both normal shadow operation and any future
authorized live session. It has no broker adapter, credentials, production
ledger writes, execution authority, or capital authority.

## Live cohorts

Every five minutes the twin scans public Kalshi BTC/ETH/SOL markets and freezes
the current Coinbase, Kraken, Deribit, and Kalshi state.
It operates two decision clocks in parallel:

- `15m`: native `KXBTC15M`, `KXETH15M`, and `KXSOL15M` direction contracts
  with minute momentum, volume, and microstructure inputs;
- `1h`: BTC, ETH, and SOL hourly price ladders with hourly-only technical state.

Each timeframe has three isolated lanes:

- `incumbent`: current production forecast and production crypto selection
  thresholds;
- `recursive`: a frozen evolution-lab genome blended with the timeframe model;
- `exploratory`: a permissive positive-EV paper-only lane that accumulates
  outcomes even when production correctly abstains. It can diagnose threshold
  and timing mistakes but never counts as promotion evidence.

Only one paper position may be opened per strategy, timeframe, asset, and
expiry. Adjacent strike ladders therefore cannot manufacture independent
trades or pyramid one event.

## Decision explanations

Every lane writes a plain-language and structured explanation containing:

- market ticker, asset, timeframe, strategy, and action;
- model and market probabilities, uncertainty, and absolute edge;
- timeframe-specific model probability and signal features;
- quoted entry, fee, conservative probability, and conservative EV;
- exact eligibility or abstention rule;
- frozen market, source-weight, crypto-state, and policy payloads;
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
authorized live session without inheriting its authority.
