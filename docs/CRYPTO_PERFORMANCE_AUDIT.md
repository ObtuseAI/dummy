# Dummy crypto performance and hardening audit

As of 2026-07-10. This report separates broad forecast calibration from the
orders that actually filled. It does not authorize live trading.

## Initial baseline weakness

- Seven witnessed crypto fills had settled; all seven lost, for `-267c`.
- On those decisions, Dummy ensemble Brier was `0.316213` versus `0.225746`
  for the contemporaneous market midpoint.
- `crypto_spot_vol` and `crypto_ewma_t` were `0.999714` correlated across
  10,234 paired settled markets. They consumed the same Coinbase history but
  were treated as independent precision.
- 189,710 historical model rows reported uncertainty below 8%. Most stored
  one-hour return-distribution sigma (often 0.2%-0.4%) as if it were epistemic
  probability uncertainty. This overstated fusion confidence.
- Five of the seven filled losses came from decisions with less than 5%
  market-prior share.
- The same hourly BTC market was entered twice before settlement and both
  fills lost.

## Incumbent corrections now active

1. Crypto probability-model uncertainty has an 8% floor and retains horizon
   return sigma as a separately named feature.
2. Coinbase flat-vol and EWMA-tail models are pooled as one information
   family. Family precision is the strongest member, not the sum.
3. Crypto forecasts retain at least 25% market-prior share.
4. Fused uncertainty includes cross-source disagreement.
5. Crypto orders require at least 8 cents of conservative fee-adjusted EV and
   cannot buy above 75 cents.
6. The risk brain refuses to pyramid into a market with an existing open
   order or filled position.
7. Crypto source caches reset each cycle so a continuous daemon cannot reuse
   stale spot and volatility.
8. Crypto maker leases expire after one minute. Historical witness-time
   censoring retained six witnessed fills but reduced settled loss exposure
   from `-302c` at 20 minutes to `-112c` at one minute; the diagnostic does not
   invent fills and the retained record is still unprofitable.

On the current 29-order history, the combined `EV>=8c`, `price<=75c`, and
no-repeat-market filter retains 17 observed orders, three witnessed/settled
fills, and `-118c` rather than `-302c`. It is a filtering diagnostic only and
does not invent replacement opportunities.

## Current operating evidence

- Nine witnessed crypto fills have settled; all nine lost, for `-302c`.
- Fill-conditioned ensemble Brier is `0.263303` versus `0.182919` for the
  contemporaneous market, so operational selection remains worse than the
  market despite strong full-surface calibration.
- The full decision surface has 632 settled snapshots across 48 event
  clusters, 38.11% Brier skill versus market, and 2.27% ECE.
- Leakage-resistant walk-forward threshold selection reports 389 descriptive
  midpoint/taker trades, `+4849c`, and 19.05% ROI; it does not prove resting
  maker fills.
- No new order has been emitted since the hardened policy became active. The
  collector remains shadow-only and simulation-training status is `HOLD`.

## Indicator and distribution challengers

### `crypto_empirical_regime`

Weighted non-overlapping historical simulation at the contract horizon.
Minute blocks are used below 45 minutes; hourly blocks are used otherwise.
It directly counts threshold/bucket outcomes in historical return blocks with
Jeffreys smoothing. Logged indicators include:

- 5/15/60-minute momentum;
- RSI(14) and MACD(12,26);
- 60-minute and seven-day annualized realized volatility;
- short/long volatility regime ratio;
- 15-minute volume surge;
- Coinbase top-book imbalance and microprice basis;
- Coinbase/Kraken spot divergence;
- Deribit DVOL.

### `crypto_dvol_implied`

Maps current Deribit DVOL to a driftless lognormal strike/bucket probability,
with a 12% minimum probability-model uncertainty. This tests whether options-
implied volatility beats backward-looking realized volatility at the horizons
Dummy trades.

### `crypto_technical_composite`

Converts the logged technical state into an auditable directional score using
fixed, bounded research priors. Live inputs include 5/15/60-minute momentum,
RSI, MACD, volume confirmation, top-book imbalance, microprice, and four-hour
context. Historical replay uses only hourly momentum/RSI/MACD and labels that
lower-resolution path. The score can shift the distribution center by at most
0.45 horizon standard deviations; missing inputs increase uncertainty rather
than being renormalized away.

All three sources set `challenger_only=true`. They are stored and graded but the
forecaster excludes them. None can change weights, orders, risk, canary, or
scale.

Public reads use official endpoints: [Coinbase Exchange candles](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles),
[Coinbase product book](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-book),
[Kraken ticker](https://docs.kraken.com/api/docs/rest-api/get-ticker-information/),
and [Deribit volatility index data](https://docs.deribit.com/#public-get_volatility_index_data).

## Accelerated point-in-time training

All challengers can be appended to existing immutable settlements using only
Coinbase/Deribit candles fully closed before the historical decision. The
initial 250-market cap mostly sampled adjacent strikes from the same expiries,
so a diversified 30-day, 5,000-per-series replay was also run. Current results:

- empirical: 11,600 settled, 1,408 contested, 42 expiry clusters, lower-95%
  contested Brier advantage `0.070510`;
- technical composite: 11,600 settled, 1,418 contested, 42 expiry clusters,
  lower-95% advantage `0.064344`;
- DVOL: 11,600 settled, 1,422 contested, 44 expiry clusters, lower-95%
  advantage `0.060249`;
- all three now have 526 independently live-settled markets, but only two live
  expiry clusters versus the ten-cluster minimum.

They therefore remain quarantined. Retro breadth cannot substitute for live
forward evidence.

## Promotion gate

A crypto challenger requires all of:

- 500 settled markets;
- 100 contested markets;
- 20 contested event clusters;
- positive lower-95% contested Brier advantage;
- 100 independently live-settled markets;
- 10 independently live event clusters.

Even then, the report says `ready_for_explicit_fusion_review`; it never
auto-promotes. A bounded shadow experiment and verified settled-fill evidence
remain necessary before execution changes.
