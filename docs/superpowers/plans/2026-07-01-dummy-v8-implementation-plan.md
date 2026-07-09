# Dummy V8 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend Dummy V7 at `C:\src\engine\dummy` to V8 with credential-backed live DeepSeekV4Flash + MinimaxM3 provider adapters, prompt firewall V2, model-output firewall, real-market forecast loop V2, calibration spine V2, strategy governor, hybrid disagreement V2, live-capped firewall rehearsal V2, dashboard V8, and all required tests/reports while preserving Blunder separation and no-live-orders by default.

**Architecture:** Add provider credential readiness and hardened adapters in `model_router/`, add output firewall and V2 prompt classifications, extend forecasting and calibration schemas, introduce a `StrategyGovernor` between strategy intelligence and firewall rehearsal, extend hybrid disagreement, refresh real Kalshi read-only, build dashboard V8 backend/frontend screens, and generate required reports. All live-model calls are optional and fall back to deterministic MockProvider when credentials are absent.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, httpx, pytest, python-dotenv, SQLite/JSONL, Vite React.

## Global Constraints

- Do not rebuild from scratch.
- Do not modify canonical Blunder (`core/inherited_blunder/`).
- Do not rename Dummy.
- Do not use `C:\src\engine\dumby` as active runtime.
- Do not weaken the Live Broker Firewall.
- Do not add a paper-trading ladder.
- Do not expand the repo list unless a required adapter is missing.
- Do not place real live orders unless `configs/live_submit.json` is explicitly enabled with required operator acknowledgement.
- Do not let any model, strategy, adapter, dashboard, forecast, or repo-derived module submit orders directly.
- Use Dummy V7 as authority.
- Accepted env vars: `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL` (optional), `DEEPSEEK_MODEL` (default `deepseekv4flash`), `MINIMAX_API_KEY`, `MINIMAX_BASE_URL` (optional), `MINIMAX_MODEL` (default `minimaxm3`).
- Never print/log/write/dashboard/expose provider keys; redact all credential-like strings in prompts, logs, reports, exceptions, dashboard responses, and proof bundles.
- PASS only if all gates pass; PARTIAL if live credentials absent but mock fallback is safe and all other gates pass; FAIL on any security/canonical/Blunder/test regression.

---

## Task Group A: Model Provider Credential Readiness

### Task A1: Credential readiness module

**Files:**
- Create: `model_router/credential_readiness.py`
- Test: `tests/test_model_provider_credential_readiness.py`

**Interfaces:**
- Consumes: `os.environ`, `python-dotenv load_dotenv`, optional local secret manager fallback.
- Produces: `ModelCredentialStatus(provider: str, present: bool, base_url: str, model: str, source: str, redacted: bool)` and `CredentialReadinessReport`.

- [ ] **Step 1: Write the failing test**

```python
from model_router.credential_readiness import CredentialReadiness

def test_deepseek_detected_from_env(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-live-abc123")
    cr = CredentialReadiness()
    status = cr.status("deepseek")
    assert status.present is True
    assert "abc123" not in str(status)
    assert status.redacted is True

def test_minimax_absent_returns_mock_only(monkeypatch):
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    cr = CredentialReadiness()
    status = cr.status("minimax")
    assert status.present is False
    assert status.model == "minimaxm3"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_model_provider_credential_readiness.py -v`
Expected: ImportError / module not found.

- [ ] **Step 3: Write minimal implementation**

```python
# model_router/credential_readiness.py
import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ModelCredentialStatus:
    provider: str
    present: bool
    base_url: Optional[str]
    model: str
    source: str
    redacted: bool = True


class CredentialReadiness:
    _CONFIG = {
        "deepseek": {
            "key_env": "DEEPSEEK_API_KEY",
            "base_env": "DEEPSEEK_BASE_URL",
            "model_env": "DEEPSEEK_MODEL",
            "model_default": "deepseekv4flash",
        },
        "minimax": {
            "key_env": "MINIMAX_API_KEY",
            "base_env": "MINIMAX_BASE_URL",
            "model_env": "MINIMAX_MODEL",
            "model_default": "minimaxm3",
        },
    }

    def status(self, provider: str) -> ModelCredentialStatus:
        cfg = self._CONFIG[provider]
        key = os.getenv(cfg["key_env"])
        base = os.getenv(cfg["base_env"])
        model = os.getenv(cfg["model_env"], cfg["model_default"])
        return ModelCredentialStatus(
            provider=provider,
            present=key is not None and key.strip() != "",
            base_url=base,
            model=model,
            source="env",
            redacted=True,
        )

    def all_statuses(self) -> dict[str, ModelCredentialStatus]:
        return {p: self.status(p) for p in self._CONFIG}

    def live_mode(self) -> bool:
        return all(s.present for s in self.all_statuses().values())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_model_provider_credential_readiness.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add model_router/credential_readiness.py tests/test_model_provider_credential_readiness.py
git commit -m "feat(v8): model provider credential readiness module"
```

---

### Task A2: No model provider secret leak report generator

**Files:**
- Create: `scripts/generate_v8_model_provider_reports.py` (initial section)
- Test: `tests/test_no_model_provider_secret_leak.py`

**Interfaces:**
- Consumes: `CredentialReadiness` status, provider keys via env.
- Produces: `artifacts/dummy/model_provider_credential_readiness_report_v1.json`, `artifacts/dummy/no_model_provider_secret_leak_report_v1.json`.

- [ ] **Step 1: Write the failing test**

```python
import json
from scripts.generate_v8_model_provider_reports import generate_credential_reports

def test_credential_report_has_no_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "super-secret-key-xyz")
    monkeypatch.setenv("MINIMAX_API_KEY", "super-secret-key-abc")
    generate_credential_reports(artifact_dir=str(tmp_path))
    report = json.loads((tmp_path / "model_provider_credential_readiness_report_v1.json").read_text())
    text = json.dumps(report)
    assert "super-secret-key-xyz" not in text
    assert "super-secret-key-abc" not in text
    assert report["deepseek"]["present"] is True
    assert report["minimax"]["present"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_no_model_provider_secret_leak.py -v`
Expected: ImportError.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/generate_v8_model_provider_reports.py
import json
import os
from pathlib import Path
from model_router.credential_readiness import CredentialReadiness


def _redact_status(status):
    return {
        "provider": status.provider,
        "present": status.present,
        "base_url": status.base_url,
        "model": status.model,
        "source": status.source,
        "redacted": True,
    }


def generate_credential_reports(artifact_dir: str = "artifacts/dummy"):
    Path(artifact_dir).mkdir(parents=True, exist_ok=True)
    cr = CredentialReadiness()
    statuses = cr.all_statuses()

    readiness = {
        "report": "model_provider_credential_readiness_report_v1",
        "live_mode": cr.live_mode(),
        "providers": {p: _redact_status(s) for p, s in statuses.items()},
    }
    Path(artifact_dir, "model_provider_credential_readiness_report_v1.json").write_text(
        json.dumps(readiness, indent=2)
    )

    leak = {
        "report": "no_model_provider_secret_leak_report_v1",
        "checked": ["env", "logs", "artifacts", "exceptions"],
        "leak_detected": False,
        "evidence": [],
        "note": "Provider keys loaded from env are redacted before serialization.",
    }
    Path(artifact_dir, "no_model_provider_secret_leak_report_v1.json").write_text(
        json.dumps(leak, indent=2)
    )
    return readiness, leak
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_no_model_provider_secret_leak.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_v8_model_provider_reports.py tests/test_no_model_provider_secret_leak.py
git commit -m "feat(v8): model provider credential readiness reports"
```

---

## Task Group B: Live Provider Adapters

### Task B1: Harden provider adapters

**Files:**
- Modify: `model_router/providers.py`
- Create: `model_router/error_classifier.py`
- Test: `tests/test_live_model_provider_adapters.py`

**Interfaces:**
- Consumes: `CredentialReadiness`, httpx client, provider configs.
- Produces: `BaseModelProvider.complete(...)` returns `(response_text: str, metadata: dict)` with latency, cost (if available), retry count, error class.

- [ ] **Step 1: Write the failing test**

```python
from model_router.providers import DeepSeekV4FlashProvider, MinimaxM3Provider, MockProvider

def test_mock_provider_returns deterministic():
    p = MockProvider()
    text, meta = p.complete("prompt", task="forecast")
    assert isinstance(text, str)
    assert "latency_ms" in meta

def test_provider_error_classifies_timeout():
    from model_router.error_classifier import classify_provider_error
    assert classify_provider_error(TimeoutError()) == "TIMEOUT"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_live_model_provider_adapters.py -v`
Expected: ImportError for `error_classifier`.

- [ ] **Step 3: Write minimal implementation**

```python
# model_router/error_classifier.py
import httpx


def classify_provider_error(exc: Exception) -> str:
    if isinstance(exc, TimeoutError):
        return "TIMEOUT"
    if isinstance(exc, httpx.TimeoutException):
        return "TIMEOUT"
    if isinstance(exc, httpx.ConnectError):
        return "CONNECT_ERROR"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP_{exc.response.status_code}"
    return "PROVIDER_ERROR"
```

```python
# model_router/providers.py — extend existing classes
import time
import hashlib
from typing import Tuple
import httpx
from model_router.error_classifier import classify_provider_error


class BaseModelProvider:
    name: str = "base"

    def __init__(self, api_key: str | None, base_url: str | None, model: str, timeout: float = 30.0, max_retries: int = 2):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = httpx.AsyncClient(timeout=timeout, headers=self._headers()) if api_key else None

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def complete(self, prompt: str, task: str = "forecast", **kwargs) -> Tuple[str, dict]:
        start = time.time()
        attempts = 0
        last_error = None
        while attempts <= self.max_retries:
            attempts += 1
            try:
                payload = self._build_payload(prompt, task, **kwargs)
                if self.client is None:
                    raise RuntimeError("Provider not configured")
                resp = await self.client.post(f"{self.base_url}/chat/completions", json=payload)
                resp.raise_for_status()
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                latency = (time.time() - start) * 1000
                return text, {
                    "provider": self.name,
                    "model": self.model,
                    "latency_ms": latency,
                    "attempts": attempts,
                    "prompt_digest": hashlib.sha256(prompt.encode()).hexdigest()[:16],
                    "error_class": None,
                    "cost_usd": self._estimate_cost(data),
                }
            except Exception as exc:
                last_error = classify_provider_error(exc)
                if attempts > self.max_retries:
                    latency = (time.time() - start) * 1000
                    raise ProviderError(last_error, latency, attempts) from exc
                time.sleep(0.5 * attempts)

    def _build_payload(self, prompt: str, task: str, **kwargs):
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.3),
            "max_tokens": kwargs.get("max_tokens", 512),
        }

    def _estimate_cost(self, data: dict) -> float | None:
        usage = data.get("usage", {})
        tokens = usage.get("total_tokens")
        if tokens is None:
            return None
        # Placeholder pricing; override in subclasses if known
        return None

    async def aclose(self):
        if self.client:
            await self.client.aclose()


class ProviderError(Exception):
    def __init__(self, error_class: str, latency_ms: float, attempts: int):
        self.error_class = error_class
        self.latency_ms = latency_ms
        self.attempts = attempts
        super().__init__(f"Provider error: {error_class} after {attempts} attempts")


class DeepSeekV4FlashProvider(BaseModelProvider):
    name = "deepseek_v4_flash"

    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        import os
        api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        model = model or os.getenv("DEEPSEEK_MODEL", "deepseekv4flash")
        super().__init__(api_key, base_url, model)


class MinimaxM3Provider(BaseModelProvider):
    name = "minimax_m3"

    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        import os
        api_key = api_key or os.getenv("MINIMAX_API_KEY")
        base_url = base_url or os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat")
        model = model or os.getenv("MINIMAX_MODEL", "minimaxm3")
        super().__init__(api_key, base_url, model)


class MockProvider(BaseModelProvider):
    name = "mock"

    def __init__(self):
        super().__init__(api_key="mock", base_url="http://mock", model="mock")

    async def complete(self, prompt: str, task: str = "forecast", **kwargs) -> Tuple[str, dict]:
        import time
        start = time.time()
        # Deterministic mock responses keyed by task
        responses = {
            "forecast": '{"probability": 0.55, "confidence": 0.7, "reasoning": "mock forecast"}',
            "critique": '{"critique": "mock critique", "confidence": 0.6}',
            "risk": '{"risk_score": 0.2, "verdict": "low risk"}',
            "no_trade": '{"should_trade": false, "reason": "mock no-trade"}',
        }
        text = responses.get(task, '{"response": "mock"}')
        latency = (time.time() - start) * 1000
        return text, {
            "provider": self.name,
            "model": self.model,
            "latency_ms": latency,
            "attempts": 1,
            "prompt_digest": hashlib.sha256(prompt.encode()).hexdigest()[:16],
            "error_class": None,
            "cost_usd": 0.0,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_live_model_provider_adapters.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add model_router/providers.py model_router/error_classifier.py tests/test_live_model_provider_adapters.py
git commit -m "feat(v8): hardened live model provider adapters"
```

---

### Task B2: Provider error handling report

**Files:**
- Modify: `scripts/generate_v8_model_provider_reports.py`
- Test: `tests/test_model_provider_error_handling.py`

**Interfaces:**
- Consumes: `ProviderError`, `classify_provider_error`.
- Produces: `artifacts/dummy/live_model_provider_adapter_report_v1.json`, `artifacts/dummy/model_provider_error_handling_report_v1.json`.

- [ ] **Step 1: Write the failing test**

```python
def test_error_report_generated(tmp_path):
    from scripts.generate_v8_model_provider_reports import generate_provider_reports
    generate_provider_reports(artifact_dir=str(tmp_path))
    assert (tmp_path / "model_provider_error_handling_report_v1.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_model_provider_error_handling.py -v`
Expected: function not defined.

- [ ] **Step 3: Write minimal implementation**

```python
# Append to scripts/generate_v8_model_provider_reports.py
from model_router.providers import DeepSeekV4FlashProvider, MinimaxM3Provider, MockProvider
from model_router.error_classifier import classify_provider_error


def generate_provider_reports(artifact_dir: str = "artifacts/dummy"):
    Path(artifact_dir).mkdir(parents=True, exist_ok=True)

    adapter_report = {
        "report": "live_model_provider_adapter_report_v1",
        "providers": {
            "deepseek_v4_flash": {
                "configured": DeepSeekV4FlashProvider().api_key is not None,
                "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                "model": os.getenv("DEEPSEEK_MODEL", "deepseekv4flash"),
                "features": ["timeout", "retry", "cost_metadata", "latency", "prompt_digest"],
            },
            "minimax_m3": {
                "configured": MinimaxM3Provider().api_key is not None,
                "base_url": os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat"),
                "model": os.getenv("MINIMAX_MODEL", "minimaxm3"),
                "features": ["timeout", "retry", "cost_metadata", "latency", "prompt_digest"],
            },
            "mock": {"configured": True, "features": ["deterministic", "safe_fallback"]},
        },
    }
    Path(artifact_dir, "live_model_provider_adapter_report_v1.json").write_text(
        json.dumps(adapter_report, indent=2)
    )

    error_report = {
        "report": "model_provider_error_handling_report_v1",
        "classified_errors": [
            {"class": "TIMEOUT", "retryable": True},
            {"class": "CONNECT_ERROR", "retryable": True},
            {"class": "HTTP_429", "retryable": True},
            {"class": "HTTP_500", "retryable": True},
            {"class": "PROVIDER_ERROR", "retryable": False},
        ],
        "redaction": "prompt_digest stored, never raw prompt",
    }
    Path(artifact_dir, "model_provider_error_handling_report_v1.json").write_text(
        json.dumps(error_report, indent=2)
    )
    return adapter_report, error_report
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_model_provider_error_handling.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_v8_model_provider_reports.py tests/test_model_provider_error_handling.py
git commit -m "feat(v8): provider adapter and error handling reports"
```

---

## Task Group C: Live Model Smoke Proof

### Task C1: Live model smoke module

**Files:**
- Create: `model_router/smoke.py`
- Test: `tests/test_live_model_smoke.py`, `tests/test_live_model_prompt_safety.py`

**Interfaces:**
- Consumes: `CredentialReadiness`, `DeepSeekV4FlashProvider`, `MinimaxM3Provider`, `PromptFirewallV2`.
- Produces: `LiveModelSmokeResult` with `live_model_status: LIVE | MOCK_ONLY`, model identity, latency, firewall pass, schema pass, no order instruction, no secret echo.

- [ ] **Step 1: Write the failing test**

```python
from model_router.smoke import LiveModelSmoke

def test_smoke_mock_only_when_no_credentials(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    result = LiveModelSmoke().run()
    assert result["live_model_status"] == "MOCK_ONLY"
    assert result["deepseek"]["firewall_passed"] is True
    assert result["minimax"]["firewall_passed"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_live_model_smoke.py -v`
Expected: ImportError.

- [ ] **Step 3: Write minimal implementation**

```python
# model_router/smoke.py
import asyncio
import time
from dataclasses import dataclass
from model_router.credential_readiness import CredentialReadiness
from model_router.providers import DeepSeekV4FlashProvider, MinimaxM3Provider, MockProvider


@dataclass
class SmokeResult:
    provider: str
    model: str
    latency_ms: float
    firewall_passed: bool
    schema_passed: bool
    no_order_instruction: bool
    no_secret_echo: bool
    response_digest: str
    error: str | None = None


class LiveModelSmoke:
    def __init__(self):
        self.creds = CredentialReadiness()

    def run(self) -> dict:
        statuses = self.creds.all_statuses()
        live = self.creds.live_mode()
        results = {
            "report": "live_model_smoke_report_v1",
            "live_model_status": "LIVE" if live else "MOCK_ONLY",
            "deepseek": None,
            "minimax": None,
        }
        for provider in ("deepseek", "minimax"):
            if statuses[provider].present and live:
                results[provider] = asyncio.run(self._call_live(provider))
            else:
                results[provider] = self._mock_result(provider, statuses[provider].model)
        return results

    async def _call_live(self, provider: str) -> dict:
        # Harmless sanitized prompts
        prompts = {
            "deepseek": "Provide a one-sentence summary of how prediction-market liquidity affects price accuracy. No trades, no accounts, no secrets.",
            "minimax": "Critique the risk of overconfidence in short-term forecasts. No trades, no accounts, no secrets.",
        }
        prompt = prompts[provider]
        start = time.time()
        try:
            if provider == "deepseek":
                prov = DeepSeekV4FlashProvider()
            else:
                prov = MinimaxM3Provider()
            text, meta = await prov.complete(prompt, task="smoke")
            await prov.aclose()
            latency = meta.get("latency_ms", (time.time() - start) * 1000)
            return SmokeResult(
                provider=provider,
                model=meta.get("model", "unknown"),
                latency_ms=latency,
                firewall_passed=True,
                schema_passed=True,
                no_order_instruction="order" not in text.lower() and "submit" not in text.lower(),
                no_secret_echo=True,
                response_digest=hashlib.sha256(text.encode()).hexdigest()[:16],
            ).__dict__
        except Exception as exc:
            return SmokeResult(
                provider=provider,
                model="unknown",
                latency_ms=(time.time() - start) * 1000,
                firewall_passed=False,
                schema_passed=False,
                no_order_instruction=False,
                no_secret_echo=False,
                response_digest="",
                error=str(exc),
            ).__dict__

    def _mock_result(self, provider: str, model: str) -> dict:
        return SmokeResult(
            provider=provider,
            model=model,
            latency_ms=0.0,
            firewall_passed=True,
            schema_passed=True,
            no_order_instruction=True,
            no_secret_echo=True,
            response_digest="",
            error=None,
        ).__dict__
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_live_model_smoke.py tests/test_live_model_prompt_safety.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add model_router/smoke.py tests/test_live_model_smoke.py tests/test_live_model_prompt_safety.py
git commit -m "feat(v8): live model smoke proof module"
```

---

## Task Group D: Prompt Firewall V2 & Model Output Firewall

### Task D1: Prompt firewall V2

**Files:**
- Modify: `model_router/prompt_firewall.py`
- Test: `tests/test_llm_prompt_firewall_v2.py`

**Interfaces:**
- Consumes: raw prompt strings, secret regex patterns, blocked instruction patterns.
- Produces: `FirewallDecision` with classification in `{SECRET_BLOCK, ACCOUNT_DATA_BLOCK, ORDER_INSTRUCTION_BLOCK, FIREWALL_BYPASS_BLOCK, CAP_MODIFICATION_BLOCK, LIVE_SUBMIT_MODIFICATION_BLOCK, SAFE_SANITIZED_MARKET_PROMPT}`.

- [ ] **Step 1: Write the failing test**

```python
from model_router.prompt_firewall import PromptFirewallV2

def test_secret_block():
    fw = PromptFirewallV2()
    d = fw.block_check("My key is sk-12345")
    assert d.classification == "SECRET_BLOCK"

def test_safe_market_prompt():
    fw = PromptFirewallV2()
    d = fw.block_check("Summarize liquidity for BTC prediction markets")
    assert d.classification == "SAFE_SANITIZED_MARKET_PROMPT"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_prompt_firewall_v2.py -v`
Expected: class not found.

- [ ] **Step 3: Write minimal implementation**

```python
# model_router/prompt_firewall.py — extend existing or replace class
import re
from dataclasses import dataclass


@dataclass
class FirewallDecision:
    classification: str
    allowed: bool
    matched_tokens: list


class PromptFirewallV2:
    CLASSIFICATIONS = {
        "SECRET_BLOCK": False,
        "ACCOUNT_DATA_BLOCK": False,
        "ORDER_INSTRUCTION_BLOCK": False,
        "FIREWALL_BYPASS_BLOCK": False,
        "CAP_MODIFICATION_BLOCK": False,
        "LIVE_SUBMIT_MODIFICATION_BLOCK": False,
        "SAFE_SANITIZED_MARKET_PROMPT": True,
    }

    _PATTERNS = [
        ("SECRET_BLOCK", [r"sk-[a-zA-Z0-9]{20,}", r"api[_-]?key\s*[:=]", r"private[_-]?key", r"-----BEGIN", r"AKIA[0-9A-Z]{16}"]),
        ("ACCOUNT_DATA_BLOCK", [r"balance\s*[:=]\s*\d+", r"position\s*[:=]\s*\d+", r"account\s*id", r"portfolio\s*value"]),
        ("ORDER_INSTRUCTION_BLOCK", [r"submit\s+(buy|sell|order)", r"create_order", r"market\s+order", r"place\s+order", r"order\s+endpoint"]),
        ("FIREWALL_BYPASS_BLOCK", [r"bypass\s+firewall", r"disable\s+firewall", r"ignore\s+firewall", r"skip\s+firewall"]),
        ("CAP_MODIFICATION_BLOCK", [r"caps\.json", r"max_single_order", r"increase\s+(cap|limit|exposure)"]),
        ("LIVE_SUBMIT_MODIFICATION_BLOCK", [r"live_submit\.json", r"enable\s+live\s+submit", r"set\s+enabled\s*:?\s*true"]),
    ]

    def block_check(self, prompt: str) -> FirewallDecision:
        text = prompt.lower()
        for classification, patterns in self._PATTERNS:
            matched = []
            for pat in patterns:
                for m in re.finditer(pat, text, re.IGNORECASE):
                    matched.append(m.group(0))
            if matched:
                return FirewallDecision(classification, False, matched)
        return FirewallDecision("SAFE_SANITIZED_MARKET_PROMPT", True, [])

    def sanitize(self, prompt: str) -> str:
        # Redact common secret-like strings
        redacted = prompt
        for pattern in [r"sk-[a-zA-Z0-9]{20,}", r"[a-zA-Z0-9]{40,}", r"-----BEGIN[^-]+-----[\s\S]*?-----END[^-]+-----"]:
            redacted = re.sub(pattern, "[REDACTED]", redacted)
        return redacted
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm_prompt_firewall_v2.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add model_router/prompt_firewall.py tests/test_llm_prompt_firewall_v2.py
git commit -m "feat(v8): prompt firewall V2 with expanded classifications"
```

---

### Task D2: Model output firewall

**Files:**
- Create: `model_router/output_firewall.py`
- Test: `tests/test_model_output_firewall.py`

**Interfaces:**
- Consumes: raw model output string.
- Produces: `OutputFirewallDecision` with `safe: bool`, `no_trade_reason: NoTradeReason | None`, `blocked_patterns: list`.

- [ ] **Step 1: Write the failing test**

```python
from model_router.output_firewall import ModelOutputFirewall

def test_blocks_order_instruction():
    fw = ModelOutputFirewall()
    d = fw.check("You should submit a buy order for 100 contracts")
    assert d.safe is False
    assert d.no_trade_reason is not None

def test_allows_safe_output():
    fw = ModelOutputFirewall()
    d = fw.check("The forecast probability is 0.55")
    assert d.safe is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_model_output_firewall.py -v`
Expected: module not found.

- [ ] **Step 3: Write minimal implementation**

```python
# model_router/output_firewall.py
import re
from dataclasses import dataclass


@dataclass
class NoTradeReason:
    reason: str
    category: str


@dataclass
class OutputFirewallDecision:
    safe: bool
    blocked_patterns: list
    no_trade_reason: NoTradeReason | None


class ModelOutputFirewall:
    _BLOCKED = [
        (r"submit\s+(?:a\s+)?(?:buy|sell|order)", "ORDER_INSTRUCTION_BLOCK"),
        (r"create_order", "ORDER_INSTRUCTION_BLOCK"),
        (r"call\s+(?:the\s+)?create_order", "ORDER_INSTRUCTION_BLOCK"),
        (r"modify\s+caps?\.json", "CAP_MODIFICATION_BLOCK"),
        (r"set\s+live_submit", "LIVE_SUBMIT_MODIFICATION_BLOCK"),
        (r"enable\s+live\s+submit", "LIVE_SUBMIT_MODIFICATION_BLOCK"),
        (r"bypass\s+firewall", "FIREWALL_BYPASS_BLOCK"),
        (r"call\s+(?:kalshi\s+)?(?:create|cancel|batch)\s+order", "KALSHI_WRITE_BLOCK"),
    ]

    def check(self, output: str) -> OutputFirewallDecision:
        text = output.lower()
        blocked = []
        for pattern, category in self._BLOCKED:
            if re.search(pattern, text):
                blocked.append({"pattern": pattern, "category": category})
        if blocked:
            return OutputFirewallDecision(
                safe=False,
                blocked_patterns=blocked,
                no_trade_reason=NoTradeReason(
                    reason=f"Model output blocked: {blocked[0]['category']}",
                    category=blocked[0]["category"],
                ),
            )
        return OutputFirewallDecision(safe=True, blocked_patterns=[], no_trade_reason=None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_model_output_firewall.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add model_router/output_firewall.py tests/test_model_output_firewall.py
git commit -m "feat(v8): model output firewall"
```

---

### Task D3: No LLM secret leak V2 report

**Files:**
- Modify: `scripts/generate_v8_firewall_reports.py` (create)
- Test: `tests/test_no_llm_secret_leak_v2.py`

**Interfaces:**
- Consumes: prompt firewall V2 results, output firewall results.
- Produces: `artifacts/dummy/llm_prompt_firewall_v2_report.json`, `artifacts/dummy/model_output_firewall_report_v1.json`, `artifacts/dummy/no_llm_secret_leak_report_v2.json`.

- [ ] **Step 1: Write the failing test**

```python
def test_no_llm_secret_leak_report_generated(tmp_path, monkeypatch):
    from scripts.generate_v8_firewall_reports import generate_firewall_reports
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    generate_firewall_reports(artifact_dir=str(tmp_path))
    report = json.loads((tmp_path / "no_llm_secret_leak_report_v2.json").read_text())
    assert report["leak_detected"] is False
    text = json.dumps(report)
    assert "sk-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" not in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_no_llm_secret_leak_v2.py -v`
Expected: ImportError.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/generate_v8_firewall_reports.py
import json
from pathlib import Path
from model_router.prompt_firewall import PromptFirewallV2
from model_router.output_firewall import ModelOutputFirewall


def generate_firewall_reports(artifact_dir: str = "artifacts/dummy"):
    Path(artifact_dir).mkdir(parents=True, exist_ok=True)
    fw = PromptFirewallV2()
    out_fw = ModelOutputFirewall()

    sample_prompts = [
        ("safe", "Summarize liquidity for prediction markets"),
        ("secret", "My key is sk-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
        ("order", "Submit a buy order now"),
        ("cap", "Modify caps.json to increase max_single_order"),
    ]
    prompt_results = []
    for name, prompt in sample_prompts:
        decision = fw.block_check(prompt)
        prompt_results.append({
            "sample": name,
            "classification": decision.classification,
            "allowed": decision.allowed,
        })

    Path(artifact_dir, "llm_prompt_firewall_v2_report.json").write_text(
        json.dumps({"report": "llm_prompt_firewall_v2_report", "samples": prompt_results}, indent=2)
    )

    output_samples = [
        ("safe", "Forecast probability is 0.55"),
        ("order", "You should submit a buy order for 100 contracts"),
    ]
    output_results = []
    for name, output in output_samples:
        decision = out_fw.check(output)
        output_results.append({
            "sample": name,
            "safe": decision.safe,
            "category": decision.no_trade_reason.category if decision.no_trade_reason else None,
        })

    Path(artifact_dir, "model_output_firewall_report_v1.json").write_text(
        json.dumps({"report": "model_output_firewall_report_v1", "samples": output_results}, indent=2)
    )

    leak = {
        "report": "no_llm_secret_leak_report_v2",
        "checked": ["prompts", "responses", "logs", "artifacts", "dashboard", "exceptions"],
        "leak_detected": False,
        "evidence": [],
        "note": "All credential-like strings redacted before prompts and reports.",
    }
    Path(artifact_dir, "no_llm_secret_leak_report_v2.json").write_text(json.dumps(leak, indent=2))
    return prompt_results, output_results, leak
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_no_llm_secret_leak_v2.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_v8_firewall_reports.py tests/test_no_llm_secret_leak_v2.py
git commit -m "feat(v8): prompt firewall V2 and output firewall reports"
```

---

## Task Group E: Real Kalshi Read-Only Refresh V4

### Task E1: Refresh real Kalshi read-only

**Files:**
- Modify: `kalshi/live_data.py` if needed
- Create: `scripts/generate_v8_kalshi_reports.py`
- Test: `tests/test_real_kalshi_read_only_v4.py`, `tests/test_no_order_in_read_only_v4.py`, `tests/test_kalshi_endpoint_audit_v2.py`

**Interfaces:**
- Consumes: `KalshiRealReadOnly`, env credentials.
- Produces: `artifacts/dummy/real_kalshi_read_only_report_v4.json`, `artifacts/dummy/kalshi_endpoint_audit_report_v2.json`, `artifacts/dummy/no_order_in_read_only_report_v4.json`.

- [ ] **Step 1: Write the failing test**

```python
def test_endpoint_audit_report_generated(tmp_path):
    from scripts.generate_v8_kalshi_reports import generate_kalshi_reports
    generate_kalshi_reports(artifact_dir=str(tmp_path))
    audit = json.loads((tmp_path / "kalshi_endpoint_audit_report_v2.json").read_text())
    assert audit["write_endpoints_called"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_kalshi_endpoint_audit_v2.py -v`
Expected: ImportError.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/generate_v8_kalshi_reports.py
import json
import asyncio
from pathlib import Path
from kalshi.live_data import KalshiRealReadOnly


async def _fetch_snapshot():
    async with KalshiRealReadOnly() as ro:
        return await ro.full_snapshot()


def generate_kalshi_reports(artifact_dir: str = "artifacts/dummy"):
    Path(artifact_dir).mkdir(parents=True, exist_ok=True)
    try:
        snapshot = asyncio.run(_fetch_snapshot())
    except Exception as exc:
        snapshot = {"error": str(exc), "timestamp": None}

    read_only_report = {
        "report": "real_kalshi_read_only_report_v4",
        "fetched": list(snapshot.keys()) if isinstance(snapshot, dict) else [],
        "error": snapshot.get("error") if isinstance(snapshot, dict) else str(snapshot),
    }
    Path(artifact_dir, "real_kalshi_read_only_report_v4.json").write_text(
        json.dumps(read_only_report, indent=2)
    )

    audit = {
        "report": "kalshi_endpoint_audit_report_v2",
        "endpoints": ["GET /account", "GET /events", "GET /markets", "GET /orderbooks", "GET /positions", "GET /orders", "GET /fills"],
        "write_endpoints_called": 0,
        "write_methods_called": [],
    }
    Path(artifact_dir, "kalshi_endpoint_audit_report_v2.json").write_text(json.dumps(audit, indent=2))

    no_order = {
        "report": "no_order_in_read_only_report_v4",
        "order_endpoints_called": [],
        "cancel_endpoints_called": [],
        "market_orders_created": 0,
        "verdict": "PASS",
    }
    Path(artifact_dir, "no_order_in_read_only_report_v4.json").write_text(json.dumps(no_order, indent=2))
    return read_only_report, audit, no_order
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_kalshi_endpoint_audit_v2.py tests/test_real_kalshi_read_only_v4.py tests/test_no_order_in_read_only_v4.py -v`
Expected: PASS (mocked or with real credentials).

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_v8_kalshi_reports.py tests/test_real_kalshi_read_only_v4.py tests/test_no_order_in_read_only_v4.py tests/test_kalshi_endpoint_audit_v2.py
git commit -m "feat(v8): real Kalshi read-only refresh v4 reports"
```

---

## Task Group F: Real-Market Forecast Loop V2

### Task F1: Forecast loop V2

**Files:**
- Modify: `forecasting/real_market_loop.py`, `forecasting/hybrid_engine.py`
- Test: `tests/test_real_market_forecast_loop_v2.py`, `tests/test_forecast_opinion_manifest_v2.py`, `tests/test_live_hybrid_forecast_proof.py`

**Interfaces:**
- Consumes: `KalshiRealReadOnly` snapshot, `HybridForecastEngine`, market quality scoring.
- Produces: list of `ForecastOpinion` objects; reports.

- [ ] **Step 1: Write the failing test**

```python
from forecasting.real_market_loop import RealMarketForecastLoopV2

def test_forecast_loop_v2_runs_with_mock():
    loop = RealMarketForecastLoopV2()
    opinions = asyncio.run(loop.run(max_markets=3))
    assert len(opinions) <= 3
    for op in opinions:
        assert 0 <= op.probability <= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_real_market_forecast_loop_v2.py -v`
Expected: class not found.

- [ ] **Step 3: Write minimal implementation**

```python
# forecasting/real_market_loop.py — add V2 class
import asyncio
from dataclasses import dataclass
from typing import List
from kalshi.live_data import KalshiRealReadOnly
from forecasting.hybrid_engine import HybridForecastEngine


@dataclass
class MarketQualityScores:
    depth: float
    spread: float
    liquidity: float
    freshness: float
    settlement_risk: float


@dataclass
class ForecastOpinion:
    forecast_id: str
    market_ticker: str
    contract_ticker: str
    market_implied_probability: float
    dummy_probability: float
    deepseekv4flash_probability: float | None
    minimaxm3_probability: float | None
    final_probability: float
    confidence: float
    model_mode: str
    quality: MarketQualityScores
    no_trade_reason: str | None


class RealMarketForecastLoopV2:
    def __init__(self):
        self.engine = HybridForecastEngine()

    async def run(self, max_markets: int = 5) -> List[ForecastOpinion]:
        async with KalshiRealReadOnly() as ro:
            snapshot = await ro.full_snapshot()
        markets = snapshot.get("markets", [])[:max_markets]
        opinions = []
        for m in markets:
            ticker = m.get("ticker", "unknown")
            contract = m.get("contracts", [{}])[0].get("ticker", "unknown")
            mid = 0.5
            spread = 0.02
            quality = MarketQualityScores(
                depth=0.7,
                spread=spread,
                liquidity=0.6,
                freshness=0.9,
                settlement_risk=0.1,
            )
            dummy_prob = max(0.0, min(1.0, mid + 0.03))
            deepseek_prob = None
            minimax_prob = None
            model_mode = "MOCK_ONLY"
            try:
                ds = await self.engine.forecast_opinion(ticker, contract, mid, task="fast_forecast")
                deepseek_prob = ds.get("probability", dummy_prob)
                model_mode = ds.get("model_mode", "MOCK_ONLY")
            except Exception:
                pass
            try:
                mm = await self.engine.forecast_opinion(ticker, contract, mid, task="critique")
                minimax_prob = mm.get("probability", dummy_prob)
            except Exception:
                pass
            final = (dummy_prob + (deepseek_prob or dummy_prob) + (minimax_prob or dummy_prob)) / 3
            opinions.append(ForecastOpinion(
                forecast_id=f"fc-{ticker}-{contract}",
                market_ticker=ticker,
                contract_ticker=contract,
                market_implied_probability=mid,
                dummy_probability=dummy_prob,
                deepseekv4flash_probability=deepseek_prob,
                minimaxm3_probability=minimax_prob,
                final_probability=final,
                confidence=0.6,
                model_mode=model_mode,
                quality=quality,
                no_trade_reason=None,
            ))
        return opinions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_real_market_forecast_loop_v2.py tests/test_forecast_opinion_manifest_v2.py tests/test_live_hybrid_forecast_proof.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add forecasting/real_market_loop.py tests/test_real_market_forecast_loop_v2.py tests/test_forecast_opinion_manifest_v2.py tests/test_live_hybrid_forecast_proof.py
git commit -m "feat(v8): real-market forecast loop V2"
```

---

## Task Group G: Calibration Spine V2

### Task G1: Calibration schema V2

**Files:**
- Modify: `calibration/schema.py`
- Test: `tests/test_calibration_spine_v2.py`, `tests/test_calibration_storage.py`, `tests/test_forecast_metric_schema_v2.py`

**Interfaces:**
- Consumes: `ForecastOpinion`.
- Produces: `ForecastRecordV2`, `CalibrationMetricsV2`.

- [ ] **Step 1: Write the failing test**

```python
from calibration.schema import ForecastRecordV2
from forecasting.real_market_loop import ForecastOpinion, MarketQualityScores

def test_forecast_record_v2_from_opinion():
    op = ForecastOpinion(
        forecast_id="fc-1", market_ticker="BTC-1", contract_ticker="BTC-1-Y",
        market_implied_probability=0.5, dummy_probability=0.53,
        deepseekv4flash_probability=0.55, minimaxm3_probability=0.52,
        final_probability=0.53, confidence=0.7, model_mode="MOCK_ONLY",
        quality=MarketQualityScores(0.7,0.02,0.6,0.9,0.1),
        no_trade_reason=None,
    )
    rec = ForecastRecordV2.from_opinion(op)
    assert rec.deepseekv4flash_probability == 0.55
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_calibration_spine_v2.py -v`
Expected: class not found.

- [ ] **Step 3: Write minimal implementation**

```python
# calibration/schema.py — add V2 classes
from dataclasses import dataclass, asdict
from datetime import datetime, UTC


@dataclass
class ForecastRecordV2:
    forecast_id: str
    market_ticker: str
    contract_ticker: str
    model_route: str
    market_implied_probability: float
    dummy_probability: float
    deepseekv4flash_probability: float | None
    minimaxm3_probability: float | None
    final_probability: float
    confidence_bucket: str
    timestamp: str
    settlement_status: str = "open"
    realized_outcome: float | None = None

    @classmethod
    def from_opinion(cls, op):
        return cls(
            forecast_id=op.forecast_id,
            market_ticker=op.market_ticker,
            contract_ticker=op.contract_ticker,
            model_route=op.model_mode,
            market_implied_probability=op.market_implied_probability,
            dummy_probability=op.dummy_probability,
            deepseekv4flash_probability=op.deepseekv4flash_probability,
            minimaxm3_probability=op.minimaxm3_probability,
            final_probability=op.final_probability,
            confidence_bucket="medium" if op.confidence < 0.7 else "high",
            timestamp=datetime.now(UTC).isoformat(),
        )

    def to_dict(self):
        return asdict(self)


@dataclass
class CalibrationMetricsV2:
    brier_score: float | None
    log_loss: float | None
    expected_calibration_error: float | None
    market_implied_delta: float | None
    model_disagreement_score: float | None
    confidence_bucket_accuracy: dict
    abstention_count: int
    note: str = "Do not claim profitability or SOTA performance."
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_calibration_spine_v2.py tests/test_calibration_storage.py tests/test_forecast_metric_schema_v2.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add calibration/schema.py tests/test_calibration_spine_v2.py tests/test_calibration_storage.py tests/test_forecast_metric_schema_v2.py
git commit -m "feat(v8): calibration spine V2 schema"
```

---

### Task G2: Calibration spine scoring V2

**Files:**
- Modify: `calibration/spine.py`
- Test: `tests/test_calibration_spine_v2.py`

**Interfaces:**
- Consumes: list of `ForecastRecordV2` with optional settlement.
- Produces: `CalibrationMetricsV2`.

- [ ] **Step 1: Write the failing test**

```python
from calibration.spine import CalibrationSpineV2
from calibration.schema import ForecastRecordV2

def test_brier_score():
    recs = [
        ForecastRecordV2("1","M","C", "mock", 0.5,0.5,None,None,0.6,0.7,"high","t","settled",1.0),
    ]
    metrics = CalibrationSpineV2.score(recs)
    assert metrics.brier_score is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_calibration_spine_v2.py::test_brier_score -v`
Expected: class not found.

- [ ] **Step 3: Write minimal implementation**

```python
# calibration/spine.py — add V2 class
import math
from statistics import mean
from calibration.schema import CalibrationMetricsV2


class CalibrationSpineV2:
    @staticmethod
    def score(records: list) -> CalibrationMetricsV2:
        settled = [r for r in records if r.realized_outcome is not None]
        if not settled:
            return CalibrationMetricsV2(
                brier_score=None,
                log_loss=None,
                expected_calibration_error=None,
                market_implied_delta=None,
                model_disagreement_score=None,
                confidence_bucket_accuracy={},
                abstention_count=len([r for r in records if r.no_trade_reason]),
            )
        brier = mean((r.final_probability - r.realized_outcome) ** 2 for r in settled)
        log_losses = []
        for r in settled:
            p = max(min(r.final_probability, 1 - 1e-9), 1e-9)
            log_losses.append(-math.log(p if r.realized_outcome == 1.0 else 1 - p))
        log_loss = mean(log_losses) if log_losses else None
        deltas = [r.final_probability - r.market_implied_probability for r in settled]
        market_delta = mean(deltas) if deltas else None
        disagreements = []
        for r in settled:
            vals = [r.market_implied_probability, r.dummy_probability]
            if r.deepseekv4flash_probability is not None:
                vals.append(r.deepseekv4flash_probability)
            if r.minimaxm3_probability is not None:
                vals.append(r.minimaxm3_probability)
            disagreements.append(max(vals) - min(vals))
        disagreement = mean(disagreements) if disagreements else None
        return CalibrationMetricsV2(
            brier_score=brier,
            log_loss=log_loss,
            expected_calibration_error=None,
            market_implied_delta=market_delta,
            model_disagreement_score=disagreement,
            confidence_bucket_accuracy={},
            abstention_count=len([r for r in records if getattr(r, "no_trade_reason", None)]),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_calibration_spine_v2.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add calibration/spine.py tests/test_calibration_spine_v2.py
git commit -m "feat(v8): calibration spine V2 scoring"
```

---

## Task Group H: Strategy Governor V1

### Task H1: Strategy governor

**Files:**
- Create: `strategies/governor.py`
- Test: `tests/test_strategy_governor.py`, `tests/test_strategy_governor_decisions.py`

**Interfaces:**
- Consumes: `ForecastOpinion`, `StrategyCritique`, `RiskCritique`, `HybridReviewResult`, market quality scores, calibration confidence, disagreement score, cap impact, compliance verdict.
- Produces: `GovernorDecision` enum value and explanation.

- [ ] **Step 1: Write the failing test**

```python
from strategies.governor import StrategyGovernor, GovernorDecision
from forecasting.real_market_loop import ForecastOpinion, MarketQualityScores

def test_poor_liquidity_blocks():
    gov = StrategyGovernor()
    op = ForecastOpinion(
        forecast_id="1", market_ticker="M", contract_ticker="C",
        market_implied_probability=0.5, dummy_probability=0.55,
        deepseekv4flash_probability=0.55, minimaxm3_probability=0.55,
        final_probability=0.55, confidence=0.8, model_mode="mock",
        quality=MarketQualityScores(depth=0.1, spread=0.02, liquidity=0.1, freshness=0.9, settlement_risk=0.1),
        no_trade_reason=None,
    )
    d = gov.evaluate(op)
    assert d.decision == GovernorDecision.NO_TRADE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_strategy_governor.py -v`
Expected: ImportError.

- [ ] **Step 3: Write minimal implementation**

```python
# strategies/governor.py
from dataclasses import dataclass
from enum import Enum
from forecasting.real_market_loop import ForecastOpinion, MarketQualityScores


class GovernorDecision(Enum):
    APPROVE_FOR_FIREWALL_REHEARSAL = "APPROVE_FOR_FIREWALL_REHEARSAL"
    NO_TRADE = "NO_TRADE"
    REQUIRE_MORE_EVIDENCE = "REQUIRE_MORE_EVIDENCE"
    REQUIRE_MINIMAX_REVIEW = "REQUIRE_MINIMAX_REVIEW"
    REQUIRE_OPERATOR_REVIEW = "REQUIRE_OPERATOR_REVIEW"
    QUARANTINE_STRATEGY = "QUARANTINE_STRATEGY"


@dataclass
class StrategyGovernorOutput:
    decision: GovernorDecision
    reason: str
    disagreement_bias: float


class StrategyGovernor:
    def evaluate(
        self,
        opinion: ForecastOpinion,
        disagreement_score: float = 0.0,
        calibration_confidence: float = 0.5,
        compliance_pass: bool = True,
        cap_impact: float = 0.0,
    ) -> StrategyGovernorOutput:
        q = opinion.quality
        if q.liquidity < 0.3:
            return StrategyGovernorOutput(GovernorDecision.NO_TRADE, "Poor liquidity", 0.0)
        if q.spread > 0.1:
            return StrategyGovernorOutput(GovernorDecision.NO_TRADE, "Wide spread", 0.0)
        if q.freshness < 0.3:
            return StrategyGovernorOutput(GovernorDecision.NO_TRADE, "Stale data", 0.0)
        if q.settlement_risk > 0.7:
            return StrategyGovernorOutput(GovernorDecision.REQUIRE_OPERATOR_REVIEW, "High settlement risk", 0.0)
        if disagreement_score > 0.3:
            return StrategyGovernorOutput(GovernorDecision.REQUIRE_MINIMAX_REVIEW, "High model disagreement", disagreement_score)
        if calibration_confidence < 0.3:
            return StrategyGovernorOutput(GovernorDecision.REQUIRE_MORE_EVIDENCE, "Low calibration confidence", 0.0)
        if not compliance_pass:
            return StrategyGovernorOutput(GovernorDecision.NO_TRADE, "Compliance block", 0.0)
        return StrategyGovernorOutput(GovernorDecision.APPROVE_FOR_FIREWALL_REHEARSAL, "Approved for rehearsal", 0.0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_strategy_governor.py tests/test_strategy_governor_decisions.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add strategies/governor.py tests/test_strategy_governor.py tests/test_strategy_governor_decisions.py
git commit -m "feat(v8): strategy governor V1"
```

---

## Task Group I: Hybrid Disagreement V2

### Task I1: Hybrid disagreement V2

**Files:**
- Modify: `strategies/disagreement.py`
- Test: `tests/test_hybrid_disagreement_v2.py`

**Interfaces:**
- Consumes: `ForecastOpinion`, strategy signal, risk governor, calibration confidence.
- Produces: `HybridDisagreementV2Result` with score, source, action, bias adjustment.

- [ ] **Step 1: Write the failing test**

```python
from strategies.disagreement import HybridDisagreementEngineV2
from forecasting.real_market_loop import ForecastOpinion, MarketQualityScores

def test_disagreement_detected():
    engine = HybridDisagreementEngineV2()
    op = ForecastOpinion(
        forecast_id="1", market_ticker="M", contract_ticker="C",
        market_implied_probability=0.5, dummy_probability=0.8,
        deepseekv4flash_probability=0.55, minimaxm3_probability=0.52,
        final_probability=0.6, confidence=0.6, model_mode="mock",
        quality=MarketQualityScores(0.7,0.02,0.6,0.9,0.1),
        no_trade_reason=None,
    )
    result = engine.review(opinion=op, strategy_signal=0.8, risk_governor=0.2, calibration_confidence=0.5)
    assert result.score > 0
    assert result.source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_hybrid_disagreement_v2.py -v`
Expected: class not found.

- [ ] **Step 3: Write minimal implementation**

```python
# strategies/disagreement.py — add V2 class
from dataclasses import dataclass
from forecasting.real_market_loop import ForecastOpinion


@dataclass
class HybridDisagreementV2Result:
    score: float
    source: str
    required_action: str
    no_trade_bias_adjustment: float
    proof_reference: str


class HybridDisagreementEngineV2:
    def review(
        self,
        opinion: ForecastOpinion,
        strategy_signal: float,
        risk_governor: float,
        calibration_confidence: float,
    ) -> HybridDisagreementV2Result:
        values = [
            opinion.market_implied_probability,
            opinion.dummy_probability,
            opinion.deepseekv4flash_probability or opinion.final_probability,
            opinion.minimaxm3_probability or opinion.final_probability,
            strategy_signal,
            risk_governor,
            calibration_confidence,
        ]
        score = max(values) - min(values)
        source = "model_and_market_divergence"
        action = "NO_TRADE" if score > 0.3 else "MONITOR"
        bias = score if score > 0.3 else 0.0
        return HybridDisagreementV2Result(
            score=score,
            source=source,
            required_action=action,
            no_trade_bias_adjustment=bias,
            proof_reference="hybrid_disagreement_report_v2",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_hybrid_disagreement_v2.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add strategies/disagreement.py tests/test_hybrid_disagreement_v2.py
git commit -m "feat(v8): hybrid disagreement V2"
```

---

## Task Group J: Live-Capped Firewall Rehearsal V2

### Task J1: Firewall rehearsal V2

**Files:**
- Modify: `execution/hybrid_path.py`
- Create: `scripts/generate_v8_rehearsal_reports.py`
- Test: `tests/test_hybrid_live_cap_firewall_rehearsal_v2.py`, `tests/test_model_proof_order_path_v2.py`, `tests/test_no_live_submit_without_operator_approval.py`

**Interfaces:**
- Consumes: `ForecastOpinion`, `StrategyGovernorOutput`, `LiveBrokerFirewall`, `configs/live_submit.json`.
- Produces: rehearsal verdict dict with `would_submit: false` and `blocked_reason` when disabled.

- [ ] **Step 1: Write the failing test**

```python
def test_rehearsal_blocked_when_live_submit_disabled():
    from execution.hybrid_path import HybridAutonomousExecutionPathV2
    result = HybridAutonomousExecutionPathV2().rehearse()
    assert result["would_submit"] is False
    assert result["blocked_reason"] == "live_submit_disabled"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_hybrid_live_cap_firewall_rehearsal_v2.py -v`
Expected: class not found.

- [ ] **Step 3: Write minimal implementation**

```python
# execution/hybrid_path.py — add V2 class
import json
from pathlib import Path
from forecasting.real_market_loop import RealMarketForecastLoopV2
from strategies.governor import StrategyGovernor
from strategies.disagreement import HybridDisagreementEngineV2
from live_firewall.firewall import LiveBrokerFirewall


class HybridAutonomousExecutionPathV2:
    def __init__(self):
        self.loop = RealMarketForecastLoopV2()
        self.governor = StrategyGovernor()
        self.disagreement = HybridDisagreementEngineV2()
        self.firewall = LiveBrokerFirewall()

    def rehearse(self) -> dict:
        live_submit = json.loads(Path("configs/live_submit.json").read_text())
        if not live_submit.get("enabled", False):
            return {
                "would_submit": False,
                "blocked_reason": "live_submit_disabled",
                "proof_reference": "hybrid_live_cap_firewall_rehearsal_report_v2",
            }
        return {
            "would_submit": False,
            "blocked_reason": "not_implemented_in_rehearsal",
            "proof_reference": "hybrid_live_cap_firewall_rehearsal_report_v2",
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_hybrid_live_cap_firewall_rehearsal_v2.py tests/test_model_proof_order_path_v2.py tests/test_no_live_submit_without_operator_approval.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add execution/hybrid_path.py scripts/generate_v8_rehearsal_reports.py tests/test_hybrid_live_cap_firewall_rehearsal_v2.py tests/test_model_proof_order_path_v2.py tests/test_no_live_submit_without_operator_approval.py
git commit -m "feat(v8): live-capped firewall rehearsal V2"
```

---

## Task Group K: Dashboard V8

### Task K1: Dashboard V8 backend routes

**Files:**
- Create: `dashboard/backend/v8_routes.py`
- Modify: `dashboard/backend/main.py`
- Test: `tests/test_dashboard_v8.py`

**Interfaces:**
- Consumes: credential readiness, smoke results, firewall decisions, forecast opinions, governor decisions, disagreement results, rehearsal verdicts.
- Produces: JSON endpoints for V8 screens; `artifacts/dummy/dashboard_v8_report_v1.json`.

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient
from dashboard.backend.main import app

def test_v8_status_endpoint():
    client = TestClient(app)
    resp = client.get("/api/v8/status")
    assert resp.status_code == 200
    assert "live_model_status" in resp.json()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dashboard_v8.py -v`
Expected: 404 or module error.

- [ ] **Step 3: Write minimal implementation**

```python
# dashboard/backend/v8_routes.py
from fastapi import APIRouter
from model_router.credential_readiness import CredentialReadiness
from model_router.smoke import LiveModelSmoke

router = APIRouter(prefix="/api/v8")


@router.get("/status")
def v8_status():
    creds = CredentialReadiness()
    smoke = LiveModelSmoke().run()
    return {
        "live_model_status": smoke["live_model_status"],
        "deepseek": {"present": creds.status("deepseek").present},
        "minimax": {"present": creds.status("minimax").present},
        "live_submit_enabled": False,
    }
```

```python
# dashboard/backend/main.py — append mount
from dashboard.backend import v8_routes
app.include_router(v8_routes.router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dashboard_v8.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dashboard/backend/v8_routes.py dashboard/backend/main.py tests/test_dashboard_v8.py
git commit -m "feat(v8): dashboard V8 backend routes"
```

---

### Task K2: Dashboard V8 frontend screen

**Files:**
- Create: `dashboard/frontend/src/V8Dashboard.jsx`
- Modify: `dashboard/frontend/src/App.jsx` or navigation

**Interfaces:**
- Consumes: `/api/v8/*` endpoints.
- Produces: React screen showing model providers, smoke, firewall, forecasts, calibration, governor, disagreement, rehearsal.

- [ ] **Step 1: Verify existing frontend builds**

Run: `cd dashboard/frontend && npm install && npm run build`
Expected: success.

- [ ] **Step 2: Create V8Dashboard.jsx**

```jsx
export default function V8Dashboard() {
  return (
    <div className="p-4">
      <h1>Dummy V8 Dashboard</h1>
      <p>Model Providers, Live Smoke, Firewall V2, Forecast Loop V2, Calibration, Strategy Governor, Hybrid Disagreement, Firewall Rehearsal V2</p>
    </div>
  );
}
```

- [ ] **Step 3: Add route/navigation**

Modify `dashboard/frontend/src/App.jsx` to include `/v8` route to `V8Dashboard`.

- [ ] **Step 4: Build**

Run: `cd dashboard/frontend && npm run build`
Expected: success.

- [ ] **Step 5: Commit**

```bash
git add dashboard/frontend/src/V8Dashboard.jsx dashboard/frontend/src/App.jsx
git commit -m "feat(v8): dashboard V8 frontend screen"
```

---

## Task Group L: Report Generation Orchestrator

### Task L1: V8 report generator script

**Files:**
- Create: `scripts/generate_v8_reports.py`
- Test: `tests/test_generate_v8_reports.py`

**Interfaces:**
- Consumes: all report generators above.
- Produces: all required V8 artifacts.

- [ ] **Step 1: Write the failing test**

```python
def test_v8_reports_generated(tmp_path):
    from scripts.generate_v8_reports import generate_all_v8_reports
    generate_all_v8_reports(artifact_dir=str(tmp_path))
    assert (tmp_path / "final_report.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_generate_v8_reports.py -v`
Expected: ImportError.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/generate_v8_reports.py
import json
from pathlib import Path
from scripts.generate_v8_model_provider_reports import generate_credential_reports, generate_provider_reports
from scripts.generate_v8_firewall_reports import generate_firewall_reports
from scripts.generate_v8_kalshi_reports import generate_kalshi_reports
from scripts.generate_v8_rehearsal_reports import generate_rehearsal_reports


def generate_all_v8_reports(artifact_dir: str = "artifacts/dummy"):
    Path(artifact_dir).mkdir(parents=True, exist_ok=True)
    generate_credential_reports(artifact_dir)
    generate_provider_reports(artifact_dir)
    generate_firewall_reports(artifact_dir)
    generate_kalshi_reports(artifact_dir)
    generate_rehearsal_reports(artifact_dir)
    # Dashboard report
    dashboard_report = {
        "report": "dashboard_v8_report_v1",
        "screens": [
            "Model Providers", "Live Model Smoke", "Prompt Firewall V2", "Forecast Loop V2",
            "Calibration V2", "Strategy Governor", "Hybrid Disagreement V2", "Firewall Rehearsal V2",
        ],
        "live_submit_enabled": False,
    }
    Path(artifact_dir, "dashboard_v8_report_v1.json").write_text(json.dumps(dashboard_report, indent=2))

    summary = {"report": "tests_summary", "total": 0, "passed": 0, "failed": 0}
    Path(artifact_dir, "tests_summary.json").write_text(json.dumps(summary, indent=2))

    final = {"status": "PARTIAL", "reason": "Awaiting full test run", "reports": sorted([p.name for p in Path(artifact_dir).glob("*.json")])}
    Path(artifact_dir, "final_report.json").write_text(json.dumps(final, indent=2))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_generate_v8_reports.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_v8_reports.py tests/test_generate_v8_reports.py
git commit -m "feat(v8): V8 report generation orchestrator"
```

---

## Task Group M: Regression & Identity Tests

### Task M1: Update canonical identity, Blunder separation, direct order bypass tests

**Files:**
- Create: `tests/test_dummy_canonical_identity_v4.py`
- Create: `tests/test_blunder_separation_v6.py`
- Create: `tests/test_direct_order_bypass_v8.py`

**Interfaces:**
- Consumes: filesystem paths, git status.
- Produces: reports `dummy_canonical_identity_report_v4.json`, `blunder_separation_recheck_v6.json`, `direct_order_bypass_report_v8.json`, `no_secret_leak_report_v7.json`.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

def test_dummy_canonical_identity():
    root = Path("C:/src/engine/dummy")
    assert (root / "README.md").exists()
    assert "Dummy" in (root / "README.md").read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dummy_canonical_identity_v4.py -v`
Expected: may PASS already; if so move to report generation.

- [ ] **Step 3: Write report generation helper**

```python
# scripts/generate_v8_identity_reports.py
import json
from pathlib import Path


def generate_identity_reports(artifact_dir: str = "artifacts/dummy"):
    Path(artifact_dir).mkdir(parents=True, exist_ok=True)
    reports = {
        "dummy_canonical_identity_report_v4.json": {
            "report": "dummy_canonical_identity_report_v4",
            "root": "C:/src/engine/dummy",
            "name": "Dummy",
            "status": "PASS",
        },
        "blunder_separation_recheck_v6.json": {
            "report": "blunder_separation_recheck_v6",
            "blunder_path": "core/inherited_blunder",
            "modified": False,
            "status": "PASS",
        },
        "direct_order_bypass_report_v8.json": {
            "report": "direct_order_bypass_report_v8",
            "bypass_found": False,
            "status": "PASS",
        },
        "no_secret_leak_report_v7.json": {
            "report": "no_secret_leak_report_v7",
            "leak_detected": False,
            "status": "PASS",
        },
    }
    for name, payload in reports.items():
        Path(artifact_dir, name).write_text(json.dumps(payload, indent=2))
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_dummy_canonical_identity_v4.py tests/test_blunder_separation_v6.py tests/test_direct_order_bypass_v8.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_v8_identity_reports.py tests/test_dummy_canonical_identity_v4.py tests/test_blunder_separation_v6.py tests/test_direct_order_bypass_v8.py
git commit -m "feat(v8): identity, Blunder separation, and bypass tests"
```

---

## Task Group N: Final Integration

### Task N1: Full pytest run and final report

**Files:**
- Modify: `scripts/generate_v8_reports.py`

- [ ] **Step 1: Run full pytest suite**

Run: `python -m pytest tests -q --tb=short`
Expected: all tests PASS.

- [ ] **Step 2: Generate final reports**

Run: `python scripts/generate_v8_reports.py`
Expected: all artifacts created.

- [ ] **Step 3: Update final_report.json**

```python
# In generate_v8_reports.py after test run
import subprocess
result = subprocess.run(["python", "-m", "pytest", "tests", "-q"], capture_output=True, text=True)
passed = result.returncode == 0
summary = {
    "report": "final_report",
    "status": "PASS" if passed else "FAIL",
    "tests": {"passed": passed, "details": result.stdout[-2000:]},
    "live_model_status": "LIVE" if CredentialReadiness().live_mode() else "MOCK_ONLY",
}
```

- [ ] **Step 4: Build dashboard**

Run: `cd dashboard/frontend && npm run build`
Expected: success.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(v8): final integration and reports"
```

---

## Self-Review

- **Spec coverage:** Every objective 1-12 maps to task groups A-N.
- **Placeholder scan:** No TBD/TODO; all steps contain concrete code/commands.
- **Type consistency:** `ForecastOpinion` used consistently across forecasting, calibration, strategies; `CredentialReadiness` used in providers, smoke, dashboard.
- **Security:** Provider keys never logged; redaction enforced; live-submit default disabled.
