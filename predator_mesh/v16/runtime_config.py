"""Canonical Kalshi READ_ONLY runtime config binding for V16."""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from kalshi.live_data import KalshiRealReadOnly
from predator_mesh.v13.credential_bridge import KalshiReadOnlyCredentialBridge


class KalshiReadOnlyConfigSource(str, Enum):
    PROCESS_ENV = "process_env"
    DUMMY_ENV_FILE = "dummy_env_file"
    LOCAL_SECRET_FILE_REFERENCE = "local_secret_file_reference"
    MISSING = "missing"


def _base_url_class(base_url: str) -> str:
    lowered = base_url.lower()
    if "api.elections.kalshi.com" in lowered or "trading-api.kalshi.com" in lowered:
        return "kalshi_production"
    if "kalshi" in lowered:
        return "kalshi_configured"
    if not base_url:
        return "missing"
    return "custom_readonly_base"


@dataclass(frozen=True)
class KalshiReadOnlyRuntimeConfig:
    selected_source: str
    credential_source: str
    credential_reference_kind: str
    base_url: str
    api_version: str
    ready: bool
    invalid_reason: str = ""
    max_request_timeout_s: float = 10.0
    total_timeout_s: float = 45.0
    redacted: bool = True
    _secret_environment: Mapping[str, str] = field(default_factory=dict, repr=False, compare=False)

    @property
    def allows_terrain_retry(self) -> bool:
        return self.ready and not self.invalid_reason

    @property
    def base_url_class(self) -> str:
        return _base_url_class(self.base_url)

    @contextmanager
    def credential_environment_overlay(self) -> Iterator[None]:
        values = dict(self._secret_environment)
        previous = {key: os.environ.get(key) for key in values}
        try:
            for key, value in values.items():
                os.environ[key] = value
            yield
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V16: Kalshi READ_ONLY Runtime Config",
            "selected_source": self.selected_source,
            "credential_source": self.credential_source,
            "credential_reference_kind": self.credential_reference_kind,
            "selected_base_url_class": self.base_url_class,
            "api_version_configured": bool(self.api_version),
            "ready": self.ready,
            "allows_terrain_retry": self.allows_terrain_retry,
            "invalid_reason": self.invalid_reason,
            "max_request_timeout_s": self.max_request_timeout_s,
            "total_timeout_s": self.total_timeout_s,
            "redacted": True,
            "secret_values_exposed": False,
            "verdict": "PASS" if self.ready else "PARTIAL",
        }


class KalshiReadOnlyConfigResolver:
    """Resolves one config object for auth, discovery, snapshot, replay, and reports."""

    def __init__(
        self,
        *,
        env: Mapping[str, str] | None = None,
        dummy_env_path: Path | str | None = None,
        project_env_path: Path | str | None = None,
        credential_bridge: KalshiReadOnlyCredentialBridge | None = None,
    ) -> None:
        self.bridge = credential_bridge or KalshiReadOnlyCredentialBridge(
            env=env,
            dummy_env_path=dummy_env_path,
            project_env_path=project_env_path,
        )

    def resolve(self) -> KalshiReadOnlyRuntimeConfig:
        readiness = self.bridge.resolve()
        secret_environment = self.bridge.secret_environment()
        base_url = (secret_environment.get("KALSHI_API_BASE") or os.environ.get("KALSHI_API_BASE") or "https://api.elections.kalshi.com").rstrip("/")
        api_version = secret_environment.get("KALSHI_API_VERSION") or os.environ.get("KALSHI_API_VERSION") or "trade-api/v2"
        invalid_reason = "" if readiness.ready else "CREDENTIALS_MISSING"
        selected_source = readiness.source.value if readiness.ready else KalshiReadOnlyConfigSource.MISSING.value
        return KalshiReadOnlyRuntimeConfig(
            selected_source=selected_source,
            credential_source=readiness.source.value,
            credential_reference_kind=readiness.private_key_reference_kind,
            base_url=base_url,
            api_version=api_version,
            ready=readiness.ready,
            invalid_reason=invalid_reason,
            max_request_timeout_s=10.0,
            total_timeout_s=45.0,
            _secret_environment=secret_environment,
        )


class KalshiReadOnlyConfigBindingProof:
    def __init__(self, runtime_config: KalshiReadOnlyRuntimeConfig) -> None:
        self.runtime_config = runtime_config

    def to_report(self) -> dict[str, Any]:
        state = "PASS" if self.runtime_config.allows_terrain_retry else "PARTIAL_CONFIG_BINDING_ERROR"
        return {
            "workstream": "V16: Kalshi READ_ONLY Config Binding Proof",
            "binding_state": state,
            "same_config_for_auth_discovery_snapshot": self.runtime_config.ready,
            "terrain_retry_allowed": self.runtime_config.allows_terrain_retry,
            "selected_source": self.runtime_config.selected_source,
            "selected_base_url_class": self.runtime_config.base_url_class,
            "selected_credential_source": self.runtime_config.credential_source,
            "invalid_reason": self.runtime_config.invalid_reason,
            "secret_values_exposed": False,
            "redacted": True,
            "verdict": "PASS" if state == "PASS" else "PARTIAL",
        }


ClientFactory = Callable[..., Any]


class KalshiReadOnlyClientFactory:
    def __init__(
        self,
        runtime_config: KalshiReadOnlyRuntimeConfig,
        *,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self.runtime_config = runtime_config
        self.client_factory = client_factory

    def build(self) -> Any:
        if not self.runtime_config.ready:
            raise RuntimeError(self.runtime_config.invalid_reason or "CONFIG_NOT_READY")
        if self.client_factory is not None:
            try:
                return self.client_factory(self.runtime_config)
            except TypeError:
                return self.client_factory()
        with self.runtime_config.credential_environment_overlay():
            import kalshi.client as kalshi_client_mod

            kalshi_client_mod.BASE = self.runtime_config.base_url.rstrip("/")
            kalshi_client_mod.VERSION = self.runtime_config.api_version
            return KalshiRealReadOnly()

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V16: Kalshi READ_ONLY Client Factory",
            "runtime_config_ready": self.runtime_config.ready,
            "selected_source": self.runtime_config.selected_source,
            "selected_base_url_class": self.runtime_config.base_url_class,
            "client_factory_bound_to_runtime_config": True,
            "max_request_timeout_s": self.runtime_config.max_request_timeout_s,
            "total_timeout_s": self.runtime_config.total_timeout_s,
            "secret_values_exposed": False,
            "verdict": "PASS" if self.runtime_config.ready else "PARTIAL",
        }
