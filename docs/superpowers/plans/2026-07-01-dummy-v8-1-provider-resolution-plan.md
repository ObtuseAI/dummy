# DUMMY_V8_1 Provider Resolution & Hybrid Smoke Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` task-by-task.

**Goal:** Resolve DeepSeekV4Flash / MinimaxM3 provider configuration through a bounded, redacted resolver so live smoke can prove `LIVE_PROVEN`, or fail cleanly as `OPERATOR_MODEL_CONFIG_REQUIRED` with precise repair guidance.

**Architecture:** Add a `model_router.resolver` layer that queries model-list endpoints and tries configured aliases with bounded smoke calls, then feeds a `LiveModelSmokeV2` runner. A new `scripts/generate_v8_1_reports.py` orchestrator writes all V8.1 reports. Dashboard backend exposes `/api/v8/model-provider-resolution`. Tests prove resolution, 404 classification, safety, and regression invariants.

**Tech Stack:** Python 3.11+, httpx, pydantic, pytest-asyncio, FastAPI, existing Dummy firewalls.

## Global Constraints
- No provider keys, balances, positions, private keys, or order instructions sent to LLMs.
- All prompts pass `PromptFirewallV2`; all outputs pass `ModelOutputFirewall`.
- Provider HTTP timeout `<= 20s`; smoke total timeout `<= 45s`; Kalshi per-call `<= 10s`.
- `configs/live_submit.json` remains disabled; `configs/caps.json` unchanged.
- No direct order endpoint calls introduced.
- No canonical Blunder modification; no Dummy rename.
- All secrets redacted in reports/dashboard.

---

### Task 1: Resolver data model and config reader

**Files:**
- Create: `model_router/resolver.py`

**Interfaces:**
- Produces: `ProviderEndpointCandidate`, `ModelAliasCandidate`, `ProviderResolutionResult`, `ModelProviderResolver`.

- [ ] **Step 1: Write the data classes**

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class ProviderEndpointCandidate:
    provider_name: str
    api_base: str
    api_key_env: str
    timeout_seconds: float = 10.0

@dataclass
class ModelAliasCandidate:
    model_name: str
    source: str  # "config", "env", "default"

@dataclass
class ProviderResolutionResult:
    provider_name: str
    status: str  # LIVE_PROVEN, OPERATOR_MODEL_CONFIG_REQUIRED, PROVIDER_AUTH_FAILED, MOCK_ONLY
    api_base: str
    api_key_env: str
    configured_model: str
    resolved_model: str | None = None
    resolved_by: str | None = None  # "model_list", "alias_smoke", "override"
    error_category: str | None = None
    error_detail: str | None = None
    redacted_metadata: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 2: Add resolver constructor that reads env + config**

```python
class ModelProviderResolver:
    def __init__(self):
        self._cfg = load_model_routing_config()

    def _env_aliases(self, prefix: str) -> list[str]:
        raw = os.environ.get(f"{prefix}_MODEL_ALIASES", "")
        return [a.strip() for a in raw.split(",") if a.strip()]

    def _candidates_for(self, name: str, default_base: str, default_aliases: list[str]) -> tuple[ProviderEndpointCandidate, list[ModelAliasCandidate]]:
        cfg = self._cfg.provider_configs.get(name, ProviderConfig(api_base="", api_key_env="", model_name=""))
        api_base = (
            os.environ.get(f"{name.upper().replace('_v4_flash', '').replace('_m3', '').replace('_', '')}_BASE_URL")
            or cfg.api_base
            or default_base
        )
        # Normalize env prefixes: deepseek_v4_flash -> DEEPSEEK, minimax_m3 -> MINIMAX
        prefix = "DEEPSEEK" if "deepseek" in name else "MINIMAX"
        model = os.environ.get(f"{prefix}_MODEL") or cfg.model_name
        aliases = self._env_aliases(prefix) or default_aliases
        ...
```

> Note: exact env-prefix mapping to be implemented as helper `_provider_env_prefix(name)`.

- [ ] **Step 3: Commit**

---

### Task 2: Error classifier 404 categories

**Files:**
- Modify: `model_router/error_classifier.py`

**Interfaces:**
- Produces: `classify_provider_error_v2(exc, context)` returning `MODEL_NOT_FOUND`, `ENDPOINT_NOT_FOUND`, etc.

- [ ] **Step 1: Add new classification function**

```python
def classify_provider_error_v2(exc: Exception, path: str = "") -> str:
    tag = classify_provider_error(exc)
    if tag == "HTTP_404":
        if "/models" in path:
            return "ENDPOINT_NOT_FOUND"
        if "/chat/completions" in path:
            return "MODEL_NOT_FOUND"
        return "PROVIDER_ROUTE_NOT_FOUND"
    if tag == "HTTP_401":
        return "PROVIDER_AUTH_FAILED"
    if tag == "HTTP_429":
        return "PROVIDER_RATE_LIMITED"
    if tag == "TIMEOUT":
        return "PROVIDER_TIMEOUT"
    if tag == "CONNECT_ERROR":
        return "PROVIDER_NETWORK_ERROR"
    if tag == "SCHEMA_VALIDATION":
        return "PROVIDER_SCHEMA_ERROR"
    return tag
```

- [ ] **Step 2: Commit**

---

### Task 3: Resolver model-list and alias-smoke probes

**Files:**
- Modify: `model_router/resolver.py`

**Interfaces:**
- Consumes: `ProviderEndpointCandidate`, `ModelAliasCandidate`, `classify_provider_error_v2`.
- Produces: `ModelProviderResolver.resolve(name, default_base, default_aliases)`.

- [ ] **Step 1: Implement model-list probe**

```python
async def _probe_model_list(self, candidate: ProviderEndpointCandidate) -> tuple[bool, list[str]]:
    key = os.environ.get(candidate.api_key_env)
    if not key:
        return False, []
    url = f"{candidate.api_base.rstrip('/')}/v1/models"
    try:
        async with httpx.AsyncClient(timeout=candidate.timeout_seconds) as client:
            r = await client.get(url, headers={"Authorization": f"Bearer {key}"})
            r.raise_for_status()
            data = r.json()
            models = [m.get("id", "") for m in data.get("data", []) if isinstance(m, dict)]
            return True, models
    except Exception:
        return False, []
```

- [ ] **Step 2: Implement alias-smoke probe**

```python
async def _probe_alias(self, candidate: ProviderEndpointCandidate, alias: ModelAliasCandidate, prompt: str, task) -> tuple[bool, dict[str, Any] | None]:
    ...  # POST /v1/chat/completions, timeout bounded, return (ok, metadata)
```

- [ ] **Step 3: Implement resolve orchestration**

```python
async def resolve(self, name: str, default_base: str, default_aliases: list[str], smoke_prompt: str, task) -> ProviderResolutionResult:
    candidate, aliases = self._candidates_for(name, default_base, default_aliases)
    key = os.environ.get(candidate.api_key_env)
    if not key:
        return ProviderResolutionResult(provider_name=name, status="MOCK_ONLY", api_base=candidate.api_base, api_key_env=candidate.api_key_env, configured_model=aliases[0].model_name if aliases else "")
    ok, models = await self._probe_model_list(candidate)
    configured = next((a for a in aliases), ModelAliasCandidate("", "")).model_name
    if ok and configured and configured in models:
        return ProviderResolutionResult(..., status="LIVE_PROVEN", resolved_model=configured, resolved_by="model_list")
    # try aliases
    for alias in aliases:
        ok, meta = await self._probe_alias(candidate, alias, smoke_prompt, task)
        if ok:
            return ProviderResolutionResult(..., status="LIVE_PROVEN", resolved_model=alias.model_name, resolved_by="alias_smoke")
    # classify best failure
    ...
    return ProviderResolutionResult(..., status="OPERATOR_MODEL_CONFIG_REQUIRED", error_category=...)
```

- [ ] **Step 4: Commit**

---

### Task 4: Smoke v2 runner

**Files:**
- Modify: `model_router/smoke.py`

**Interfaces:**
- Consumes: `ModelProviderResolver`, `ProviderResolutionResult`.
- Produces: `LiveModelSmokeV2.run()` returning v2 report dict.

- [ ] **Step 1: Add LiveModelSmokeV2 class**

```python
class LiveModelSmokeV2(LiveModelSmoke):
    async def run(self) -> dict[str, Any]:
        # use resolver per provider, build call results, enforce total timeout
        ...
```

- [ ] **Step 2: Add prompt/output safety report helpers**

```python
def generate_prompt_safety_report_v2(self) -> dict[str, Any]: ...
def generate_output_safety_report(self) -> dict[str, Any]: ...
```

- [ ] **Step 3: Commit**

---

### Task 5: Config audit report

**Files:**
- Create: `scripts/generate_v8_1_reports.py`
- Modify: `model_router/resolver.py` (expose audit helper)

**Interfaces:**
- Produces: `generate_model_provider_config_audit_report_v1()`.

- [ ] **Step 1: Implement audit helper**

```python
def audit_provider_config(name: str, default_base: str, default_aliases: list[str]) -> dict[str, Any]:
    # return redacted presence flags and values (base url safe, model name, aliases)
    ...
```

- [ ] **Step 2: Write report function**

```python
def generate_model_provider_config_audit_report_v1() -> dict[str, Any]:
    resolver = ModelProviderResolver()
    return {
        "generated_at": now_iso(),
        "workstream": "V8.1: Model Provider Config Audit",
        "deepseek": resolver.audit_provider_config("deepseek_v4_flash", "https://api.deepseek.com", ["deepseek-chat", "deepseek-v3"]),
        "minimax": resolver.audit_provider_config("minimax_m3", "https://api.minimax.chat", ["minimax-01"]),
        "verdict": "PASS",
    }
```

- [ ] **Step 3: Commit**

---

### Task 6: Resolution, alias, error-resolution reports

**Files:**
- Modify: `scripts/generate_v8_1_reports.py`

**Interfaces:**
- Consumes: `ModelProviderResolver.resolve`.
- Produces: resolution/alias/error-resolution reports.

- [ ] **Step 1: Implement async report functions**

```python
async def generate_model_provider_resolution_report_v1() -> dict[str, Any]: ...
async def generate_model_alias_resolution_report_v1() -> dict[str, Any]: ...
async def generate_model_provider_error_resolution_report_v1() -> dict[str, Any]: ...
```

- [ ] **Step 2: Commit**

---

### Task 7: Operator repair recommendations

**Files:**
- Modify: `scripts/generate_v8_1_reports.py`
- Modify: `configs/model_routing.json` (safe defaults + alias arrays only)

**Interfaces:**
- Produces: `generate_model_provider_operator_repair_recommendations_v1()`.

- [ ] **Step 1: Write recommendation builder**

```python
def generate_model_provider_operator_repair_recommendations_v1(resolution_report: dict) -> dict[str, Any]:
    ...
```

- [ ] **Step 2: Update configs/model_routing.json**

```json
{
  "provider_configs": {
    "deepseek_v4_flash": {
      "api_base": "https://api.deepseek.com",
      "api_key_env": "DEEPSEEK_API_KEY",
      "model_name": "deepseek-chat",
      "model_aliases": ["deepseek-chat", "deepseek-v3", "deepseek/deepseek-v3"],
      ...
    },
    "minimax_m3": {
      "api_base": "https://api.minimax.chat",
      "api_key_env": "MINIMAX_API_KEY",
      "model_name": "minimax-01",
      "model_aliases": ["minimax-01", "MiniMax-Text-01"],
      ...
    }
  }
}
```

- [ ] **Step 3: Commit**

---

### Task 8: V8.1 report orchestrator script

**Files:**
- Create: `scripts/generate_v8_1_reports.py`

**Interfaces:**
- Produces: all required V8.1 artifacts plus a `final_report_v8_1.json`.

- [ ] **Step 1: Implement main async orchestrator**

```python
async def main() -> dict[str, Any]:
    ...
    (ARTIFACTS / "final_report_v8_1.json").write_text(...)
```

- [ ] **Step 2: Commit**

---

### Task 9: Dashboard V8.1 endpoint

**Files:**
- Modify: `dashboard/backend/v8_routes.py`

**Interfaces:**
- Produces: `GET /api/v8/model-provider-resolution`.

- [ ] **Step 1: Add route**

```python
@router.get("/model-provider-resolution")
async def model_provider_resolution() -> dict[str, Any]:
    resolver = ModelProviderResolver()
    ds = await resolver.resolve("deepseek_v4_flash", "https://api.deepseek.com", ["deepseek-chat", "deepseek-v3"], _DEEPSEEK_SMOKE_PROMPT, ModelTask.MARKET_THESIS)
    mm = await resolver.resolve("minimax_m3", "https://api.minimax.chat", ["minimax-01"], _MINIMAX_SMOKE_PROMPT, ModelTask.RISK_CRITIQUE)
    return {"deepseek": ds.redacted_metadata, "minimax": mm.redacted_metadata, ...}
```

- [ ] **Step 2: Commit**

---

### Task 10: Tests

**Files:**
- Create: `tests/test_model_provider_config_audit.py`
- Create: `tests/test_model_provider_resolution.py`
- Create: `tests/test_model_alias_resolution.py`
- Create: `tests/test_model_provider_http_404_classification.py`
- Create: `tests/test_live_model_smoke_v2.py`
- Create: `tests/test_live_model_prompt_safety_v2.py`
- Create: `tests/test_live_model_output_safety.py`
- Create: `tests/test_model_provider_operator_repair_recommendations.py`
- Create: `tests/test_dashboard_v8_1.py`
- Create: `tests/test_no_model_provider_secret_leak_v2.py`
- Create: `tests/test_no_llm_secret_leak_v3.py`
- Create: `tests/test_no_live_submit_still_disabled_v8_1.py`
- Create: `tests/test_direct_order_bypass_v8_1.py`

**Interfaces:**
- Consumes: resolver, smoke v2, dashboard endpoint, report functions.

- [ ] **Step 1: Write each test with mocked httpx where live calls would occur**
- [ ] **Step 2: Commit**

---

### Task 11: Regression validation

**Files:**
- All above.

- [ ] **Step 1: Run full pytest**
  - `python -m pytest tests/ -vv -s --tb=short --maxfail=1 --durations=25 --timeout=60`
- [ ] **Step 2: Run quick pytest**
  - `python -m pytest tests/ -q --tb=short --timeout=60`
- [ ] **Step 3: Build dashboard**
  - `cd dashboard/frontend && npm run build`
- [ ] **Step 4: Run V8 and V8.1 report generators**
  - `python scripts/generate_v8_reports.py`
  - `python scripts/generate_v8_1_reports.py`
- [ ] **Step 5: Commit if all green**
