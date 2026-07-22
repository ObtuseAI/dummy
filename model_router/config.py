from __future__ import annotations
import json
from pathlib import Path
from pydantic import BaseModel, Field, StrictBool


class ProviderConfig(BaseModel):
    api_base: str
    api_key_env: str
    model_name: str
    rpm: int = 60
    tpm: int = 100000
    timeout_seconds: float = 20.0
    model_aliases: list[str] = Field(default_factory=list)
    route_mode: str | None = None
    reasoning_effort: str | None = None
    prompt_cost_per_million: float | None = None
    completion_cost_per_million: float | None = None
    # A panel call is an atomic research observation.  Exact-panel providers
    # can pin this to zero so a seven-call review cannot silently fan out into
    # as many as twenty-eight billable HTTP attempts.
    max_retries: int = Field(default=3, ge=0, le=3)


class ModelRoutingConfig(BaseModel):
    default_provider: dict[str, str] = Field(default_factory=dict)
    provider_configs: dict[str, ProviderConfig] = Field(default_factory=dict)
    hybrid_providers: list[str] = Field(default_factory=list)
    mock_fallback_enabled: bool = True
    # Never coerce strings such as "1", "yes", or "true" into paid-call
    # authority.  The JSON contract must contain a literal boolean.
    live_model_calls_enabled: StrictBool = False
    max_prompt_length: int = 16000
    blocked_prompt_categories: list[str] = Field(default_factory=lambda: [
        "secret_leak", "instruction_injection", "order_endpoint", "cap_modification"
    ])
    secret_key_env_names: list[str] = Field(default_factory=lambda: [
        "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY", "MINIMAX_API_KEY",
        "KALSHI_API_KEY_ID", "KALSHI_API_PRIVATE_KEY_PEM",
    ])


CONFIG_PATH = Path(__file__).parent.parent / "configs" / "model_routing.json"


def load_model_routing_config(path: Path | None = None) -> ModelRoutingConfig:
    target = path or CONFIG_PATH
    if target.exists():
        return ModelRoutingConfig.model_validate(json.loads(target.read_text()))
    return ModelRoutingConfig()
