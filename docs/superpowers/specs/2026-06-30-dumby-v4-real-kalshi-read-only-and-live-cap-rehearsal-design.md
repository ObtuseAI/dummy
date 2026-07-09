# DUMBY_V4_REAL_KALSHI_READ_ONLY_INGESTION_AND_LIVE_CAP_FIREWALL_REHEARSAL_V1 — Design Spec

## Overview

Build on the existing V3 Dummy codebase to connect to real Kalshi account and market data in **READ_ONLY** mode, prove ingestion works without leaking secrets or creating orders, and run an **AUTONOMOUS_LIVE_CAPPED** firewall rehearsal using real market data while blocking real order submission unless an explicit operator-approved live-submit flag is present.

This milestone does **not** rebuild Dummy, modify canonical Blunder, weaken the firewall, add a paper-trading ladder, or expand the repo list. It treats the V3 adapter promotion, strategy extraction, and autonomous live capped path as authority.

## Goals

1. **Real Kalshi READ_ONLY ingestion**
   - Load Kalshi credentials from `.env` or local secret manager.
   - Redact all secrets before logging or reporting.
   - Connect to Kalshi in READ_ONLY mode.
   - Fetch account status, balance, events, markets, order books, positions, resting orders, and fills.
   - Prove no order endpoints are called in READ_ONLY mode.
   - Produce `real_kalshi_read_only_report_v1.json`.

2. **Real market data normalization**
   - Convert live Kalshi data into Dummy-native `Market`, `Event`, `Contract`, `OrderBook`, `Position`, `Fill`, and `ForecastInput` objects.
   - Validate schemas with Pydantic.
   - Reject malformed or stale data.
   - Produce `kalshi_normalization_report_v1.json`.

3. **Strategy pass over real market data**
   - Run the 8 repo-derived strategy families against real market snapshots.
   - Generate `TradeProposal` or no-trade explanations.
   - Do not submit live orders in this stage.
   - Record strategy family, market ticker, edge estimate, confidence, liquidity score, spread score, settlement-risk score, and no-trade reason or proposal summary.
   - Produce `real_market_strategy_scan_report_v1.json`.

4. **AUTONOMOUS_LIVE_CAPPED firewall rehearsal**
   - Build the full live capped execution path using real market data: Kalshi market data → forecast engine → strategy module → `TradeProposal` → risk verdict → compliance verdict → firewall verdict → limit order request.
   - Stop before actual submit unless `configs/live_submit.json` exists with `enabled: true`.
   - Prove oversized orders, market orders, unknown adapters, rejected repos, kill switch, emergency stop, stale data, missing proof, and cap violations are blocked.
   - Produce `live_cap_firewall_rehearsal_report_v1.json`.

5. **Dashboard V4**
   - Show real Kalshi connection status, account balance with redaction-safe formatting, real markets, real order books, positions, resting orders, strategy proposals/no-trade reasons, firewall rehearsal verdicts, blocked order reasons, and current caps.
   - Produce `dashboard_v4_report_v1.json`.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Kalshi Real READ_ONLY                        │
│  .env / secret manager → KalshiClient → KalshiRealReadOnly          │
│                                                   │                  │
│                    account | events | markets | orderbook |          │
│                    positions | resting orders | fills                │
│                                                   ▼                  │
│                        KalshiNormalizer                              │
│                                                   │                  │
│    Market | Event | Contract | OrderBook | Position | Fill |         │
│    ForecastInput                                                     │
│                                                   ▼                  │
│                        Strategy Repo-Derived Scan                    │
│                                                   │                  │
│              TradeProposal  or  No-Trade Explanation                 │
│                                                   ▼                  │
│                     Autonomous Live Cap Rehearsal                    │
│   forecast → risk → compliance → firewall → limit order request      │
│   live submit blocked unless configs/live_submit.json enabled=true   │
└─────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. `kalshi/live_data.py` — `KalshiRealReadOnly`

New class that wraps `KalshiClient` for real READ_ONLY ingestion.

Responsibilities:
- Load credentials from `os.environ` / `.env` (reusing existing `KalshiClient` / `KalshiSigner`).
- Provide async methods:
  - `get_account_status()` → account dict
  - `get_balance()` → balance dict
  - `get_events()` → list of events
  - `get_markets()` → list of markets
  - `get_orderbook(ticker)` → orderbook dict
  - `get_positions()` → list of positions
  - `get_resting_orders()` → list of orders
  - `get_fills()` → list of fills
- Redact all returned payloads with `core.secret_guard.redact` before logging or returning to callers.
- Track which endpoints were called; expose `endpoints_called()` for the no-order-in-read-only proof.
- Raise `KalshiCredentialsMissing` if credentials are absent so tests can skip gracefully.

### 2. `kalshi/normalizer.py` — `KalshiNormalizer`

Responsibilities:
- Convert raw Kalshi payloads into Dummy-native Pydantic models.
- Validate required fields and types.
- Reject stale order books (timestamp older than configurable threshold, default 60s).
- Reject malformed contracts/markets with missing `ticker`, `title`, or `status`.
- Expose:
  - `normalize_account(raw)` → `Account`
  - `normalize_events(raw)` → `list[Event]`
  - `normalize_markets(raw)` → `list[Market]`
  - `normalize_orderbook(ticker, raw)` → `OrderBook`
  - `normalize_positions(raw)` → `list[Position]`
  - `normalize_resting_orders(raw)` → `list[Order]`
  - `normalize_fills(raw)` → `list[Fill]`
  - `to_forecast_input(market, orderbook)` → `ForecastInput`

### 3. `strategies/repo_derived/` — unchanged strategy modules

The 8 existing strategy families run against normalized `ForecastInput` / `OrderBook` objects and return `TradeProposal | None`. No strategy code is modified; V4 only adds a scan orchestrator.

### 4. `execution/autonomous_path.py` — `rehearse_live_cap`

New method on `AutonomousExecutionPath`:

```python
async def rehearse_live_cap(
    self,
    market_ticker: str,
    contract_ticker: str,
    strategy_name: str | None = None,
) -> RehearsalResult:
    ...
```

Responsibilities:
- Verify mode is `AUTONOMOUS_LIVE_CAPPED`.
- Fetch real market data via `KalshiRealReadOnly`.
- Normalize via `KalshiNormalizer`.
- Run forecast engine and strategy scan.
- Run risk, compliance, and firewall gates.
- By default stop after `firewall.evaluate()` and record the would-be order and verdict.
- Only call `firewall.submit()` if `configs/live_submit.json` exists with `enabled: true`.
- Record proof via `proof.ledger.write_proof`.

### 5. `live_firewall/firewall.py` — live-submit gate and rehearsal mode

Add:
- `_live_submit_enabled()` reads `configs/live_submit.json` and returns `True` only if `enabled` is `true`, the file is valid JSON, and the timestamp is recent (within 24h).
- `submit_rehearsal(req, orderbook, forecast)` returns a `RehearsalVerdict` containing the firewall verdict and the order that would be submitted, without calling the broker.
- Keep `submit()` as the only real order path.

### 6. `configs/live_submit.json` — operator-approved live-submit flag

Template:

```json
{
  "enabled": false,
  "operator": "operator-id",
  "timestamp": "2026-06-30T18:54:51Z",
  "reason": "scheduled live rehearsal"
}
```

Default `enabled: false`. Dummy never modifies this file.

### 7. Dashboard V4

Backend (`dashboard/backend/v4_routes.py`):
- `/v4/kalshi/status`
- `/v4/kalshi/account`
- `/v4/kalshi/markets`
- `/v4/kalshi/orderbook/{ticker}`
- `/v4/kalshi/positions`
- `/v4/kalshi/orders`
- `/v4/kalshi/fills`
- `/v4/strategies/scan`
- `/v4/firewall/rehearse`
- `/v4/firewall/blocked`
- `/v4/caps`
- `/v4/live-submit/status`

Frontend:
- New screens: `KalshiReal`, `StrategyScan`, `FirewallRehearsal`, `LiveSubmit`.
- Update navigation in `App.jsx`.
- Reuse existing `useApi` hook.

## Data Flow

1. Operator starts Dummy in `AUTONOMOUS_LIVE_CAPPED` mode.
2. `KalshiRealReadOnly` loads credentials and fetches real data.
3. `KalshiNormalizer` converts and validates data.
4. Strategy scan evaluates each repo-derived family.
5. `AutonomousExecutionPath.rehearse_live_cap` runs risk/compliance/firewall gates.
6. If live-submit flag is disabled, the rehearsal stops and records the would-be order and block reason.
7. If live-submit flag is enabled, `LiveBrokerFirewall.submit` places a real limit order.

## Error Handling

- Missing credentials: skip real Kalshi tests, report `credentials_present: false`.
- Network errors: classify with `kalshi.error_classifier`, retry via `kalshi.rate_limiter`, record error category.
- Stale/malformed data: reject at normalizer, record rejection reason.
- Cap violations: rejected by firewall with explicit reason.
- Live-submit not enabled: rehearsal records `blocked_reason: live_submit_disabled`.

## Testing

- `tests/test_real_kalshi_read_only.py` — credential guard, endpoint coverage, secret redaction, no order endpoints in READ_ONLY mode.
- `tests/test_kalshi_normalizer.py` — schema validation, stale data rejection, malformed data rejection.
- `tests/test_real_market_strategy_scan.py` — 8 families evaluate against normalized snapshots, proposals/no-trade explanations recorded.
- `tests/test_live_cap_firewall_rehearsal.py` — rehearsal blocks by default, oversized/market/unknown adapter/rejected repo/kill switch/emergency stop/stale data/missing proof/cap violations all blocked.
- `tests/test_no_order_in_read_only.py` — static + runtime proof that no order endpoint is called in READ_ONLY.
- `tests/test_no_secret_leak_v3.py` — scan logs + artifacts for secrets.
- `tests/test_direct_order_bypass_v4.py` — static scan confirms only `live_firewall/firewall.py` and `kalshi/submitter.py` call `create_order`.
- `tests/test_backend_v4.py` — all `/v4/*` endpoints, redaction, caps read-only.
- `tests/test_blunder_separation_v2.py` — Dummy does not import from or modify canonical Blunder.
- Full pytest suite: `python -m pytest tests/ -v`.
- Dashboard build: `cd dashboard/frontend && npm run build`.

## Reports

All reports go to `artifacts/dummy/`:

- `real_kalshi_read_only_report_v1.json`
- `kalshi_normalization_report_v1.json`
- `real_market_strategy_scan_report_v1.json`
- `live_cap_firewall_rehearsal_report_v1.json`
- `dashboard_v4_report_v1.json`
- `no_order_in_read_only_report_v1.json`
- `no_secret_leak_report_v3.json`
- `firewall_rehearsal_regression_report_v1.json`
- `blunder_separation_recheck_v2.json`
- `tests_summary.json`
- `final_report.json`

## Safety Boundaries

- No Kalshi secrets logged or written to artifacts.
- No market orders created.
- No real live orders unless `configs/live_submit.json` has `enabled: true`.
- No strategy, adapter, forecast, or repo-derived module submits orders directly.
- All real order submission passes through `LiveBrokerFirewall.submit`.
- `configs/caps.json` remains operator-controlled and read-only for Dummy.
- Canonical Blunder remains unmodified and separate.
