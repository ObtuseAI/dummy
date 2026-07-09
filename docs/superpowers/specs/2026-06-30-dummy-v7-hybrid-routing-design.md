# DUMMY_V7 Design Spec

## Goal

Install a DeepSeekV4Flash + MinimaxM3 hybrid model-routing layer on top of Dummy V6, then use it to improve real-market forecasting, strategy critique, calibration scoring, no-trade reasoning, and autonomous alpha-loop selection while preserving the Live Broker Firewall and keeping real live submit disabled unless explicitly armed.

## Authority

Dummy V6 is the authority:

- `artifacts/dummy/final_report.json` = PASS
- Real Kalshi credentials present
- Real Kalshi read-only path proven
- Dashboard built, tests pass
- Live-submit flag disabled, no live orders submitted

## Decisions

1. **Model API mode**: provider-agnostic clients with deterministic mock fallback. Real API calls are attempted only when env vars are present; otherwise the router falls back to mock responses and reports `PARTIAL` for live-model status. This satisfies "do not block the bundle if credentials are absent".
2. **Provider env vars**:
   - `DEEPSEEK_API_KEY` / `DEEPSEEK_API_BASE` (optional)
   - `MINIMAX_API_KEY` / `MINIMAX_API_BASE` (optional)
3. **Async throughout**: the router is async to fit existing `KalshiRealReadOnly`, `StrategyScanner`, and `LiveBrokerFirewall` patterns.
4. **No live orders from LLMs**: LLM outputs are limited to opinion/critique/draft value objects. Every trade must become a `TradeProposal` and pass risk/compliance/firewall gates.
5. **Calibration storage**: JSON files under `data/calibration/` and `artifacts/dummy/calibration/` to keep dependencies minimal; settlement backfill is opportunistic.
6. **Dashboard**: add a V7 screen alongside V6; V6 screen remains untouched.
7. **Reports**: create `scripts/generate_v7_reports.py` that builds on V6 reports and writes the V7 `final_report.json`.
8. **Decomposition**: V7 is implemented in four phases:
   - Phase A: Model router, prompt firewall, model-routing config, secret safety.
   - Phase B: Real-market forecast loop + calibration spine.
   - Phase C: Strategy intelligence + hybrid disagreement engine.
   - Phase D: Hybrid live-cap firewall rehearsal + dashboard V7 + integration reports/tests.

## Architecture

```
configs/model_routing.json
model_router/
  __init__.py
  config.py          # load config + env
  tasks.py           # ModelTask enum + routing rules
  providers.py       # BaseModelProvider, DeepSeekV4FlashProvider, MinimaxM3Provider, MockProvider
  router.py          # ModelRouter, ModelRouteDecision
  envelope.py        # ModelResponseEnvelope, ModelProofRecord, HybridReviewResult
  prompt_firewall.py # PromptFirewall redaction + blocking
  cost_tracker.py    # latency/cost metadata stub
forecasting/
  hybrid_engine.py   # HybridForecastEngine -> ForecastOpinion
calibration/
  __init__.py
  spine.py           # CalibrationSpine metrics
  storage.py         # JSON persistence
  schema.py          # ForecastMetricSchema
strategies/
  intelligence.py    # StrategyIntelligence wrapper + critiques
  critique.py        # StrategyCritique model
  disagreement.py    # HybridDisagreementEngine
execution/
  hybrid_path.py     # HybridAutonomousExecutionPath (extends rehearse_live_cap with model review)
dashboard/backend/
  v7_routes.py       # /v7/* endpoints
dashboard/frontend/src/screens/
  V7Dashboard.jsx
scripts/
  generate_v7_reports.py
tests/
  test_model_routing_config.py
  test_model_router.py
  test_deepseekv4flash_minimaxm3_routing.py
  test_llm_prompt_firewall.py
  test_no_llm_secret_leak.py
  test_real_market_forecast_loop.py
  test_forecast_opinion_schema.py
  test_calibration_spine.py
  test_strategy_intelligence.py
  test_strategy_critique.py
  test_hybrid_disagreement_engine.py
  test_hybrid_live_cap_firewall_rehearsal.py
  test_model_proof_order_path.py
  test_dashboard_v7.py
  test_dummy_canonical_identity_v3.py
  test_blunder_separation_v5.py
  test_direct_order_bypass_v7.py
```

## LLM Output Boundaries

LLMs may emit only:

- `ForecastOpinion`
- `StrategyCritique`
- `RiskCritique`
- `NoTradeReason`
- `TradeProposalDraft`
- `CalibrationNote`
- `MarketThesis`

No order endpoint calls, no live-submit modification, no cap modification.

## Pass / Partial / Fail Rules

- **PASS**: all tests pass, dashboard builds, hybrid router + prompt firewall implemented, no secrets leak, real Kalshi read-only still works, no live submit without explicit arming, all reports generated.
- **PARTIAL**: same as PASS but live model API credentials absent (mock mode) or Kalshi read-only temporarily unavailable.
- **FAIL**: any regression in canonical identity, Blunder separation, tests, dashboard, secret leaks, direct order bypass, or firewall weakening.
