"""Deterministic, redacted model-provider credential discovery.

``ProviderCredentialSourceResolver`` searches for API keys in a fixed order:

1. Explicit process environment variables.
2. Project-root ``.env`` file (loaded by absolute path so the result does not
   depend on the current working directory).
3. An approved local secret-manager adapter, if one has been registered.
4. Redacted missing status.

Only presence/absence/source are tracked.  No API key value is returned,
logged, or written to artifacts.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable


try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - defensive fallback
    load_dotenv = None  # type: ignore[assignment]


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ENV_PATH = PROJECT_ROOT / ".env"


class ProviderCredentialSource(str, Enum):
    """Where a credential was found, or why it is missing."""

    PROCESS_ENV = "process_env"
    PROJECT_ENV = "project_env"
    SECRET_ADAPTER = "secret_adapter"
    MISSING = "missing"


SecretAdapter = Callable[[str], str | None]


@dataclass(frozen=True)
class ProviderCredentialStatusV2:
    """Redacted credential status for a model provider.

    The API key value is intentionally absent.  ``redacted`` is always True
    to signal that this structure is safe to log, serialize, and store.
    """

    present: bool
    api_key_env: str
    api_base: str
    model: str
    source: ProviderCredentialSource
    route_mode: str = "unknown"
    redacted: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "present": self.present,
            "api_key_env": self.api_key_env,
            "api_base": self.api_base,
            "model": self.model,
            "source": self.source.value,
            "route_mode": self.route_mode,
            "redacted": True,
        }


@dataclass
class CredentialResolution:
    """Result of resolving a single credential key."""

    key_name: str
    present: bool
    source: ProviderCredentialSource
    redacted: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "key_name": self.key_name,
            "present": self.present,
            "source": self.source.value,
            "redacted": True,
        }


class ProviderCredentialSourceResolver:
    """Resolve which credential source actually supplied a provider key.

    The resolver is deterministic across shells: it always loads the project
    ``.env`` from the repository root, never from the current working
    directory.  Existing process environment variables take precedence, so
    an operator export overrides the file.
    """

    def __init__(
        self,
        project_root: Path | None = None,
        secret_adapter: SecretAdapter | None = None,
    ):
        self.project_root = project_root or PROJECT_ROOT
        self.env_path = self.project_root / ".env"
        self._secret_adapter = secret_adapter
        self._project_env_cache: dict[str, str] | None = None

    def _load_project_env(self) -> dict[str, str]:
        """Return key/value pairs from the project .env without mutating os.environ."""
        if self._project_env_cache is not None:
            return self._project_env_cache

        if load_dotenv is None or not self.env_path.exists():
            self._project_env_cache = {}
            return self._project_env_cache

        # Stream the file and parse simple KEY=VALUE lines.  This avoids
        # dotenv overwriting os.environ and lets us detect the true source.
        parsed: dict[str, str] = {}
        try:
            with self.env_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key:
                        parsed[key] = value
        except Exception:
            parsed = {}

        self._project_env_cache = parsed
        return parsed

    def _secret_adapter_lookup(self, key_name: str) -> str | None:
        if self._secret_adapter is None:
            return None
        try:
            value = self._secret_adapter(key_name)
            return value
        except Exception:
            return None

    def resolve(self, key_name: str) -> CredentialResolution:
        """Return the resolution for *key_name* following the precedence chain."""
        # 1. Explicit process env.
        if os.environ.get(key_name):
            return CredentialResolution(
                key_name=key_name,
                present=True,
                source=ProviderCredentialSource.PROCESS_ENV,
            )

        # 2. Project .env.
        project_env = self._load_project_env()
        if project_env.get(key_name):
            return CredentialResolution(
                key_name=key_name,
                present=True,
                source=ProviderCredentialSource.PROJECT_ENV,
            )

        # 3. Approved local secret adapter.
        adapter_value = self._secret_adapter_lookup(key_name)
        if adapter_value:
            return CredentialResolution(
                key_name=key_name,
                present=True,
                source=ProviderCredentialSource.SECRET_ADAPTER,
            )

        # 4. Missing.
        return CredentialResolution(
            key_name=key_name,
            present=False,
            source=ProviderCredentialSource.MISSING,
        )

    def resolve_all(self, key_names: list[str]) -> dict[str, CredentialResolution]:
        return {name: self.resolve(name) for name in key_names}

    def get_value(self, key_name: str) -> str | None:
        """Return the resolved credential value without exposing it in reports.

        This is intended for authenticated outbound calls only.  Callers must
        never log, store, or echo the returned value.
        """
        # 1. Explicit process env.
        value = os.environ.get(key_name, "")
        if value:
            return value

        # 2. Project .env.
        project_env = self._load_project_env()
        value = project_env.get(key_name, "")
        if value:
            return value

        # 3. Approved local secret adapter.
        adapter_value = self._secret_adapter_lookup(key_name)
        if adapter_value:
            return adapter_value

        return None


class ProviderCredentialReadinessV2:
    """Redacted credential readiness that sources keys deterministically."""

    def __init__(
        self,
        resolver: ProviderCredentialSourceResolver | None = None,
    ):
        self.resolver = resolver or ProviderCredentialSourceResolver()

    def _base_url(self, prefix: str, default: str) -> str:
        return os.environ.get(f"{prefix}_BASE_URL") or default

    def _model(self, prefix: str, default: str) -> str:
        return os.environ.get(f"{prefix}_MODEL") or default

    def _resolve_key(
        self,
        key_name: str,
        prefix: str,
        default_base: str,
        default_model: str,
        route_mode: str = "unknown",
    ) -> ProviderCredentialStatusV2:
        resolution = self.resolver.resolve(key_name)
        return ProviderCredentialStatusV2(
            present=resolution.present,
            api_key_env=key_name,
            api_base=self._base_url(prefix, default_base),
            model=self._model(prefix, default_model),
            source=resolution.source,
            route_mode=route_mode,
        )

    def deepseek_status(self) -> ProviderCredentialStatusV2:
        return self._resolve_key(
            "DEEPSEEK_API_KEY",
            "DEEPSEEK",
            "https://api.deepseek.com",
            "deepseek-chat",
        )

    def minimax_status(self) -> ProviderCredentialStatusV2:
        return self._resolve_key(
            "MINIMAX_API_KEY",
            "MINIMAX",
            "https://api.minimax.chat",
            "minimax-01",
        )

    def openrouter_status(self) -> ProviderCredentialStatusV2:
        return self._resolve_key(
            "OPENROUTER_API_KEY",
            "OPENROUTER",
            "https://openrouter.ai/api",
            "openrouter/auto",
        )

    def all_statuses(self) -> dict[str, ProviderCredentialStatusV2]:
        return {
            "deepseek": self.deepseek_status(),
            "minimax": self.minimax_status(),
            "openrouter": self.openrouter_status(),
        }

    def ready(self, key_names: list[str]) -> bool:
        return all(self.resolver.resolve(name).present for name in key_names)
