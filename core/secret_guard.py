import os, re
from typing import Any

_SENSITIVE_KEYS = {
    "api_key", "apikey", "api_secret", "apisecret", "private_key",
    "password", "token", "secret", "key_id", "credential",
}

_SECRET_VALUES: list[str] = []

def _load_env_secrets():
    for k, v in os.environ.items():
        if any(s in k.lower() for s in _SENSITIVE_KEYS) and v and len(v) >= 4:
            _SECRET_VALUES.append(v)

_load_env_secrets()

def redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if any(s in k.lower() for s in _SENSITIVE_KEYS):
                out[k] = "***REDACTED***"
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    if isinstance(obj, str):
        for s in _SECRET_VALUES:
            obj = obj.replace(s, "***REDACTED***")
        return obj
    return obj
