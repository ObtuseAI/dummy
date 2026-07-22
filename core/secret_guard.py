import os
from typing import Any

_SENSITIVE_KEYS = {
    "api_key", "apikey", "api_secret", "apisecret", "private_key",
    "password", "token", "secret", "key_id", "credential",
    "deepseek_api_key", "minimax_api_key", "openrouter_api_key",
    "authorization", "bearer",
}

_SECRET_VALUES: list[str] = []

def _load_env_secrets():
    for k, v in os.environ.items():
        if any(s in k.lower() for s in _SENSITIVE_KEYS) and v and len(v) >= 4:
            _SECRET_VALUES.append(v)

_load_env_secrets()

def _current_env_secrets() -> list[str]:
    values: list[str] = []
    for k, v in os.environ.items():
        if any(s in k.lower() for s in _SENSITIVE_KEYS) and v and len(v) >= 4:
            values.append(v)
    return values


def _secret_snapshot() -> tuple[str, ...]:
    return tuple(dict.fromkeys([*_SECRET_VALUES, *_current_env_secrets()]))


def _redact_string(text: str, secrets: tuple[str, ...] | None = None) -> str:
    for s in secrets if secrets is not None else _secret_snapshot():
        text = text.replace(s, "***REDACTED***")
    return text


def redact_text(text: str) -> str:
    """Redact known secret values from a plain string."""
    return _redact_string(text)


def _redact(obj: Any, secrets: tuple[str, ...]) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if any(s in k.lower() for s in _SENSITIVE_KEYS):
                out[k] = "***REDACTED***"
            else:
                out[k] = _redact(v, secrets)
        return out
    if isinstance(obj, list):
        return [_redact(x, secrets) for x in obj]
    if isinstance(obj, str):
        return _redact_string(obj, secrets)
    return obj


def redact(obj: Any) -> Any:
    return _redact(obj, _secret_snapshot())
