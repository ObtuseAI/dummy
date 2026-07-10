# Dummy open-source opportunity audit

As of 2026-07-09. The selection rule is capability gained per unit of runtime,
dependency, licensing, and live-trading risk. External execution libraries do
not bypass `LiveBrokerFirewall` and are not authorized to submit orders.

## Added in this review

| Addition | License / surface | What Dummy gained | Boundary |
|---|---|---|---|
| [Polymarket public CLOB orderbook](https://docs.polymarket.com/trading/orderbook) | Public unauthenticated API; official SDKs are MIT | `cross_venue_polymarket` now resolves the matched outcome token and uses its live best bid/ask midpoint, spread, and top-of-book depth. Gamma `outcomePrices` remains a fallback only. | GET-only; no wallet, credentials, order construction, or Polymarket execution path. |
| [Hypothesis](https://github.com/HypothesisWorks/hypothesis) | MPL-2.0; development only | Generated boundary tests for fee dominance, stale-fee fail-closed behavior, settlement-P&L bounds, and public-book midpoint invariants. | Optional `dev` extra; absent from runtime dependencies. |
| [River 0.25.0](https://github.com/online-ml/river) | BSD-3-Clause; `analytics` extra | ADWIN diagnostics on chronological decision-policy Brier excess, surfaced in reports/dashboard and as a scale blocker on confirmed negative drift. | Observational only; cannot reset weights, promote stages, or touch orders. |
| [OR-Tools 9.15](https://developers.google.com/optimization) | Apache-2.0; `optimizer` extra | CP-SAT portfolio challenger with budget, payout-sanity, unresolved-market, event-cluster, and count constraints. | `execution_authority=false`; no executor import or live-routing path. |
| [Polars 1.42](https://docs.pola.rs/api/python/stable/reference/api/polars.read_database.html) | MIT; `research` extra | Atomic, hash-manifested Parquet snapshots of the complete ledger. | SQLite is opened with `mode=ro` and `PRAGMA query_only=ON`. |
| [BLS Public Data API](https://www.bls.gov/developers/api_signature_v2.htm), [Deribit DVOL](https://docs.deribit.com/#public-get_volatility_index_data), [NWS API](https://www.weather.gov/documentation/services-web-api) | Public official APIs | Deduplicated macro, implied-volatility, and official station observations with units and time provenance. | Raw facts only; no probability or trust-weight conversion without later point-in-time backtesting. |
| [Kalshi public trades](https://docs.kalshi.com/api-reference/market/get-trades) | Official read-only market feed | Exact standard-book prints now witness strict limit-price trade-throughs and queue consumption; fixed-point books capture queue depth at submission. | Block trades excluded; no account data, credentials, order writes, or optimistic price improvement. |
| [Coinbase candles/book](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles), [Kraken ticker](https://docs.kraken.com/api/docs/rest-api/get-ticker-information/), and [Deribit DVOL](https://docs.deribit.com/#public-get_volatility_index_data) | Official public read-only APIs; no new package | Shared multi-venue crypto state, empirical horizon returns, momentum/RSI/MACD, realized-vol regimes, volume surge, top-book imbalance/microprice, venue divergence, and options-implied volatility challengers. | Indicator sources are `challenger_only`; logged and graded but excluded from fusion and execution. |

## Highest-value next additions

### 1. PMXT normalized venue schema — recommended as a read-only reference

- Source: [pmxt-dev/pmxt](https://github.com/pmxt-dev/pmxt), MIT.
- Capability: a CCXT-like event/market/outcome schema across Kalshi,
  Polymarket, and additional prediction venues.
- Integration: borrow/test the normalization contract or run the self-hosted
  core behind a read-only adapter. Do not send Dummy credentials to its hosted
  service and do not adopt its write API.
- Value: enables cross-venue price disagreement, venue-health comparison, and
  market-identity coverage without one bespoke model per venue.

### 2. Point-in-time macro forecast transformations

- Use the new BLS observation ledger to build release-calendar-aware CPI,
  payroll, unemployment, GDP, and Fed challengers.
- Require vintage/revision handling (ALFRED or equivalent) before historical
  tests; a latest-revised series is lookahead-contaminated.
- Add ECON watchlist series only after ticker-resolution rules, release timing,
  and probability mappings have settlement-backed tests.

### 3. `scoringrules` — recommended when continuous/multi-outcome markets expand

- Source: [frazane/scoringrules](https://github.com/frazane/scoringrules),
  Apache-2.0.
- Capability: CRPS, ranked probability score, energy score, and
  threshold-weighted scores beyond binary Brier/log loss.
- Constraint: current releases require Python 3.12+. Dummy supports 3.11, so
  use an environment marker or raise the project minimum only for a separate
  analytics extra.

## Useful references, not dependencies yet

| Material | Useful idea | Decision |
|---|---|---|
| [Polymarket official Python SDK](https://github.com/Polymarket/py-sdk), MIT | Typed public client and current API models | Beta. Evaluate for public reads only; never route writes around Dummy's firewall. |
| [Polymarket agent skill](https://github.com/Polymarket/agent-skills) | Compact Gamma/CLOB/Data/WebSocket reference | Do not install yet: no license file was visible and parts still point at the archived legacy Python client. Use official docs as authority. |
| [FutureShow](https://github.com/HKUDS/FutureShow), MIT | Per-model forecast trails, identical decision points, model-vs-market leaderboard | Borrow experiment/report shapes; its accuracy-first headline is weaker than Dummy's Brier, calibration, and fill-truth standards. |
| [skfolio](https://github.com/skfolio/skfolio), BSD-3-Clause | Purged CV, risk models, robust allocation, opinion pooling | Heavy equity-return assumptions/dependencies. Borrow validation ideas before adopting the package. |
| [Extremized probability pools](https://arxiv.org/abs/1501.06943) | Logit-space aggregation can outperform a plain average when sources have diverse information | Add only as a challenger with point-in-time fit and cluster-purged validation; never assume extremizing is universally beneficial. |

## Excluded or restricted

- [Metaculus API data](https://www.metaculus.com/api/) is not automatically
  ingested. Current terms state that AI/ML training or evaluation needs prior
  written permission, and commercial use needs a separate agreement.
- `netcal` is capable but pulls a large PyTorch/SciPy/scikit-learn stack for
  metrics Dummy now computes directly; its marginal value does not justify the
  runtime footprint.
- Generic equity backtest frameworks do not naturally model binary settlement,
  mutually exclusive outcomes, maker queue fills, or event-cluster exposure.
- Third-party Kalshi/Polymarket write clients are contract-test references only.
  Dummy's existing firewall remains the sole live submission boundary.

## Proposed sequence

1. Accumulate and grade the new CLOB-enriched cross-venue signal separately
   from its historical Gamma-only record (feature provenance already records
   the price source).
2. Extend ADWIN diagnostics to fill probability and realized P&L only after
   each ordered stream has adequate sample size.
3. Compare the OR-Tools challenger with the current allocator in a joint-payoff,
   point-in-time shadow replay before considering any promotion.
4. Add read-only PMXT normalization for a third venue only after exact market
   identity and resolution-rule matching tests exist.
5. Build revision-safe macro forecast challengers from the raw observation
   layer, preserving release timestamps and historical vintages.
