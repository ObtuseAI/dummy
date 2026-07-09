# Dummy V9 Concurrent Predator Mesh — Design

## Status
Design derived from operator specification `DUMMY_V9_CONCURRENT_PREDATOR_MESH_RECURSIVE_DATA_INFLOW_AND_EDGE_ORCHESTRATION_V1`. Approved implicitly by operator initiation under auto-permission mode.

## Authority
Builds on V8.2 PASS state:
- 895 passed, 2 skipped
- Dashboard build PASS
- DeepSeekV4Flash / MinimaxM3 LIVE_PROVEN through OpenRouter
- Kalshi READ_ONLY PASS
- Live-submit disabled
- Prompt/output firewall PASS
- No provider credential leak
- No direct order bypass

## Goal
Add a bounded concurrent autonomous intelligence mesh that runs multiple intelligence lanes at once, recursively widens the public/allowed data inflow surface, normalizes signals into Dummy ontology, detects asymmetric edge, scores signal bloodlines, routes high-value signals into forecast/strategy/governor loops, and continuously proves or starves signal sources — without weakening the Live Broker Firewall or enabling live order submission.

## Core Doctrine
Many eyes. One ontology. One proof ledger. Many signal hunters. One aggression governor. One Live Broker Firewall. Continuous learning. Dynamic opportunity capture.

## Design Principles
1. **Bounded concurrency, not a mega-loop.** Each lane has its own timeout and budget; the scheduler caps total concurrency and cycle time.
2. **No live orders.** All execution intent terminates at `LiveBrokerFirewall.submit_rehearsal()` unless `configs/live_submit.json` is explicitly enabled.
3. **No secret leakage to LLMs.** Prompts are sanitized through `PromptFirewallV2`; outputs are gated by `ModelOutputFirewall`.
4. **Deterministic degradation.** If a model/provider/source fails, the lane degrades; deterministic/statistical lanes continue.
5. **Proof-backed decisions.** Every promotion, pruning, edge generation, and rejection writes a proof reference.
6. **Public/allowed data only.** No unauthorized scraping, no private/insider data.
7. **Minimal viable pass.** Use mock/sample adapters where live connections are not already proven; real calls only where bounded and safe.

## Subsystems

### 1. Concurrent Predator Mesh Scheduler
- Dataclasses: `MeshLane`, `MeshTask`, `MeshRun`, `MeshBudget`, `MeshPriority`, `MeshHeartbeat`, `MeshTimeout`, `MeshResult`, `MeshProofRef`
- Lifecycle states: `READY`, `RUNNING`, `DEGRADED`, `BLOCKED`, `TIMED_OUT`, `COMPLETED`, `QUARANTINED`
- Priority levels: `realtime_market_terrain`, `high_value_signal`, `forecast_update`, `strategy_review`, `calibration_update`, `source_discovery`, `maintenance`
- Bounded execution: per-lane timeout, total cycle timeout, max concurrency, max provider calls per cycle, max Kalshi read-only calls per cycle, stuck-task killer, no unbounded subprocess
- Reports: `concurrent_predator_mesh_report_v1.json`, `mesh_scheduler_report_v1.json`, `mesh_timeout_guard_report_v1.json`

### 2. Mesh Lanes (ten bounded workers)
A. **Kalshi terrain lane** — READ_ONLY market/orderbook/event/position-safe summaries → `MarketTerrainSnapshot`
B. **Recursive data inflow lane** — discover/public sources → `DataSourceCandidate`
C. **Signal normalization lane** — convert to Dummy-native ontology → `NormalizedSignal`
D. **Anomaly mining lane** — detect edge anomalies → `EdgeAnomaly`
E. **Forecast update lane** — DeepSeek fast pass + Minimax critique → `ForecastOpinion`
F. **Strategy intelligence lane** — run strategy families → `TradeProposalDraft` / `NoTradeReason`
G. **Strategy governor lane** — route to `StrategyGovernor` → governor decision
H. **Firewall rehearsal lane** — call `LiveBrokerFirewall.submit_rehearsal()` only
I. **Calibration lane** — track forecast/source quality → `CalibrationUpdate`
J. **Mesh health lane** — detect stuck/slow/noisy lanes → `MeshHealthReport`

Reports: `mesh_lane_registry_report_v1.json`, `mesh_lane_execution_report_v1.json`

### 3. Recursive Data Inflow Mesh
- Dataclasses: `DataSourceCandidate`, `DataSourceRegistry`, `DataSourceScore`, `SourceReliabilityProfile`, `SourceFreshnessProfile`, `SourceLatencyProfile`, `SourceUniquenessScore`, `SourceEdgeContribution`, `SourcePromotionDecision`, `SourcePruningDecision`
- Source categories: Kalshi data, weather, sports, crypto/BTC, macro calendar, stocks/indices, commodities, public news, government datasets, forecasting platforms, prediction-market cross-prices, public sentiment, liquidity shifts, historical archives
- Behavior: registry, scoring, normalization path, safe adapters; mock/sample data where live is not yet proven
- Reports: `recursive_data_inflow_mesh_report_v1.json`, `data_source_registry_report_v1.json`, `data_source_scoring_report_v1.json`, `source_promotion_pruning_report_v1.json`

### 4. Signal Ontology
- Dataclasses: `NormalizedSignal`, `SignalType`, `SignalStrength`, `SignalFreshness`, `SignalConfidence`, `SignalSourceRef`, `SignalProofRef`, `SignalEdgeContribution`, `SignalDecay`, `SignalConflict`
- Signal types: price_move, orderbook_shift, liquidity_change, spread_change, external_event, weather_update, sports_update, crypto_volatility, macro_calendar, settlement_rule, cross_market_price, sentiment_shift, anomaly, no_trade_warning
- Reports: `signal_ontology_report_v1.json`, `signal_normalization_report_v1.json`

### 5. Edge Intelligence Engine
- Dataclasses: `EdgeCandidate`, `EdgeHypothesis`, `EdgeScore`, `EdgeDecay`, `EdgeConfidence`, `EdgeConflict`, `EdgeProofTrail`, `EdgePromotionDecision`
- Scoring dimensions: probability_delta, liquidity_quality, spread_quality, freshness_advantage, source_reliability, source_uniqueness, model_agreement, model_disagreement, calibration_support, settlement_risk, execution_feasibility, cap_impact, no_trade_pressure
- Decisions: `ATTACK_REHEARSAL`, `WATCH`, `REQUIRE_MORE_EVIDENCE`, `REQUIRE_MINIMAX_REVIEW`, `NO_TRADE`, `STARVE_SIGNAL`, `QUARANTINE_SOURCE`
- Reports: `edge_intelligence_engine_report_v1.json`, `edge_candidate_manifest_v1.json`, `edge_decision_report_v1.json`

### 6. Hybrid Model Integration
- Reuse V8.2 route/resolution: DeepSeekV4Flash fast tactical, MinimaxM3 deeper critique via OpenRouter
- Prompt firewall V2 + output firewall on every model call
- Degradation: if model fails, lane degrades but mesh continues; deterministic lanes keep running
- Reports: `mesh_hybrid_model_routing_report_v1.json`, `mesh_model_failure_degradation_report_v1.json`

### 7. Proof-Weighted Aggression Governor
- Inputs: edge score, source quality, forecast confidence, model agreement/disagreement, calibration support, liquidity/spread quality, settlement risk, cap impact, no-trade pressure, timeout pressure, source decay, strategy governor output
- Outputs: increase/decrease attention, require evidence, require Minimax review, starve/promote/quarantine source, approve firewall rehearsal, no trade
- Reports: `proof_weighted_aggression_governor_report_v1.json`, `aggression_allocation_manifest_v1.json`

### 8. Continuous Proof Ledger
- Hook every lane lifecycle event, source promotion/pruning, edge generation/rejection, forecast update, governor decision, firewall rehearsal verdict, model digest, no-secret check, no-order-bypass check
- Report: `mesh_proof_ledger_report_v1.json`

### 9. Dashboard V9
- New routes in `dashboard/backend/v9_routes.py`: `/api/v9/mesh/status`, `/api/v9/mesh/lanes`, `/api/v9/data-inflow/sources`, `/api/v9/signals`, `/api/v9/edges`, `/api/v9/aggression-governor`, `/api/v9/mesh-health`, `/api/v9/proof`
- Redacted views: lane status, timeouts, provider mode, source/edge scores, no-trade reasons, aggression allocation, proof paths, live-submit disabled status
- Report: `dashboard_v9_report_v1.json`

## Integration Points
- Mesh scheduler imports from `model_router.router.ModelRouter` for hybrid model calls.
- Forecast lane reuses `forecasting.hybrid_engine.HybridForecastEngine`.
- Strategy lanes reuse `strategies.governor.StrategyGovernor` and `strategies.disagreement.HybridDisagreementEngineV2`.
- Firewall rehearsal lane calls `live_firewall.firewall.LiveBrokerFirewall.submit_rehearsal()`.
- Kalshi terrain lane uses existing READ_ONLY adapters in `kalshi/`.
- Reports follow `scripts/generate_v8_2_reports.py` pattern: async main, `_write_report`, versioned JSON, redacted metadata, `verdict` field.

## Testing Strategy
- Add 28 tests under `tests/` covering scheduler, lanes, timeouts, stuck-task killer, data inflow, source scoring, signal ontology, edge engine, hybrid routing, model degradation, aggression governor, proof ledger, dashboard V9, secret leak, LLM secret leak, live-submit disabled, direct order bypass, Kalshi READ_ONLY, timeout guards, Blunder separation, Dummy canonical identity.
- All tests use `clean_env`/`no_project_env` fixtures where credentials matter.
- No recursive pytest; no unbounded network calls in unit tests.

## Regression Validation
```bash
python -m pytest tests/ -vv -s --tb=short --maxfail=1 --durations=25 --timeout=60
python -m pytest tests/ -q --tb=short --timeout=60
cd dashboard/frontend && npm run build
python scripts/generate_v8_reports.py
python scripts/generate_v8_1_reports.py
python scripts/generate_v8_2_reports.py
python scripts/generate_v9_reports.py
```

## Pass Criteria
- Tests pass
- Dashboard builds
- V8.2 live model proof remains PASS or degrades cleanly
- Kalshi READ_ONLY PASS
- Live-submit disabled
- No secrets leak
- No direct order bypass
- Mesh runs bounded lanes with timeouts
- Recursive data inflow registry/scoring works
- Signal ontology works
- Edge engine generates decisions
- Aggression governor works
- Firewall rehearsal blocked when live-submit disabled
- All required reports generated

## Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| Hanging lanes | Per-lane + cycle timeouts + stuck-task killer |
| Recursive pytest | Unit tests never run full pytest suite |
| Secret leak in LLM prompts | PromptFirewallV2 + output scanning in tests |
| Direct order bypass | Static tests + firewall rehearsal only |
| Live-submit enabled | Explicit check that `configs/live_submit.json` is untouched |
| Unauthorized data sources | Source registry only allows public/allowed categories; tests enforce |
| Blunder modification | `test_blunder_separation_v9.py` verifies no canonical Blunder files changed |
