# Phase B Report: Real-Market Forecast Loop + Calibration Spine

**Status:** Complete  
**Date:** 2026-07-01  
**Worker:** Kimi Code CLI  

## Summary

Phase B deliverables were implemented according to the brief. The Phase B exit gate passes, and no regressions were introduced in the existing test suite.

## Files Created / Modified

### Modified
- `core/ontology.py` — added `ForecastOpinion`, `CalibrationNote`, and `MarketThesis` Pydantic models.

### Created
- `forecasting/hybrid_engine.py` — `HybridForecastEngine` wrapping the base `ForecastEngine` and `ModelRouter`.
- `forecasting/real_market_loop.py` — `RealMarketForecastLoop` that ingests real Kalshi snapshots or falls back to mock when credentials are missing.
- `calibration/__init__.py` — package exports.
- `calibration/schema.py` — `ForecastRecord`, `SettlementRecord`, `CalibrationMetrics`.
- `calibration/spine.py` — `CalibrationSpine` scoring (Brier, log-loss, calibration error, coverage).
- `calibration/storage.py` — `CalibrationStorage` appending/loading forecasts and settlements as JSONL.
- `data/calibration/` — working calibration JSONL directory.
- `artifacts/dummy/calibration/` — generated calibration report directory.
- `tests/test_real_market_forecast_loop.py`
- `tests/test_forecast_opinion_schema.py`
- `tests/test_calibration_spine.py`

## Test Results

### Phase B Exit Gate
```bash
python -m pytest tests/test_real_market_forecast_loop.py tests/test_forecast_opinion_schema.py tests/test_calibration_spine.py -v
```

Result: **7 passed**

### Full Existing Test Suite
```bash
python -m pytest -q
```

Result: **624 passed, 2 failed, 2 skipped**

## Regressions / Concerns

The two failures in the full suite are **pre-existing** and unrelated to Phase B changes:

- `tests/test_kalshi_normalization_v2.py::test_normalizer_report_exists`
- `tests/test_real_market_strategy_scan_v3.py::test_real_market_strategy_scan_report_v3`

Both fail because the runtime environment has real Kalshi credentials (`KALSHI_API_KEY_ID`, `KALSHI_API_PRIVATE_KEY_PEM_PATH`) configured, and the V5/V6 report generators attempt live API calls that error out (`Kalshi API error`). These same two tests fail when the new Phase B tests are excluded from the run (617 passed, 2 failed), confirming they are not regressions introduced by this work.

Per the brief, Phase B code falls back to mock when Kalshi credentials are missing (see `RealMarketForecastLoop.run`). The failing tests exercise legacy V5/V6 report scripts that do not gracefully handle live API errors when credentials happen to be present.

No live order submission is performed by any Phase B code. No secrets are embedded in prompts, logs, or artifacts. Caps and live-submit configuration were not modified.
