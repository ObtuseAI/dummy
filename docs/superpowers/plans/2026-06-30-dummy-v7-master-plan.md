# DUMMY_V7 Hybrid Model Routing Master Plan

> **For agentic workers:** Implement the four phase briefs in order (A → B → C → D). Each phase is self-contained and must pass its phase test gate before the next phase starts.

**Goal:** Install a DeepSeekV4Flash + MinimaxM3 hybrid model-routing layer on top of Dummy V6, then use it to improve real-market forecasting, strategy critique, calibration scoring, no-trade reasoning, and autonomous alpha-loop selection while preserving the Live Broker Firewall and keeping real live submit disabled unless explicitly armed.

**Authority:** Dummy V6 is the authority:
- `artifacts/dummy/final_report.json` = PASS
- Real Kalshi credentials present
- Real Kalshi read-only path proven
- Dashboard built, tests pass
- Live-submit flag disabled, no live orders submitted

**Architecture:** A new `model_router/` package provides provider-agnostic async routing, prompt firewalling, secret redaction, and deterministic mock fallback. `forecasting/hybrid_engine.py` consumes the router to produce typed `ForecastOpinion` and `MarketThesis` objects. `calibration/` stores and scores outcomes. `strategies/intelligence.py`, `strategies/critique.py`, and `strategies/disagreement.py` add LLM critique and dual-model disagreement. `execution/hybrid_path.py` extends the existing `AutonomousExecutionPath` with model review while keeping every live order inside `LiveBrokerFirewall.submit`. Dashboard V7 is added alongside V6.

---

## Global Constraints

- **Do not modify canonical Blunder** (`C:/src/engine/obtuse/blunder`).
- **Do not rename Dummy** or revert the canonical identity.
- **No live order submission** except through `LiveBrokerFirewall.submit`.
- **No secrets in prompts, logs, model responses, or artifacts.** Provider API keys, Kalshi credentials, and any other secret values must be redacted before they enter prompts or persisted output.
- `configs/caps.json` and `configs/live_submit.json` are **read-only** for all runtime code; caps and live-submit state may only be changed by operators editing the files.
- **Mock fallback for missing model keys:** if `DEEPSEEK_API_KEY` or `MINIMAX_API_KEY` are absent, the router must fall back to `MockProvider` and report `PARTIAL` for live-model status. No operation may fail solely because credentials are missing.
- LLM outputs are limited to the approved value objects:
  - `ForecastOpinion`
  - `StrategyCritique`
  - `RiskCritique`
  - `NoTradeReason`
  - `TradeProposalDraft`
  - `CalibrationNote`
  - `MarketThesis`
- No LLM output may instruct or perform order endpoint calls, live-submit modification, cap modification, kill-switch changes, or emergency-stop changes.
- All new code is async to match `KalshiRealReadOnly`, `StrategyScanner`, and `LiveBrokerFirewall`.
- Preserve V6 dashboard and reports exactly as they are; V7 dashboard is additive.

---

## Phase Overview

| Phase | Focus | New / Modified Files | Exit Gate |
|-------|-------|----------------------|-----------|
| **A** | Model router, prompt firewall, model-routing config, secret safety | `configs/model_routing.json`, `model_router/*`, updates to `core/secret_guard.py`, `.env.example` | `pytest tests/test_model_routing_config.py tests/test_model_router.py tests/test_deepseekv4flash_minimaxm3_routing.py tests/test_llm_prompt_firewall.py tests/test_no_llm_secret_leak.py -v` |
| **B** | Real-market forecast loop + calibration spine | `forecasting/hybrid_engine.py`, `forecasting/real_market_loop.py`, `calibration/*`, `core/ontology.py` additions | `pytest tests/test_real_market_forecast_loop.py tests/test_forecast_opinion_schema.py tests/test_calibration_spine.py -v` |
| **C** | Strategy intelligence + hybrid disagreement engine | `strategies/intelligence.py`, `strategies/critique.py`, `strategies/disagreement.py`, `strategies/scan.py` update, `core/ontology.py` additions | `pytest tests/test_strategy_intelligence.py tests/test_strategy_critique.py tests/test_hybrid_disagreement_engine.py -v` |
| **D** | Hybrid live-cap firewall rehearsal + dashboard V7 + V7 reports + integration tests | `execution/hybrid_path.py`, `dashboard/backend/v7_routes.py`, `dashboard/frontend/src/screens/V7Dashboard.jsx`, `scripts/generate_v7_reports.py`, updates to `dashboard/backend/main.py`, `dashboard/frontend/src/App.jsx` | `pytest tests/test_hybrid_live_cap_firewall_rehearsal.py tests/test_model_proof_order_path.py tests/test_dashboard_v7.py tests/test_dummy_canonical_identity_v3.py tests/test_blunder_separation_v5.py tests/test_direct_order_bypass_v7.py -v` |

---

## Dependencies

- **Phase A** has no new runtime dependencies beyond existing `httpx` and `pydantic`.
- **Phase B** depends on Phase A (`model_router.router.ModelRouter`).
- **Phase C** depends on Phase A and Phase B (`model_router`, `ForecastOpinion`, `HybridForecastEngine`).
- **Phase D** depends on A, B, and C (`ModelRouter`, `HybridForecastEngine`, `StrategyIntelligence`, `HybridDisagreementEngine`, `LiveBrokerFirewall`).

---

## Final Validation Commands

Run from `C:/src/engine/dummy`:

```bash
# 1. Full Python test suite
python -m pytest tests/ -q --tb=short

# 2. Dashboard build
cd dashboard/frontend
npm ci
npm run build
cd ../..

# 3. V7 report generator (also regenerates V6 reports and final_report.json)
python scripts/generate_v7_reports.py

# 4. Inspect final report
cat artifacts/dummy/final_report.json
```

**Pass criteria:**
- All V6 tests still pass.
- All new V7 tests pass.
- Dashboard builds (`dist/index.html` exists).
- `final_report.json` shows `verdict` = `PASS` (or `PARTIAL` only when live model keys or Kalshi credentials are absent).
- No secret values appear in `logs/dummy.jsonl`, `artifacts/dummy/`, or any prompt/response payload.
- No new `create_order` callers appear outside `live_firewall/firewall.py` and `kalshi/submitter.py`.
```

---
