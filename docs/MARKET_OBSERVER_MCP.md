# Dummy Market Observer MCP

`dummy-market-observer` is a local, read-only evidence sidecar for BTC, ETH,
and SOL. It exposes closed public candles, deterministic local indicators,
candlestick-pattern markers, chart bundles, and source health. It never exposes
orders, cancellations, account mutations, probabilities, capital allocation,
or promotion authority.

Run it over standard I/O:

```powershell
python -m autonomy.market_observer
```

An MCP client can use that command directly. Set
`DUMMY_MARKET_OBSERVER_ROOT` only when the immutable artifact root must live
somewhere other than `artifacts/dummy/market_observer`.

## Tools

- `get_candles`
- `get_market_snapshot`
- `compute_indicators`
- `detect_candlestick_patterns`
- `get_chart_bundle`
- `get_network_metrics`
- `source_health`

Assets are allowlisted to `BTC`, `ETH`, and `SOL`; timeframes are allowlisted
to `15m`, `1h`, `4h`, `1d`, and `1w`. Coinbase Exchange is the initial public
candle provider behind a provider-neutral interface. Network metrics return an
explicit `UNAVAILABLE` until a separately reviewed source is configured.

Every successful or failed tool call produces a content-addressed observation.
Only `COMPLETE` observations advance `LATEST.json`; degraded calls advance
`LATEST_FAILURE.json` and cannot overwrite the last valid snapshot.

Every source must carry a rights identifier, a terms-review identifier, the
reviewed terms URL, and `automated_use_permitted=true`. Sources without that
explicit permission fail contract construction. The initial Coinbase adapter
is bounded by the reviewed
[Coinbase Developer Platform Terms](https://www.coinbase.com/legal/developer-platform/terms-of-service),
including its API-call limits and prohibition on automated screen scraping.

The sidecar permits at most 30 provider requests per 60-second window by
default, opens its circuit after three consecutive provider failures, and
allows only one recovery probe after 60 seconds. A cross-process lock permits
one observer process per artifact root. These controls fail closed and never
sleep, retry, or increase their own limits.

## TradingView boundary

The sidecar does not connect to TradingView, a browser, cookies, alerts,
webhooks, or private/broker endpoints. Dummy's chart renderer may consume
`get_chart_bundle` output with the separately bundled TradingView Lightweight
Charts library, but the data remains independently sourced and locally
computed. This follows TradingView's own support statement that it
[does not provide an API for data or indicator values](https://www.tradingview.com/support/solutions/43000474413-i-need-access-to-your-api-in-order-to-get-data-or-indicator-values/).
Any configured endpoint, documentation URL, or terms URL containing a
TradingView hostname is rejected, and the Coinbase adapter additionally
requires the exact allowlisted HTTPS host `api.exchange.coinbase.com`.
