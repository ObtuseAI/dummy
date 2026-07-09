# DUMMY_V8_1_LIVE_MODEL_PROVIDER_RESOLUTION_AND_HYBRID_SMOKE_PASS_CLOSURE_V1 — Design

## Goal
Make Dummy’s live-model smoke proof deterministic and operator-actionable. When valid DeepSeekV4Flash / MinimaxM3 credentials and model IDs are present, run bounded, sanitized live smoke calls and mark the provider `LIVE_PROVEN`. When the model ID cannot be resolved, fail cleanly with `OPERATOR_MODEL_CONFIG_REQUIRED` and a redaction-safe repair report. Never hang, never leak secrets, never call order endpoints.

## Current authority
- V8 test suite: 813 passed, 2 skipped.
- V8 orchestrator: `PARTIAL` only because `live_model_provider_adapter_report_v1.json` returns `HTTP_404` and smoke falls back to `MOCK_ONLY`.
- `.env` has `DEEPSEEK_API_KEY`, `MINIMAX_API_KEY`, `OPENROUTER_API_KEY`.
- `configs/model_routing.json` points both providers at `https://openrouter.ai/api/v1` with model names `deepseek/deepseek-v3` and `minimax/minimax-01`.
- The providers currently use the configured base URL/model directly, with no alias fallback or 404 classification.

## Root cause of HTTP_404
The configured base URL (`openrouter.ai`) and model slugs may not be reachable with the stored provider-specific API keys, or the model slugs are no longer valid. Without resolution, the adapter treats this as a generic `HTTP_404` and gives up.

## Design

### 1. Resolver layer (`model_router/resolver.py`)
Introduce a resolver that produces a `ProviderResolutionResult` for each live provider.

Data classes:
- `ProviderEndpointCandidate` — base URL + timeout + key env.
- `ModelAliasCandidate` — a model slug to try.
- `ProviderResolutionResult` — status (`LIVE_PROVEN`, `OPERATOR_MODEL_CONFIG_REQUIRED`, `PROVIDER_AUTH_FAILED`, `MOCK_ONLY`), resolved model/base URL/error category, redacted metadata.

Resolution algorithm per provider:
1. Gather overrides from env: `*_API_KEY`, `*_BASE_URL`, `*_MODEL`, `*_MODEL_ALIASES`.
2. Fall back to `configs/model_routing.json` and provider-specific defaults (`https://api.deepseek.com`, `https://api.minimax.chat`).
3. Try `GET {base_url}/v1/models` with timeout `<=10s` and redacted logging. If a configured model or alias is in the list, resolve.
4. If model-list fails or the model is not listed, try each alias via a bounded `POST /v1/chat/completions` smoke call (timeout `<=10s`) using a harmless, firewall-passing prompt. First 200 resolves.
5. If all candidates fail, classify the failure (`MODEL_NOT_FOUND`, `ENDPOINT_NOT_FOUND`, `PROVIDER_AUTH_FAILED`, etc.) and return `OPERATOR_MODEL_CONFIG_REQUIRED`.

### 2. Error classifier update (`model_router/error_classifier.py`)
Add categories:
- `MODEL_NOT_FOUND`
- `ENDPOINT_NOT_FOUND`
- `PROVIDER_AUTH_FAILED`
- `PROVIDER_RATE_LIMITED`
- `PROVIDER_TIMEOUT`
- `PROVIDER_NETWORK_ERROR`
- `PROVIDER_SCHEMA_ERROR`

`HTTP_404` is classified by inspecting the request path (`/v1/models` vs `/v1/chat/completions`) and, when safe, the response shape.

### 3. Smoke v2 (`model_router/smoke.py` extension)
`LiveModelSmokeV2`:
- Uses the resolver to determine whether each provider can be proven live.
- Sends only firewall-passing prompts:
  - DeepSeek: harmless market summary → `MARKET_THESIS`
  - Minimax: harmless risk critique → `RISK_CRITIQUE`
- Enforces per-call `<=20s` and total `<=45s`.
- Passes every prompt through `PromptFirewallV2` and every output through `ModelOutputFirewall`.
- Stores only digests/summaries, never raw prompts or keys.
- Status outcomes: `LIVE_PROVEN`, `OPERATOR_MODEL_CONFIG_REQUIRED`, `PROVIDER_AUTH_FAILED`, `MOCK_ONLY`.

### 4. Reports (`scripts/generate_v8_1_reports.py`)
A new script that writes:
- `model_provider_config_audit_report_v1.json`
- `model_provider_resolution_report_v1.json`
- `model_alias_resolution_report_v1.json`
- `model_provider_error_resolution_report_v1.json`
- `live_model_smoke_report_v2.json`
- `live_model_prompt_safety_report_v2.json`
- `live_model_output_safety_report_v1.json`
- `model_provider_operator_repair_recommendations_v1.json`
- `dashboard_v8_1_report_v1.json`
- `no_model_provider_secret_leak_report_v2.json`
- `no_llm_secret_leak_report_v3.json`
- `direct_order_bypass_report_v8_1.json`
- `no_live_submit_still_disabled_report_v8_1.json`

All reports are redacted; no API key values, balances, positions, or private key material is written.

### 5. Operator repair recommendation
A JSON file that tells the operator, per failing provider:
- whether the API key was present (redacted)
- whether the base URL was present (redacted-safe)
- whether the model ID appears unresolved
- exact config fields to review
- example placeholder values only

Dummy will not auto-edit `.env` or guess model IDs.

### 6. Dashboard V8.1 (`dashboard/backend/v8_routes.py`)
New endpoint `GET /api/v8/model-provider-resolution` returning:
- provider status
- credential present yes/no (redacted)
- base URL present yes/no (redacted-safe)
- configured/resolved model names
- last error category
- smoke status
- prompt/output firewall status
- repair recommendation path

### 7. Safety invariants
- All prompts pass `PromptFirewallV2`.
- All outputs pass `ModelOutputFirewall`.
- No provider key values are logged, stored, or returned.
- No account balance, positions, private keys, or order instructions are sent to LLMs.
- `configs/live_submit.json` remains untouched and disabled.
- `configs/caps.json` is not modified.
- No direct order endpoint calls are introduced.

### 8. Tests
Add/repair tests covering config audit, resolution, alias resolution, 404 classification, smoke v2, prompt/output safety, repair recommendations, dashboard v8.1, secret-leak guards, live-submit disabled, and direct-order bypass.

## Trade-offs
- **Approach A: hardcode correct model names.** Rejected — fragile and does not generalize.
- **Approach B: query model list then alias smoke.** Selected — bounded, redacted, and gives precise operator guidance on failure.
- **Approach C: full provider registry with remote manifests.** Rejected — over-scope; only provider resolution is needed now.
