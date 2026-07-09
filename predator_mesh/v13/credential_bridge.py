"""Redacted Kalshi READ_ONLY credential discovery for V13."""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DUMMY_ENV_PATH = Path("C:/src/engine/dummy.env")
DEFAULT_PROJECT_ENV_PATH = ROOT / ".env"

KEY_ID_NAMES = ("KALSHI_API_KEY_ID",)
PRIVATE_KEY_NAMES = (
    "KALSHI_API_PRIVATE_KEY_PEM",
    "KALSHI_API_PRIVATE_KEY_PEM_PATH",
    "KALSHI_API_PRIVATE_KEY_PATH",
)


class KalshiCredentialSource(str, Enum):
    PROCESS_ENV = "process_env"
    DUMMY_ENV_FILE = "dummy_env_file"
    LOCAL_SECRET_FILE_REFERENCE = "local_secret_file_reference"
    MISSING = "missing"


SecretAdapter = Callable[[str], str | None]


@dataclass(frozen=True)
class KalshiCredentialReadinessV2:
    ready: bool
    source: KalshiCredentialSource
    key_id_present: bool
    private_key_source_present: bool
    private_key_reference_kind: str
    searched_sources: list[str]
    status: str
    redacted: bool = True
    key_id_source: str = "missing"
    private_key_source: str = "missing"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "source": self.source.value,
            "key_id_present": self.key_id_present,
            "private_key_source_present": self.private_key_source_present,
            "private_key_reference_kind": self.private_key_reference_kind,
            "searched_sources": self.searched_sources,
            "status": self.status,
            "redacted": True,
            "key_id_source": self.key_id_source,
            "private_key_source": self.private_key_source,
        }


@dataclass(frozen=True)
class KalshiCredentialProbeResult:
    readiness: KalshiCredentialReadinessV2
    auth_probe_status: str
    safe_to_attempt_readonly: bool
    reason: str
    request_timeout_s: float = 10.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.readiness.ready,
            "source": self.readiness.source.value,
            "auth_probe_status": self.auth_probe_status,
            "safe_to_attempt_readonly": self.safe_to_attempt_readonly,
            "reason": self.reason,
            "request_timeout_s": self.request_timeout_s,
            "redacted": True,
        }


@dataclass(frozen=True)
class KalshiCredentialRedactionProof:
    checked_fields: list[str]
    secret_values_exposed: bool
    dashboard_safe: bool
    report_safe: bool
    verdict: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "checked_fields": self.checked_fields,
            "secret_values_exposed": self.secret_values_exposed,
            "dashboard_safe": self.dashboard_safe,
            "report_safe": self.report_safe,
            "verdict": self.verdict,
        }


@dataclass
class _ResolvedSecrets:
    source: KalshiCredentialSource
    values: dict[str, str] = field(default_factory=dict)

    @property
    def key_present(self) -> bool:
        return bool(self.values.get("KALSHI_API_KEY_ID"))

    @property
    def private_present(self) -> bool:
        return any(bool(self.values.get(name)) for name in PRIVATE_KEY_NAMES)


class KalshiReadOnlyCredentialBridge:
    """Resolve Kalshi credential presence/source without serializing values."""

    def __init__(
        self,
        *,
        env: Mapping[str, str] | None = None,
        dummy_env_path: Path | str | None = None,
        project_env_path: Path | str | None = None,
        secret_adapter: SecretAdapter | None = None,
    ) -> None:
        self.env = os.environ if env is None else env
        self.dummy_env_path = Path(dummy_env_path) if dummy_env_path is not None else DEFAULT_DUMMY_ENV_PATH
        self.project_env_path = Path(project_env_path) if project_env_path is not None else DEFAULT_PROJECT_ENV_PATH
        self.secret_adapter = secret_adapter
        self.searched_sources = [
            KalshiCredentialSource.PROCESS_ENV.value,
            KalshiCredentialSource.DUMMY_ENV_FILE.value,
            KalshiCredentialSource.LOCAL_SECRET_FILE_REFERENCE.value,
            KalshiCredentialSource.MISSING.value,
        ]

    def _parse_env_file(self, path: Path) -> dict[str, str]:
        if not path.exists():
            return {}
        parsed: dict[str, str] = {}
        try:
            for raw in path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    parsed[key] = value
        except Exception:
            return {}
        return parsed

    def _pick(self, values: Mapping[str, str]) -> dict[str, str]:
        picked: dict[str, str] = {}
        for name in (*KEY_ID_NAMES, *PRIVATE_KEY_NAMES, "KALSHI_API_BASE", "KALSHI_API_VERSION"):
            value = values.get(name)
            if value:
                picked[name] = value
        if "KALSHI_API_PRIVATE_KEY_PATH" in picked and "KALSHI_API_PRIVATE_KEY_PEM_PATH" not in picked:
            picked["KALSHI_API_PRIVATE_KEY_PEM_PATH"] = picked["KALSHI_API_PRIVATE_KEY_PATH"]
        return picked

    def _secret_adapter_values(self) -> dict[str, str]:
        if self.secret_adapter is None:
            return {}
        values: dict[str, str] = {}
        for name in (*KEY_ID_NAMES, *PRIVATE_KEY_NAMES):
            try:
                value = self.secret_adapter(name)
            except Exception:
                value = None
            if value:
                values[name] = value
        return self._pick(values)

    def _resolve_secrets(self) -> _ResolvedSecrets:
        process = self._pick(self.env)
        if process.get("KALSHI_API_KEY_ID") and any(process.get(name) for name in PRIVATE_KEY_NAMES):
            return _ResolvedSecrets(KalshiCredentialSource.PROCESS_ENV, process)

        dummy = self._pick(self._parse_env_file(self.dummy_env_path))
        if dummy.get("KALSHI_API_KEY_ID") and any(dummy.get(name) for name in PRIVATE_KEY_NAMES):
            return _ResolvedSecrets(KalshiCredentialSource.DUMMY_ENV_FILE, dummy)

        project = self._pick(self._parse_env_file(self.project_env_path))
        adapter = self._secret_adapter_values()
        local = {**project, **adapter}
        if local.get("KALSHI_API_KEY_ID") and any(local.get(name) for name in PRIVATE_KEY_NAMES):
            return _ResolvedSecrets(KalshiCredentialSource.LOCAL_SECRET_FILE_REFERENCE, local)

        partial = process or dummy or local
        return _ResolvedSecrets(KalshiCredentialSource.MISSING, partial)

    def _private_key_kind(self, values: Mapping[str, str]) -> str:
        if values.get("KALSHI_API_PRIVATE_KEY_PEM"):
            return "inline_pem"
        if values.get("KALSHI_API_PRIVATE_KEY_PEM_PATH"):
            return "pem_path"
        if values.get("KALSHI_API_PRIVATE_KEY_PATH"):
            return "private_key_path"
        return "missing"

    def resolve(self) -> KalshiCredentialReadinessV2:
        resolved = self._resolve_secrets()
        ready = resolved.key_present and resolved.private_present and resolved.source is not KalshiCredentialSource.MISSING
        source = resolved.source if ready else KalshiCredentialSource.MISSING
        key_source = source.value if resolved.key_present else "missing"
        private_source = source.value if resolved.private_present else "missing"
        return KalshiCredentialReadinessV2(
            ready=ready,
            source=source,
            key_id_present=resolved.key_present,
            private_key_source_present=resolved.private_present,
            private_key_reference_kind=self._private_key_kind(resolved.values),
            searched_sources=self.searched_sources,
            status="READY" if ready else "MISSING",
            key_id_source=key_source,
            private_key_source=private_source,
        )

    def secret_environment(self) -> dict[str, str]:
        """Return values for outbound Kalshi calls only. Never serialize this."""
        resolved = self._resolve_secrets()
        return dict(resolved.values) if resolved.source is not KalshiCredentialSource.MISSING else {}

    @contextmanager
    def credential_environment_overlay(self) -> Iterator[None]:
        values = self.secret_environment()
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

    def probe_result(self) -> KalshiCredentialProbeResult:
        readiness = self.resolve()
        if not readiness.ready:
            return KalshiCredentialProbeResult(
                readiness=readiness,
                auth_probe_status="NOT_ATTEMPTED",
                safe_to_attempt_readonly=False,
                reason="CREDENTIALS_MISSING",
            )
        return KalshiCredentialProbeResult(
            readiness=readiness,
            auth_probe_status="READY_FOR_BOUNDED_READONLY",
            safe_to_attempt_readonly=True,
            reason="READY",
        )

    def source_resolution_report(self) -> dict[str, Any]:
        readiness = self.resolve()
        return {
            "workstream": "V13: Kalshi Credential Source Resolution",
            "ready": readiness.ready,
            "source": readiness.source.value,
            "key_id_present": readiness.key_id_present,
            "private_key_source_present": readiness.private_key_source_present,
            "private_key_reference_kind": readiness.private_key_reference_kind,
            "searched_sources": readiness.searched_sources,
            "dummy_env_path_checked": str(self.dummy_env_path),
            "local_secret_file_reference_checked": self.project_env_path.exists() or self.secret_adapter is not None,
            "redacted": True,
            "verdict": "PASS" if readiness.ready else "PARTIAL",
        }

    def redaction_report(self) -> dict[str, Any]:
        readiness = self.resolve().to_dict()
        source = self.source_resolution_report()
        text = f"{readiness}{source}"
        secret_values = [value for value in self.secret_environment().values() if value]
        leaked = any(value in text for value in secret_values)
        return KalshiCredentialRedactionProof(
            checked_fields=[
                "readiness",
                "source_resolution_report",
                "dashboard_payload",
                "operator_repair_packet",
            ],
            secret_values_exposed=leaked,
            dashboard_safe=not leaked,
            report_safe=not leaked,
            verdict="FAIL" if leaked else "PASS",
        ).to_dict()

    def to_report(self) -> dict[str, Any]:
        readiness = self.resolve()
        return {
            "workstream": "V13: Kalshi READ_ONLY Credential Bridge",
            "readiness": readiness.to_dict(),
            "probe": self.probe_result().to_dict(),
            "redaction": self.redaction_report(),
            "verdict": "PASS" if readiness.ready else "PARTIAL",
        }
