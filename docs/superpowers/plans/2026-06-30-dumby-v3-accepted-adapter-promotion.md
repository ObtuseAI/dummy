# DUMBY_V3_ACCEPTED_ADAPTER_PROMOTION_STRATEGY_EXTRACTION_AND_LIVE_KALSHI_WIRING_V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote the 64 accepted V2 adapters, convert 44 repo-derived strategy candidates into Dummy-native TradeProposal-only modules, wire live Kalshi read paths, build the autonomous live capped execution chain, upgrade the dashboard, and prove all safety properties with tests and reports.

**Architecture:** Reuse the existing `DummyAdapter`/`StrategyGenome` abstractions, the `LiveBrokerFirewall` single-chokepoint order path, and the `incorporation_registry.json` gating mechanism. New code is organized into focused modules (`repo_harvester/promotion_engine.py`, `strategies/repo_derived/`, `kalshi/live_data.py`, `execution/autonomous_path.py`, dashboard v3 endpoints/screens, and dedicated test files). Every adapter and strategy is read-only or proposal-emitting; live orders continue to flow only through `LiveBrokerFirewall.submit`.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, httpx, pytest-asyncio, React + Vite dashboard, local JSON/SQLite state.

## Global Constraints

- Do not rebuild Dummy from scratch.
- Do not modify canonical Blunder (`C:/src/engine/obtuse/blunder`).
- Do not weaken the Live Broker Firewall (`live_firewall/firewall.py`).
- Do not add a paper-trading ladder.
- Do not rerun broad repo discovery unless needed.
- Use existing V2 source-scan artifacts as authority.
- All repo-derived adapters must emit Dummy-native ontology objects (`Forecast`, `TradeProposal`, etc.).
- No repo-derived adapter or strategy may call Kalshi/Polymarket live order endpoints directly.
- Only `LiveBrokerFirewall.submit` may call the broker client for live orders.
- Limit orders only; market orders are forbidden.
- Caps are read from `configs/caps.json`; Dummy code must not modify active caps.
- API credentials are loaded from `.env` or local secret manager only and must be redacted in logs/reports.
- Target mode is `AccountMode.AUTONOMOUS_LIVE_CAPPED`.
- Required reports must land in `artifacts/dummy/`.

## File Structure

### New files

- `repo_harvester/promotion_engine.py` — load accepted adapters, split into categories, build promotion records, generate per-adapter tests.
- `repo_harvester/adapter_test_generator.py` — generate the six required test types for promoted adapters.
- `adapters/promoted/` — lightweight adapter modules for promoted adapter targets (one per accepted repo-derived adapter target). These are stubs/wrappers that expose `to_native_forecast` and do NOT call live order endpoints.
- `strategies/repo_derived/` — native strategy modules for the eight required families.
- `kalshi/live_data.py` — live Kalshi read client wrapper with secret redaction.
- `kalshi/submitter.py` — thin limit-order submitter used exclusively by `LiveBrokerFirewall`.
- `execution/autonomous_path.py` — end-to-end autonomous execution orchestrator.
- `dashboard/backend/v3_routes.py` — new v3 endpoints (adapters, Kalshi status, markets/orderbooks, strategies, trades, blocked reasons, firewall verdicts, caps, positions/exposure).
- `dashboard/frontend/src/v3/` — new React components for v3 dashboard screens.
- `tests/test_adapter_promotion.py` — adapter promotion tests.
- `tests/test_repo_strategies.py` — repo-derived strategy tests.
- `tests/test_live_kalshi.py` — live Kalshi read tests (skipped if no creds).
- `tests/test_autonomous_path.py` — autonomous live capped path tests.
- `tests/test_no_direct_order_bypass.py` — static + runtime proofs that no strategy/adapter calls live order endpoints.
- `tests/test_secret_redaction.py` — secret redaction tests.
- `tests/test_blunder_separation.py` — Blunder separation recheck.

### Modified files

- `repo_harvester/incorporation_engine.py` — add `approve_adapter_tests`, `get_allowed_adapter_names` already exists; ensure promoted adapters move from `pending_tests` to `incorporated` only when their generated tests pass.
- `repo_harvester/incorporation_registry.json` — updated by promotion engine.
- `strategies/registry.py` — register repo-derived strategies.
- `dashboard/backend/main.py` — include v3 routes.
- `kalshi/client.py` — add `get_events`, ensure all read methods redact secrets.
- `core/secret_guard.py` — extend redaction patterns if needed.

## Workstream Decomposition

The work is split into parallel workstreams. Each workstream is implemented by a dedicated subagent. Shared integration points are explicit below.

### Workstream 1: Adapter Promotion Engine and Reports

**Deliverables:**
- `repo_harvester/promotion_engine.py`
- `repo_harvester/adapter_test_generator.py`
- `adapters/promoted/__init__.py`
- `adapters/promoted/*.py` (one lightweight module per accepted adapter target)
- `tests/test_adapter_promotion.py`
- `artifacts/dummy/adapter_promotion_report_v1.json`
- `artifacts/dummy/adapter_test_report_v1.json`
- Updated `repo_harvester/incorporation_registry.json`

**Inputs:** `artifacts/repo_harvester/adapter_plan_v3.json`

**Behavior:**
1. Load the 64 accepted plans.
2. Split by verdict into:
   - `direct_dependency_candidates` (verdict `DIRECT_DEPENDENCY_CANDIDATE`)
   - `adapter_targets` (verdict `ADAPTER_TARGET`)
   - `reference_only_strategy_mines` (verdict `REFERENCE_MINE`)
3. For each accepted adapter, create a promotion record with:
   - repo name
   - category
   - detected capabilities (from scan_summary hit categories)
   - detected risks (direct_order, kalshi_order, polymarket_order, private_key, api_secret hits)
   - required tests list
   - permitted Dummy interface (`to_native_forecast`, data transformation only)
   - forbidden live-order paths (Kalshi/Polymarket order endpoints)
4. Generate a lightweight adapter module under `adapters/promoted/` for each `ADAPTER_TARGET` plan. The module must:
   - subclass `DummyAdapter`
   - implement `to_native_forecast(self, raw) -> Forecast`
   - not import or call any live order endpoint
   - include a `FORBIDDEN_PATHS` class attribute listing forbidden patterns
5. Generate tests for each promoted adapter class covering:
   - import test
   - schema conversion test (mock raw input -> native Forecast)
   - no-secret-leak test (module source scanned by inherited secret sentinel)
   - no-direct-order-path test (AST/static check that no Kalshi/Polymarket order functions are called)
   - firewall-routing test (adapter outputs are consumed by forecast/strategy, not by live order code)
   - rejected-repo-isolation test (a rejected adapter name is blocked by firewall)
6. Keep adapters whose tests have not been explicitly approved in `pending_tests`.
7. Move adapters whose generated tests pass into `incorporated` (set `tests_passed: true`).
8. Write `adapter_promotion_report_v1.json` and `adapter_test_report_v1.json`.

**Interfaces:**
- `promotion_engine.load_accepted_plans() -> list[dict]`
- `promotion_engine.build_promotion_records() -> dict`
- `promotion_engine.generate_promoted_adapter_modules() -> list[str]`
- `adapter_test_generator.generate_tests(adapter_records) -> str` (returns test file content or writes file)
- `adapters.promoted.<name>.<Name>Adapter.to_native_forecast(raw) -> Forecast`

**Testing:** Run `pytest tests/test_adapter_promotion.py -v` and expect all promoted adapter tests to pass.

### Workstream 2: Repo-Derived Strategy Modules

**Deliverables:**
- `strategies/repo_derived/kalshi_weather_forecast.py`
- `strategies/repo_derived/sports_momentum.py`
- `strategies/repo_derived/crypto_event_market.py`
- `strategies/repo_derived/stock_macro_momentum.py`
- `strategies/repo_derived/commodities_energy.py`
- `strategies/repo_derived/cross_market_arbitrage.py`
- `strategies/repo_derived/orderbook_spread_capture.py`
- `strategies/repo_derived/stale_quote_detection.py`
- `strategies/repo_derived/__init__.py`
- Updated `strategies/registry.py`
- `tests/test_repo_strategies.py`
- `artifacts/dummy/strategy_module_report_v1.json`

**Inputs:** `artifacts/repo_harvester/strategy_extraction_report_v1.json`

**Behavior:**
1. Create one strategy module per required family.
2. Each strategy subclasses `StrategyGenome` and implements `evaluate(self, forecast, orderbook) -> Optional[TradeProposal]`.
3. Each strategy emits `TradeProposal` only and never calls live order endpoints.
4. Each returned `TradeProposal` includes:
   - no-trade explanation (when returning None)
   - forecast reference
   - edge estimate
   - confidence estimate
   - liquidity estimate
   - spread estimate
   - settlement-risk estimate
   - cancellation condition
   - cap impact
   - compliance verdict
   - proof reference
5. Update `strategies/registry.py` to include the new repo-derived strategies.
6. Write `strategy_module_report_v1.json` listing modules, families, source repos, and proof that they emit TradeProposal only.

**Interfaces:**
- `strategies.repo_derived.<family>.<Class>.evaluate(forecast, orderbook) -> Optional[TradeProposal]`

**Testing:** Run `pytest tests/test_repo_strategies.py -v`.

### Workstream 3: Live Kalshi Wiring

**Deliverables:**
- `kalshi/live_data.py`
- `kalshi/submitter.py`
- Updated `kalshi/client.py`
- Updated `core/secret_guard.py`
- `tests/test_live_kalshi.py`
- `artifacts/dummy/live_kalshi_wiring_report_v1.json`

**Inputs:** `configs/caps.json`, `.env` or `gh auth token` / secret manager for credentials.

**Behavior:**
1. Add a `KalshiLiveData` class that wraps `KalshiClient` and exposes async methods:
   - `get_events()`
   - `get_markets()`
   - `get_orderbook(ticker)`
   - `get_account_balance()`
   - `get_positions()`
   - `get_resting_orders()`
   - `get_fills()`
2. All credentials are loaded via `os.environ` (populated from `.env` or secret manager). Never hardcode secrets.
3. Redact secrets in logs, exception messages, and report payloads. Extend `core/secret_guard.py` with a `redact(text: str) -> str` helper if it does not exist.
4. `kalshi/submitter.py` provides a `KalshiSubmitter` class with a single async method `submit_limit_order(order: dict)`. It is a thin wrapper around `KalshiClient.create_order` and is the only component other than `LiveBrokerFirewall` that should call it.
5. `KalshiSubmitter` enforces `type == "limit"` and rejects market orders.
6. Respect caps from `configs/caps.json` (read-only).
7. Write `live_kalshi_wiring_report_v1.json` with connection status, redaction proof, and endpoint coverage.

**Interfaces:**
- `kalshi.live_data.KalshiLiveData`
- `kalshi.submitter.KalshiSubmitter.submit_limit_order(order) -> dict`
- `core.secret_guard.redact(text) -> str`

**Testing:** Run `pytest tests/test_live_kalshi.py -v`. Tests must skip live API calls when `KALSHI_API_KEY_ID` is missing, but still test redaction and order-type enforcement.

### Workstream 4: Autonomous Live Capped Execution Path

**Deliverables:**
- `execution/autonomous_path.py`
- `tests/test_autonomous_path.py`
- `artifacts/dummy/autonomous_live_capped_path_report_v1.json`
- `artifacts/dummy/firewall_order_path_report_v1.json`

**Inputs:** Workstream 2 strategies, Workstream 3 live data, existing `LiveBrokerFirewall`, `ForecastEngine`, risk/compliance governors.

**Behavior:**
1. Implement `AutonomousExecutionPath` class with async method `run_cycle(market_ticker, contract_ticker)`.
2. Chain:
   - live Kalshi market data (`KalshiLiveData`)
   - forecast engine (`ForecastEngine`)
   - strategy candidate (repo-derived strategy)
   - `TradeProposal`
   - risk verdict (`risk.governor.assess_trade_risk`)
   - compliance verdict (`compliance.governor.assess_compliance`)
   - firewall verdict (`LiveBrokerFirewall.evaluate`)
   - capped limit order request (`LiveOrderRequest`)
   - Kalshi submitter via firewall (`LiveBrokerFirewall.submit`)
   - order reconciliation
   - fill reconciliation
   - proof ledger write (`proof.ledger.write_proof`)
3. The path only operates when `STATE.mode == AccountMode.AUTONOMOUS_LIVE_CAPPED`.
4. `LiveBrokerFirewall.submit` remains the single live order chokepoint.
5. Generate `firewall_order_path_report_v1.json` proving every live order path goes through `LiveBrokerFirewall.submit` (static analysis + runtime test proof).
6. Generate `autonomous_live_capped_path_report_v1.json` documenting the chain, mode gating, cap respect, and proof ledger integration.

**Interfaces:**
- `execution.autonomous_path.AutonomousExecutionPath.run_cycle(...) -> dict`

**Testing:** Run `pytest tests/test_autonomous_path.py -v`.

### Workstream 5: Dashboard Backend v3

**Deliverables:**
- `dashboard/backend/v3_routes.py`
- Updated `dashboard/backend/main.py`
- `tests/test_backend_v3.py`

**Behavior:**
1. Add endpoints:
   - `GET /adapters` — accepted adapters, pending tests, rejected adapters.
   - `GET /adapters/pending` — pending adapter tests.
   - `GET /adapters/rejected` — rejected adapters.
   - `GET /kalshi/status` — live connection status, balance, positions, resting orders, fills.
   - `GET /kalshi/markets` — live markets/events (cached or mocked if no creds).
   - `GET /kalshi/orderbook/{ticker}` — live orderbook.
   - `GET /strategies/candidates` — repo-derived strategy candidates.
   - `GET /proposed-trades` — current proposed trades.
   - `GET /blocked-orders` — blocked order reasons.
   - `GET /firewall/verdicts` — recent firewall verdicts.
   - `GET /caps` — current caps.
   - `GET /exposure` — current positions and exposure.
2. Ensure existing `/status`, `/risk`, etc. continue to work.

**Testing:** Run `pytest tests/test_backend_v3.py -v`.

### Workstream 6: Dashboard Frontend v3

**Deliverables:**
- `dashboard/frontend/src/v3/AdaptersPanel.tsx`
- `dashboard/frontend/src/v3/KalshiStatusPanel.tsx`
- `dashboard/frontend/src/v3/StrategyCandidatesPanel.tsx`
- `dashboard/frontend/src/v3/ProposedTradesPanel.tsx`
- `dashboard/frontend/src/v3/BlockedOrdersPanel.tsx`
- `dashboard/frontend/src/v3/FirewallVerdictsPanel.tsx`
- `dashboard/frontend/src/v3/CapsExposurePanel.tsx`
- Updated `dashboard/frontend/src/App.tsx` to include v3 screens.
- `artifacts/dummy/dashboard_v3_report_v1.json`

**Behavior:**
1. Create React components that consume the v3 backend endpoints.
2. Components display: accepted/pending/rejected adapters, live Kalshi status, markets/orderbooks, strategy candidates, proposed trades, blocked order reasons, firewall verdicts, caps, positions/exposure.
3. Ensure `npm run build` succeeds.

**Testing:** Run `cd dashboard/frontend && npm run build`.

### Workstream 7: Safety Proofs and Tests

**Deliverables:**
- `tests/test_no_direct_order_bypass.py`
- `tests/test_secret_redaction.py`
- `tests/test_blunder_separation.py`
- `artifacts/dummy/no_direct_order_bypass_report_v1.json`
- `artifacts/dummy/no_secret_leak_report_v2.json`
- `artifacts/dummy/blunder_separation_recheck_v1.json`

**Behavior:**
1. `test_no_direct_order_bypass.py`:
   - Statically scan all `adapters/promoted/` and `strategies/repo_derived/` modules for imports/calls to Kalshi/Polymarket live order endpoints.
   - Assert no such calls exist.
   - Assert only `LiveBrokerFirewall.submit` (and `KalshiSubmitter` called from it) invokes `create_order`.
   - Write `no_direct_order_bypass_report_v1.json`.
2. `test_secret_redaction.py`:
   - Verify `core.secret_guard.redact` masks `KALSHI_API_KEY_ID`, `KALSHI_API_PRIVATE_KEY`, and similar patterns.
   - Verify logs/reports do not contain raw secrets.
   - Write `no_secret_leak_report_v2.json`.
3. `test_blunder_separation.py`:
   - Re-check that canonical Blunder (`C:/src/engine/obtuse/blunder`) is unmodified.
   - Re-check Dummy separation.
   - Write `blunder_separation_recheck_v1.json`.

**Testing:** Run these test files individually and verify PASS.

### Workstream 8: Final Integration, Reports, and Validation

**Deliverables:**
- `artifacts/dummy/final_report.json`
- `artifacts/dummy/tests_summary.json`
- Updated todo list / progress ledger

**Behavior:**
1. Run full pytest suite.
2. Run dashboard build.
3. Collect counts: accepted adapters, promoted adapters, pending adapters, rejected adapters, strategy modules, live Kalshi read status, autonomous path status, firewall status, Blunder separation status.
4. Write `tests_summary.json`.
5. Write `final_report.json` with PASS/PARTIAL/FAIL verdict, exact files changed, tests run, counts, proof paths, and remaining risks.

**Dependencies:** All other workstreams.

## Execution Notes

- Each workstream should create/modify only its assigned files unless shared files are explicitly listed.
- When modifying `strategies/registry.py` or `dashboard/backend/main.py`, append new registrations/import statements to avoid merge conflicts.
- All new Python files must include type hints and use Pydantic v2 where appropriate.
- All new tests must use pytest and follow the existing async test pattern (`pytest.mark.asyncio`).
- Reports must be valid JSON and include `generated_at` ISO timestamp.
