# Dummy V8 Design: Live DeepSeekV4Flash + MinimaxM3 Model Proof, Forecast, Calibration & Strategy Governor

## Context

Continue from Dummy V7 at `C:\src\engine\dummy`. V7 passed all gates with mock-model hybrid routing. V8 moves toward credential-backed live DeepSeekV4Flash + MinimaxM3 proof while keeping real live submit disabled unless explicitly armed.

## Constraints (hard)

- Do not rebuild from scratch.
- Do not modify canonical Blunder (`core/inherited_blunder/` remains untouched).
- Do not rename Dummy.
- Do not use `C:\src\engine\dumby` as active runtime.
- Do not weaken the Live Broker Firewall.
- Do not add a paper-trading ladder.
- Do not expand the repo list unless a required adapter is missing.
- Do not place real live orders unless `configs/live_submit.json` is explicitly enabled with required operator acknowledgement.
- Do not let any model, strategy, adapter, dashboard, forecast, or repo-derived module submit orders directly.
- Use Dummy V7 as authority.

## Credential model

Accepted env vars:

- `DEEPSEEK_API_KEY` (required for live)
- `DEEPSEEK_BASE_URL` optional
- `DEEPSEEK_MODEL` default `deepseekv4flash`
- `MINIMAX_API_KEY` (required for live)
- `MINIMAX_BASE_URL` optional
- `MINIMAX_MODEL` default `minimaxm3`

Credentials loaded via `python-dotenv` / `os.environ` or local secret-manager fallback. Keys are never printed, logged, written to artifacts, exposed in dashboard, or sent to models.

## Objectives

1. Model credential readiness
2. Live provider adapters (DeepSeekV4FlashProvider, MinimaxM3Provider, MockProvider hardened)
3. Live model smoke proof
4. Prompt firewall V2 + model-output firewall
5. Real Kalshi read-only refresh v4
6. Real-market forecast loop V2
7. Calibration spine V2
8. Strategy governor V1
9. Hybrid disagreement V2
10. Live-capped firewall rehearsal V2
11. Dashboard V8
12. Regression validation

## Key components to add/extend

### model_router

- `providers.py`: harden DeepSeekV4FlashProvider, MinimaxM3Provider, MockProvider with timeout, retry, cost/latency metadata, error classification, response schema validation, redacted digests.
- `prompt_firewall.py`: V2 classifications (`SECRET_BLOCK`, `ACCOUNT_DATA_BLOCK`, `ORDER_INSTRUCTION_BLOCK`, `FIREWALL_BYPASS_BLOCK`, `CAP_MODIFICATION_BLOCK`, `LIVE_SUBMIT_MODIFICATION_BLOCK`, `SAFE_SANITIZED_MARKET_PROMPT`).
- `output_firewall.py`: NEW — block direct order instructions, cap changes, live-submit changes, Kalshi write calls; convert unsafe output to `NoTradeReason`.
- `config.py`: support new env vars, redaction lists.
- `envelope.py`: add provider latency/cost metadata.

### forecasting

- `hybrid_engine.py`: route tasks to DeepSeekV4Flash (fast summary, first-pass forecast, no-trade reason) and MinimaxM3 (critique, alternate thesis, risk analysis, confidence adjustment).
- `real_market_loop.py`: V2 uses fresh Kalshi snapshot, bounded market sample, computes market-implied probability, Dummy statistical estimate, depth/spread/liquidity/freshness/settlement-risk scores, runs hybrid models, emits `ForecastOpinion` objects, no order submission.

### calibration

- `schema.py`: extend `ForecastRecord` with all model-route probabilities, confidence bucket, settlement status, realized outcome.
- `spine.py`: V2 metrics (Brier, log loss, ECE, market-implied delta, model disagreement score, confidence bucket accuracy, abstention tracking).
- `storage.py`: ensure schema migration / backward compatibility.

### strategies

- `governor.py`: NEW `StrategyGovernor` consuming `ForecastOpinion`, `StrategyCritique`, `RiskCritique`, `HybridReviewResult`, market-quality scores, calibration confidence, disagreement score, cap impact, compliance verdict. Outputs: `APPROVE_FOR_FIREWALL_REHEARSAL`, `NO_TRADE`, `REQUIRE_MORE_EVIDENCE`, `REQUIRE_MINIMAX_REVIEW`, `REQUIRE_OPERATOR_REVIEW`, `QUARANTINE_STRATEGY`.
- `disagreement.py`: V2 adds disagreement among market-implied, Dummy, DeepSeekV4Flash, MinimaxM3, strategy signal, risk governor, calibration confidence.

### execution

- `hybrid_path.py`: V2 chain adds `StrategyGovernor` before firewall rehearsal.
- Rehearsal V2 stops before submit unless `configs/live_submit.json` enabled; when enabled still requires all caps/kill-switch/proof/compliance/governor gates.

### dashboard

- `backend/v8_routes.py`: NEW routes for model providers, live smoke, prompt firewall V2, forecast loop V2, calibration V2, strategy governor, hybrid disagreement V2, firewall rehearsal V2.
- `frontend/`: add V8 screen and navigation.

### tests

Add required V8 tests and keep existing V7 tests passing.

### reports

Generate all required V8 reports under `artifacts/dummy/`.

## Data flow

1. Credential readiness detects live vs mock mode.
2. Live provider adapters validate config and redaction.
3. Smoke tests call harmless sanitized prompts if credentials present; otherwise mark `MOCK_ONLY`.
4. Prompt firewall V2 sanitizes all prompts; output firewall sanitizes model responses.
5. Real Kalshi read-only fetches snapshot with endpoint audit.
6. Forecast loop V2 builds opinions from market data + hybrid models.
7. Calibration spine V2 records and scores forecasts.
8. Strategy governor decides whether to proceed to firewall rehearsal.
9. Hybrid disagreement V2 flags conflicts.
10. Firewall rehearsal V2 returns `would_submit: false` by default (`live_submit_disabled`).
11. Dashboard V8 surfaces all statuses without exposing secrets.
12. Regression validation runs full pytest suite and produces final reports.

## Testing strategy

- Unit tests for each new component.
- Integration tests for credential readiness, provider adapters, smoke (mock fallback), prompt/output firewall, Kalshi read-only, forecast loop, calibration, strategy governor, hybrid disagreement, firewall rehearsal.
- Security tests ensure no secret leak, no direct order bypass, no live submit without operator approval.
- Dashboard build test and backend endpoint tests.

## PASS / PARTIAL / FAIL rules

As specified in the V8 brief. PASS if all gates pass; PARTIAL if live credentials absent but everything else passes with mock fallback; FAIL on any security regression, test failure, or canonical identity/Blunder separation regression.
