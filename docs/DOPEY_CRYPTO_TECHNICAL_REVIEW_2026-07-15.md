# Dopey crypto technical-analysis review

## Decision

Dummy may reuse ideas and original source from
[`ObtuseAI/dopey`](https://github.com/ObtuseAI/dopey) because the repository's
original `dopey_*` code is MIT licensed. Vendored `_forked_blunder*` directories
and bundled market data are explicitly outside that grant and were not used.
The implementation in `autonomy/signals/crypto_ta_foundry.py` is a clean-room,
Dummy-native challenger over its existing public OHLCV cache.

No Dopey performance claim was imported. Dopey's own license notice describes
the project as paper-only and says its truth layer has no demonstrated trading
edge. Every adopted feature must earn settlement-backed evidence inside Dummy.

## Useful additions

Dopey reinforced five indicator families that were useful gaps beside Dummy's
existing momentum/RSI/MACD, volatility, market-structure, order-book, and
cross-venue stack:

- ATR-normalized momentum, so a price move is interpreted relative to current
  range rather than in raw dollars;
- Bollinger and stochastic price location, recorded as bounded state rather
  than treated as a guaranteed reversal rule;
- on-balance-volume slope and volume z-score, separating directional flow from
  simple volume surge;
- close-location value, which distinguishes strong and weak closes inside a
  candle; and
- volume-confirmed breakouts plus point-in-time failed-breakout/fakeout state.

The source requires at least 30 complete oldest-first candles, at least three
active primitives, and a minimum aggregate score. It selects minute, hourly, or
daily candles from decision-time hours-to-close, caps its distribution shift at
0.35 horizon sigma, widens uncertainty, logs all primitives, and is always
`challenger_only` with `promotion_eligible=false`.

## Ideas not duplicated

Dummy already had multi-timeframe support/resistance and channels, RSI/MACD,
realized/implied volatility regimes, microprice and order-book imbalance,
venue divergence, macro context, crypto-equity flow, and sparse structure
setups. Reimplementing those under new names would add correlated sources and
reward-hacking surface without independent information.

Dopey's options-specific gamma, sector-relative-strength, and equity volatility
risk-premium modules were also not transplanted into crypto. Their assumptions
do not map directly to BTC/ETH/SOL event contracts without a separately
validated crypto derivatives dataset.

## Promotion law

`crypto_technical_foundry` is graded independently by asset, contract family,
and horizon. BTC 15-minute evidence cannot promote ETH, hourly evidence cannot
promote daily, and a price-ladder head cannot promote a direction contract.
Autonomous search may reject, quarantine, contract, or demote the challenger.
Positive runtime promotion remains human-only after private, external, and
forward-paper gates.
