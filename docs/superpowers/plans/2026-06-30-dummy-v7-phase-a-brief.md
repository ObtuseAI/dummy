# Phase A: Model Router + Prompt Firewall + Config + Secret Safety

**Goal:** Build the provider-agnostic hybrid model router, a prompt firewall that blocks secret leakage and instruction injection, and the configuration/secret-safety layer. The phase must pass with or without real DeepSeek/Minimax credentials.

---

## Global Constraints (Phase A)

- Do not modify canonical Blunder.
- Do not rename Dummy.
- No live order submission in this phase.
- No secrets in prompts, logs, or artifacts.
- Caps and live-submit config are read-only.
- Missing model keys must trigger deterministic `MockProvider` fallback, not failures.

---

## Files to Create / Modify

### Create

1. `configs/model_routing.json`
2. `model_router/__init__.py`
3. `model_router/config.py`
4. `model_router/tasks.py`
5. `model_router/providers.py`
6. `model_router/router.py`
7. `model_router/envelope.py`
8. `model_router/prompt_firewall.py`
9. `model_router/cost_tracker.py`

### Modify

10. `core/secret_guard.py` — add DeepSeek/Minimax key names to the sensitive-key set and ensure provider secrets are redacted from strings.
11. `.env.example` — document the optional provider env vars.

---

## Interfaces

### `model_router/tasks.py`

```python
from enum import Enum

class ModelTask(str, Enum):
    FORECAST_OPINION = "forecast_opinion"
    STRATEGY_CRITIQUE = "strategy_critique"
    RISK_CRITIQUE = "risk_critique"
    NO_TRADE_REASON = "no_trade_reason"
    TRADE_DRAFT = "trade_draft"
    CALIBRATION_NOTE = "calibration_note"
    MARKET_THESIS = "market_thesis"
    HYBRID_REVIEW = "hybrid_review"
```

### `model_router/config.py`

```python
from __future__ import annotations
import json
import os
from pathlib import Path
from pydantic import BaseModel, Field

class ProviderConfig(BaseModel):
    api_base: str
    api_key_env: str
    model_name: str
    rpm: int = 60
    tpm: int = 100000
    timeout_seconds: float = 30.0

class ModelRoutingConfig(BaseModel):
    default_provider: dict[str, str] = Field(default_factory=dict)
    provider_configs: dict[str, ProviderConfig] = Field(default_factory=dict)
    mock_fallback_enabled: bool = True
    max_prompt_length: int = 16000
    blocked_prompt_categories: list[str] = Field(default_factory=lambda: [
        "secret_leak", "instruction_injection", "order_endpoint", "cap_modification"
    ])
    secret_key_env_names: list[str] = Field(default_factory=lambda: [
        "DEEPSEEK_API_KEY", "MINIMAX_API_KEY",
        "KALSHI_API_KEY_ID", "KALSHI_API_PRIVATE_KEY_PEM",
    ])

CONFIG_PATH = Path(__file__).parent.parent / "configs" / "model_routing.json"

def load_model_routing_config(path: Path | None = None) -> ModelRoutingConfig:
    target = path or CONFIG_PATH
    if target.exists():
        return ModelRoutingConfig.model_validate(json.loads(target.read_text()))
    return ModelRoutingConfig()
```

### `configs/model_routing.json`

```json
{
  "default_provider": {
    "forecast_opinion": "deepseek_v4_flash",
    "strategy_critique": "minimax_m3",
    "risk_critique": "deepseek_v4_flash",
    "no_trade_reason": "minimax_m3",
    "trade_draft": "deepseek_v4_flash",
    "calibration_note": "minimax_m3",
    "market_thesis": "deepseek_v4_flash",
    "hybrid_review": "hybrid"
  },
  "provider_configs": {
    "deepseek_v4_flash": {
      "api_base": "https://api.deepseek.com",
      "api_key_env": "DEEPSEEK_API_KEY",
      "model_name": "deepseek-v4-flash",
      "rpm": 60,
      "tpm": 100000,
      "timeout_seconds": 30.0
    },
    "minimax_m3": {
      "api_base": "https://api.minimax.chat",
      "api_key_env": "MINIMAX_API_KEY",
      "model_name": "minimax-m3",
      "rpm": 60,
      "tpm": 100000,
      "timeout_seconds": 30.0
    }
  },
  "mock_fallback_enabled": true,
  "max_prompt_length": 16000,
  "blocked_prompt_categories": ["secret_leak", "instruction_injection", "order_endpoint", "cap_modification"],
  "secret_key_env_names": [
    "DEEPSEEK_API_KEY", "MINIMAX_API_KEY",
    "KALSHI_API_KEY_ID", "KALSHI_API_PRIVATE_KEY_PEM"
  ]
}
```

### `model_router/providers.py`

```python
from __future__ import annotations
from abc import ABC, abstractmethod
import json, os, time
from typing import Any
import httpx

from model_router.config import ProviderConfig
from model_router.tasks import ModelTask

class BaseModelProvider(ABC):
    name: str = "base"

    def __init__(self, config: ProviderConfig):
        self.config = config

    @property
    def available(self) -> bool:
        return bool(os.environ.get(self.config.api_key_env))

    @abstractmethod
    async def complete(self, prompt: str, task: ModelTask, max_tokens: int = 512, temperature: float = 0.2) -> dict[str, Any]:
        ...

class DeepSeekV4FlashProvider(BaseModelProvider):
    name = "deepseek_v4_flash"

    async def complete(self, prompt, task, max_tokens=512, temperature=0.2):
        key = os.environ.get(self.config.api_key_env)
        if not key:
            raise RuntimeError(f"{self.config.api_key_env} not set")
        body = {
            "model": self.config.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            r = await client.post(
                f"{self.config.api_base}/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=body,
            )
            r.raise_for_status()
            data = r.json()
        content = data["choices"][0]["message"]["content"]
        return {"raw": data, "content": content, "model": self.config.model_name}

class MinimaxM3Provider(BaseModelProvider):
    name = "minimax_m3"

    async def complete(self, prompt, task, max_tokens=512, temperature=0.2):
        key = os.environ.get(self.config.api_key_env)
        if not key:
            raise RuntimeError(f"{self.config.api_key_env} not set")
        body = {
            "model": self.config.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            r = await client.post(
                f"{self.config.api_base}/v1/text/chatcompletion_v2",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=body,
            )
            r.raise_for_status()
            data = r.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"raw": data, "content": content, "model": self.config.model_name}

class MockProvider(BaseModelProvider):
    name = "mock"

    def __init__(self, config: ProviderConfig | None = None):
        super().__init__(config or ProviderConfig(api_base="", api_key_env="", model_name="mock"))

    @property
    def available(self) -> bool:
        return True

    async def complete(self, prompt, task, max_tokens=512, temperature=0.2):
        deterministic = {
            ModelTask.FORECAST_OPINION: '{"dummy_probability": "0.55", "confidence_score": "0.72", "reasoning": "mock forecast"}',
            ModelTask.STRATEGY_CRITIQUE: '{"verdict": "proceed", "reasoning": "mock critique"}',
            ModelTask.NO_TRADE_REASON: '{"reason": "mock no-trade", "contributing_factors": ["mock"]}',
        }
        return {
            "raw": {"provider": "mock", "task": task.value},
            "content": deterministic.get(task, '{"note": "mock response"}'),
            "model": "mock",
        }
```

### `model_router/prompt_firewall.py`

```python
from __future__ import annotations
import re
from typing import Any
from core.secret_guard import redact, redact_text

_BLOCKED_PATTERNS = {
    "order_endpoint": [r"\bcreate_order\s*\(", r"\bcancel_order\s*\(", r"post\s+/orders", r"put\s+/orders"],
    "instruction_injection": [r"ignore\s+previous", r"disregard\s+all", r"you\s+are\s+now\s+.*operator"],
    "cap_modification": [r"max_single_order_cents", r"live_submit\.json", r"enabled\s*:\s*true"],
    "secret_leak": [r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", r"\b[A-Za-z0-9_]{32,}\b"],
}

class PromptFirewall:
    def __init__(self, blocked_categories: list[str], secret_env_names: list[str]):
        self.blocked_categories = set(blocked_categories)
        self.secret_env_names = secret_env_names

    def sanitize(self, prompt: str) -> str:
        prompt = redact_text(prompt)
        prompt = prompt.replace("\x00", "")
        prompt = re.sub(r"\s+", " ", prompt).strip()
        return prompt[:16000]

    def block_check(self, prompt: str) -> str | None:
        lowered = prompt.lower()
        for category, patterns in _BLOCKED_PATTERNS.items():
            if category not in self.blocked_categories:
                continue
            for pat in patterns:
                if re.search(pat, lowered):
                    return category
        for name in self.secret_env_names:
            value = __import__("os").environ.get(name)
            if value and len(value) >= 4 and value in prompt:
                return "secret_leak"
        return None

    def redact_response(self, text: str) -> str:
        return redact_text(text)
```

### `model_router/envelope.py`

```python
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field

from model_router.tasks import ModelTask

class ModelRouteDecision(BaseModel):
    task: ModelTask
    provider_name: str
    model_name: str
    reason: str
    fallback_reason: str | None = None

class ModelResponseEnvelope(BaseModel):
    task: ModelTask
    decision: ModelRouteDecision
    prompt: str
    content: str
    raw_metadata: dict[str, Any] = Field(default_factory=dict)
    latency_ms: float
    proof_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    blocked_by: str | None = None
```

### `model_router/router.py`

```python
from __future__ import annotations
import time
from typing import Any
from model_router.config import ModelRoutingConfig, load_model_routing_config, ProviderConfig
from model_router.envelope import ModelResponseEnvelope, ModelRouteDecision
from model_router.providers import DeepSeekV4FlashProvider, MinimaxM3Provider, MockProvider
from model_router.prompt_firewall import PromptFirewall
from model_router.tasks import ModelTask
from model_router.cost_tracker import CostTracker

_PROVIDER_CLASSES = {
    "deepseek_v4_flash": DeepSeekV4FlashProvider,
    "minimax_m3": MinimaxM3Provider,
    "mock": MockProvider,
}

class ModelRouter:
    def __init__(self, config_path: Any | None = None):
        self.config: ModelRoutingConfig = load_model_routing_config(config_path)
        self.providers: dict[str, Any] = {}
        self._init_providers()
        self.prompt_firewall = PromptFirewall(
            self.config.blocked_prompt_categories,
            self.config.secret_key_env_names,
        )
        self.cost_tracker = CostTracker()

    def _init_providers(self):
        for name, pc in self.config.provider_configs.items():
            cls = _PROVIDER_CLASSES.get(name, _PROVIDER_CLASSES["mock"])
            self.providers[name] = cls(pc)
        self.providers.setdefault("mock", MockProvider())

    def route(self, task: ModelTask) -> ModelRouteDecision:
        default = self.config.default_provider.get(task.value, "mock")
        if default == "hybrid":
            default = "deepseek_v4_flash"
        pc = self.config.provider_configs.get(default)
        model = pc.model_name if pc else "mock"
        if not self.providers[default].available:
            return ModelRouteDecision(
                task=task,
                provider_name="mock",
                model_name="mock",
                reason="preferred provider unavailable",
                fallback_reason=f"{default}_credentials_missing",
            )
        return ModelRouteDecision(
            task=task,
            provider_name=default,
            model_name=model,
            reason="task default provider",
        )

    async def call(self, task: ModelTask, prompt: str, context: dict | None = None, max_tokens: int = 512, temperature: float = 0.2) -> ModelResponseEnvelope:
        sanitized = self.prompt_firewall.sanitize(prompt)
        blocked = self.prompt_firewall.block_check(sanitized)
        if blocked:
            return ModelResponseEnvelope(
                task=task,
                decision=ModelRouteDecision(task=task, provider_name="none", model_name="none", reason="blocked"),
                prompt=sanitized,
                content="",
                raw_metadata={"context": context or {}},
                latency_ms=0.0,
                blocked_by=blocked,
            )
        decision = self.route(task)
        provider = self.providers[decision.provider_name]
        started = time.monotonic()
        raw = await provider.complete(sanitized, task, max_tokens, temperature)
        latency_ms = (time.monotonic() - started) * 1000
        safe_content = self.prompt_firewall.redact_response(str(raw.get("content")))
        envelope = ModelResponseEnvelope(
            task=task,
            decision=decision,
            prompt=sanitized,
            content=safe_content,
            raw_metadata={"model": raw.get("model"), "context": context or {}},
            latency_ms=latency_ms,
        )
        self.cost_tracker.record(envelope)
        return envelope
```

### `model_router/cost_tracker.py`

```python
from __future__ import annotations
from dataclasses import dataclass, field
from model_router.envelope import ModelResponseEnvelope

@dataclass
class CostTracker:
    calls: int = 0
    total_latency_ms: float = 0.0

    def record(self, envelope: ModelResponseEnvelope):
        self.calls += 1
        self.total_latency_ms += envelope.latency_ms

    def summary(self) -> dict:
        return {
            "calls": self.calls,
            "total_latency_ms": round(self.total_latency_ms, 4),
            "avg_latency_ms": round(self.total_latency_ms / max(self.calls, 1), 4),
        }
```

### `model_router/__init__.py`

```python
from model_router.router import ModelRouter
from model_router.envelope import ModelResponseEnvelope, ModelRouteDecision
from model_router.tasks import ModelTask

__all__ = ["ModelRouter", "ModelResponseEnvelope", "ModelRouteDecision", "ModelTask"]
```

### `core/secret_guard.py` modification

Add to `_SENSITIVE_KEYS`:

```python
_SENSITIVE_KEYS = {
    "api_key", "apikey", "api_secret", "apisecret", "private_key",
    "password", "token", "secret", "key_id", "credential",
    "deepseek_api_key", "minimax_api_key", "authorization", "bearer",
}
```

Ensure `redact_text` is exported and uses the updated key set.

### `.env.example` modification

Append:

```text
# Optional LLM provider credentials (mock fallback is used when absent)
DEEPSEEK_API_KEY=
DEEPSEEK_API_BASE=https://api.deepseek.com
MINIMAX_API_KEY=
MINIMAX_API_BASE=https://api.minimax.chat
```

---

## Tests

Create:

- `tests/test_model_routing_config.py`
- `tests/test_model_router.py`
- `tests/test_deepseekv4flash_minimaxm3_routing.py`
- `tests/test_llm_prompt_firewall.py`
- `tests/test_no_llm_secret_leak.py`

Example `tests/test_model_router.py`:

```python
import pytest
from model_router.router import ModelRouter
from model_router.tasks import ModelTask

@pytest.mark.asyncio
async def test_mock_fallback_no_keys():
    router = ModelRouter()
    envelope = await router.call(ModelTask.FORECAST_OPINION, "What is the probability?")
    assert envelope.decision.provider_name == "mock"
    assert envelope.blocked_by is None
    assert envelope.content
    assert envelope.proof_id
```

Example `tests/test_no_llm_secret_leak.py`:

```python
import os
from model_router.router import ModelRouter
from model_router.tasks import ModelTask

@pytest.mark.asyncio
async def test_prompt_redacts_secret(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-secret-1234567890abcdef")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-minimax-secret-1234567890abcdef")
    router = ModelRouter()
    prompt = "Analyze with key sk-deepseek-secret-1234567890abcdef"
    envelope = await router.call(ModelTask.FORECAST_OPINION, prompt)
    assert "sk-deepseek-secret" not in envelope.prompt
    assert "***REDACTED***" in envelope.prompt
    assert "sk-deepseek-secret" not in envelope.content
    assert "sk-minimax-secret" not in envelope.content
```

---

## Phase A Validation

```bash
cd /c/src/engine/dummy
python -m pytest tests/test_model_routing_config.py tests/test_model_router.py tests/test_deepseekv4flash_minimaxm3_routing.py tests/test_llm_prompt_firewall.py tests/test_no_llm_secret_leak.py -v
```

Expected: all tests pass with or without `DEEPSEEK_API_KEY` / `MINIMAX_API_KEY`.
```

---
