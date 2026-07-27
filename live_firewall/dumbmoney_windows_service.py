"""Sealed private-local Windows runner for the Dummy/Kalshi venue cell.

Importing this module performs no I/O, starts no threads, and makes no network
request.  The production entry point accepts only release-manifest arguments,
loads one raw-byte SHA-256-pinned public config from ProgramData, reads secrets
only from Windows Credential Manager, and always publishes
``RECONCILIATION_ONLY`` readiness before the first network operation.
"""
from __future__ import annotations

import argparse
import base64
import ctypes
import hashlib
import json
import os
import re
import signal
import sys
import threading
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from live_firewall.dumbmoney_capital import CapitalEnvelopeAdapter
from live_firewall.dumbmoney_command_feed import (
    CommandFeedResponse,
    CoreCommandFeedConsumer,
)
from live_firewall.dumbmoney_execution_cycle import (
    SealedDisabledExecutionCycle,
)
from live_firewall.dumbmoney_lineage import (
    ContractResolutionResponse,
    CoreAuthorityContractResolver,
)
from live_firewall.dumbmoney_journal_anchor import (
    CoreJournalAnchorClient,
    JournalAnchorResponse,
)
from live_firewall.dumbmoney_reconciliation import (
    DumbMoneyKalshiReconciliationSweeper,
)
from live_firewall.exposure_tracker import (
    EXPOSURE_STATE_ANCHOR_SCHEMA,
    ExposureTracker,
)
from live_firewall.kalshi_broker_truth import (
    KalshiBrokerTruthError,
    KalshiBrokerTruthProvider,
)
from live_firewall.kalshi_reconciliation import (
    KalshiReconciliationReader,
)
from live_firewall.operational_journal import (
    canonical_json,
    sha256_json,
)
from live_firewall.sqlite_operational_journal import SQLiteOperationalJournal


SERVICE_NAME = "DumbMoneyDummyKalshi"
CONFIG_SCHEMA = "dummy.dumbmoney-kalshi-runner-config.v1"
READINESS_SCHEMA = "dumbmoney.readiness-descriptor.v1"
HEALTH_SCHEMA = "dumbmoney.health.v1"
SIGNED_ENVELOPE_SCHEMA = "dumbmoney.signed-envelope.v1"
START_MODE = "RECONCILIATION_ONLY"
CORE_ENDPOINT_REF = "endpoint-ref:DumbMoneyCore"
CELL_TOKEN_TARGET_REF = "credential-target:DumbMoney/DummyCellToken"
KALSHI_KEY_ID_TARGET_REF = "credential-target:DumbMoney/KalshiApiKeyId"
KALSHI_PRIVATE_KEY_TARGET_REF = (
    "credential-target:DumbMoney/KalshiPrivateKeyPem"
)
READINESS_KEY_TARGET_REF = (
    "credential-target:DumbMoney/DummyReadinessEd25519"
)
READINESS_REF = "readiness-ref:DumbMoneyDummyKalshi"
CONFIG_RELATIVE_PATH = (
    Path("DumbMoney") / "config" / "dummy-kalshi-runner.v1.json"
)
CORE_READINESS_RELATIVE_PATH = (
    Path("DumbMoney") / "readiness" / "DumbMoneyCore.json"
)
READINESS_RELATIVE_PATH = (
    Path("DumbMoney") / "readiness" / f"{SERVICE_NAME}.json"
)
DATA_ROOT_RELATIVE_PATH = Path("DumbMoney") / "dummy-kalshi"
MAXIMUM_CONFIG_BYTES = 262_144
MAXIMUM_READINESS_BYTES = 262_144
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_TARGET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
_KEY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,255}$")
_CONFIG_FIELDS = {
    "schema",
    "service_name",
    "release_id",
    "core_endpoint_ref",
    "core_readiness_path",
    "core_cell_token_target",
    "kalshi_key_id_target",
    "kalshi_private_key_target",
    "readiness_signing_key_target",
    "start_mode",
    "data_root",
    "readiness_ref",
    "readiness_path",
    "core_public_keys_base64url",
    "operator_public_keys_base64url",
    "promoter_public_keys_base64url",
    "research_public_keys_base64url",
    "evaluator_public_keys_base64url",
    "expected_account_hash",
    "kalshi_subaccount_number",
    "fund_lock_sha256",
    "service_manifest_sha256",
    "role_public_keys_sha256",
    "core_runner_config_sha256",
    "risk_policy_sha256",
    "readiness_signer_public_key_sha256",
    "poll_interval_seconds",
    "readiness_ttl_seconds",
    "broker_truth_max_age_seconds",
}
_CORE_READINESS_FIELDS = {
    "schema",
    "service_name",
    "release_id",
    "instance_id",
    "process_id",
    "generation",
    "observed_at",
    "valid_until",
    "endpoint",
    "fund_lock_sha256",
    "service_manifest_sha256",
    "authority",
    "health",
    "capabilities",
}


class DumbMoneyWindowsServiceError(RuntimeError):
    """A sealed runner invariant failed closed."""


class CredentialProvider(Protocol):
    def read_bytes(self, target: str) -> bytes: ...


class BrokerTruthProvider(Protocol):
    def snapshot(self) -> Mapping[str, Any]: ...


class ExecutionCycle(Protocol):
    def __call__(
        self,
        *,
        capital_adapter: CapitalEnvelopeAdapter,
        command_feed: CoreCommandFeedConsumer,
        broker_snapshot: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...


class WindowsCredentialManager:
    """Read one Windows generic credential without logging its value."""

    CRED_TYPE_GENERIC = 1

    def read_bytes(self, target: str) -> bytes:
        if not isinstance(target, str) or not _TARGET_RE.fullmatch(target):
            raise DumbMoneyWindowsServiceError(
                "Windows credential target is invalid"
            )
        if os.name != "nt":
            raise DumbMoneyWindowsServiceError(
                "Windows Credential Manager is required"
            )
        from ctypes import wintypes

        class FileTime(ctypes.Structure):
            _fields_ = [
                ("low_datetime", wintypes.DWORD),
                ("high_datetime", wintypes.DWORD),
            ]

        class CredentialAttribute(ctypes.Structure):
            _fields_ = [
                ("keyword", wintypes.LPWSTR),
                ("flags", wintypes.DWORD),
                ("value_size", wintypes.DWORD),
                ("value", ctypes.POINTER(ctypes.c_ubyte)),
            ]

        class Credential(ctypes.Structure):
            _fields_ = [
                ("flags", wintypes.DWORD),
                ("credential_type", wintypes.DWORD),
                ("target_name", wintypes.LPWSTR),
                ("comment", wintypes.LPWSTR),
                ("last_written", FileTime),
                ("credential_blob_size", wintypes.DWORD),
                ("credential_blob", ctypes.POINTER(ctypes.c_ubyte)),
                ("persist", wintypes.DWORD),
                ("attribute_count", wintypes.DWORD),
                ("attributes", ctypes.POINTER(CredentialAttribute)),
                ("target_alias", wintypes.LPWSTR),
                ("user_name", wintypes.LPWSTR),
            ]

        pointer = ctypes.POINTER(Credential)()
        advapi32 = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        cred_read = advapi32.CredReadW
        cred_read.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.POINTER(Credential)),
        ]
        cred_read.restype = wintypes.BOOL
        cred_free = advapi32.CredFree
        cred_free.argtypes = [ctypes.c_void_p]
        cred_free.restype = None
        if not cred_read(
            target,
            self.CRED_TYPE_GENERIC,
            0,
            ctypes.byref(pointer),
        ):
            code = ctypes.get_last_error()
            raise DumbMoneyWindowsServiceError(
                f"required Windows credential is unavailable; winerror={code}"
            )
        try:
            credential = pointer.contents
            size = int(credential.credential_blob_size)
            if not 1 <= size <= 65_536:
                raise DumbMoneyWindowsServiceError(
                    "Windows credential blob size is invalid"
                )
            return ctypes.string_at(credential.credential_blob, size)
        finally:
            cred_free(pointer)


@dataclass(frozen=True)
class DummyKalshiRunnerConfig:
    release_id: str
    core_readiness_path: Path
    data_root: Path
    readiness_path: Path
    core_public_keys: Mapping[str, bytes]
    operator_public_keys: Mapping[str, bytes]
    promoter_public_keys: Mapping[str, bytes]
    research_public_keys: Mapping[str, bytes]
    evaluator_public_keys: Mapping[str, bytes]
    expected_account_hash: str
    kalshi_subaccount_number: int
    fund_lock_sha256: str
    service_manifest_sha256: str
    role_public_keys_sha256: str
    core_runner_config_sha256: str
    risk_policy_sha256: str
    readiness_signer_public_key_sha256: str
    poll_interval_seconds: int
    readiness_ttl_seconds: int
    broker_truth_max_age_seconds: int
    config_sha256: str


@dataclass(frozen=True)
class RunnerSecrets:
    cell_token: str
    kalshi_key_id: str
    kalshi_private_key_pem: bytes
    readiness_private_key: Ed25519PrivateKey


@dataclass(frozen=True)
class CoreEndpoint:
    base_url: str
    instance_id: str
    observed_at: str
    valid_until: str


@dataclass
class RunnerState:
    mode: str = START_MODE
    health_status: str = "BLOCKED"
    reason: str = "RECONCILIATION_REQUIRED"
    core_ready: bool = False
    broker_truth_fresh: bool = False
    rollback_anchor_current: bool = False
    reconciled_once: bool = False
    execution_enabled: bool = False
    unresolved_open_orders: int = 0
    unresolved_positions: int = 0
    last_cycle_status: str = "not_started"


def _strict_json(raw: bytes, *, label: str) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise DumbMoneyWindowsServiceError(
                    f"{label} contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                DumbMoneyWindowsServiceError(
                    f"{label} contains non-finite value {token}"
                )
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DumbMoneyWindowsServiceError(
            f"{label} is not valid UTF-8 JSON"
        ) from exc
    if not isinstance(value, dict):
        raise DumbMoneyWindowsServiceError(f"{label} must be a JSON object")
    return value


def _digest(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise DumbMoneyWindowsServiceError(
            f"{field} must be a lowercase sha256"
        )
    return value


def _public_key_map(
    value: Any,
    *,
    role: str,
    maximum_keys: int = 16,
) -> dict[str, bytes]:
    if not isinstance(value, dict) or not 1 <= len(value) <= maximum_keys:
        raise DumbMoneyWindowsServiceError(
            f"{role} public-key map must contain 1 to {maximum_keys} keys"
        )
    result: dict[str, bytes] = {}
    for raw_key_id, raw_encoded in value.items():
        key_id = _digest(raw_key_id, field=f"{role} key id")
        if (
            not isinstance(raw_encoded, str)
            or "=" in raw_encoded
            or re.search(r"[^A-Za-z0-9_-]", raw_encoded)
        ):
            raise DumbMoneyWindowsServiceError(
                f"{role} public key encoding is invalid"
            )
        try:
            key = base64.urlsafe_b64decode(
                raw_encoded + "=" * (-len(raw_encoded) % 4)
            )
        except Exception as exc:
            raise DumbMoneyWindowsServiceError(
                f"{role} public key encoding is invalid"
            ) from exc
        if (
            len(key) != 32
            or hashlib.sha256(key).hexdigest() != key_id
        ):
            raise DumbMoneyWindowsServiceError(
                f"{role} key id does not bind its Ed25519 key"
            )
        result[key_id] = key
    return result


def _fixed_path(value: Any, *, expected: Path, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise DumbMoneyWindowsServiceError(f"{field} must be an absolute path")
    path = Path(value)
    if not path.is_absolute() or path.resolve() != expected.resolve():
        raise DumbMoneyWindowsServiceError(
            f"{field} differs from the fixed ProgramData path"
        )
    return path.resolve()


def load_runner_config(
    path: Path,
    expected_sha256: str,
    program_data: Path,
) -> DummyKalshiRunnerConfig:
    """Load the fixed public config only after exact raw-byte pinning."""
    expected_digest = _digest(expected_sha256, field="config_sha256")
    fixed = (program_data / CONFIG_RELATIVE_PATH).resolve()
    if path.resolve() != fixed:
        raise DumbMoneyWindowsServiceError(
            "runner config path is not the fixed ProgramData path"
        )
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise DumbMoneyWindowsServiceError(
            "pinned public runner config is unavailable"
        ) from exc
    if not 1 <= len(raw) <= MAXIMUM_CONFIG_BYTES:
        raise DumbMoneyWindowsServiceError("runner config size is invalid")
    if hashlib.sha256(raw).hexdigest() != expected_digest:
        raise DumbMoneyWindowsServiceError(
            "runner config does not match --config-sha256"
        )
    payload = _strict_json(raw, label="runner config")
    if set(payload) != _CONFIG_FIELDS:
        raise DumbMoneyWindowsServiceError("runner config fields mismatch")
    fixed_values = {
        "schema": CONFIG_SCHEMA,
        "service_name": SERVICE_NAME,
        "core_endpoint_ref": CORE_ENDPOINT_REF,
        "core_cell_token_target": CELL_TOKEN_TARGET_REF,
        "kalshi_key_id_target": KALSHI_KEY_ID_TARGET_REF,
        "kalshi_private_key_target": KALSHI_PRIVATE_KEY_TARGET_REF,
        "readiness_signing_key_target": READINESS_KEY_TARGET_REF,
        "start_mode": START_MODE,
        "readiness_ref": READINESS_REF,
    }
    for field, expected in fixed_values.items():
        if payload[field] != expected:
            raise DumbMoneyWindowsServiceError(
                f"runner config {field} is not sealed"
            )
    release_id = payload["release_id"]
    if (
        not isinstance(release_id, str)
        or release_id != release_id.strip()
        or not release_id
    ):
        raise DumbMoneyWindowsServiceError("release_id is invalid")
    core = _public_key_map(
        payload["core_public_keys_base64url"],
        role="Core",
    )
    operator = _public_key_map(
        payload["operator_public_keys_base64url"],
        role="operator",
    )
    promoter = _public_key_map(
        payload["promoter_public_keys_base64url"],
        role="promoter",
    )
    research = _public_key_map(
        payload["research_public_keys_base64url"],
        role="research",
    )
    evaluator = _public_key_map(
        payload["evaluator_public_keys_base64url"],
        role="evaluator",
        maximum_keys=32,
    )
    role_sets = [
        set(core),
        set(operator),
        set(promoter),
        set(research),
        set(evaluator),
    ]
    if len(set().union(*role_sets)) != sum(len(item) for item in role_sets):
        raise DumbMoneyWindowsServiceError(
            "Core/operator/promoter/research/evaluator signing roles overlap"
        )
    subaccount = payload["kalshi_subaccount_number"]
    if (
        isinstance(subaccount, bool)
        or not isinstance(subaccount, int)
        or subaccount != 0
    ):
        raise DumbMoneyWindowsServiceError(
            "kalshi_subaccount_number must be 0 until end-to-end "
            "subaccount routing is sealed"
        )
    poll_interval = payload["poll_interval_seconds"]
    ttl = payload["readiness_ttl_seconds"]
    truth_age = payload["broker_truth_max_age_seconds"]
    if (
        isinstance(poll_interval, bool)
        or not isinstance(poll_interval, int)
        or not 5 <= poll_interval <= 300
    ):
        raise DumbMoneyWindowsServiceError(
            "poll_interval_seconds must be from 5 through 300"
        )
    if (
        isinstance(ttl, bool)
        or not isinstance(ttl, int)
        or not 10 <= ttl <= 120
    ):
        raise DumbMoneyWindowsServiceError(
            "readiness_ttl_seconds must be from 10 through 120"
        )
    if (
        isinstance(truth_age, bool)
        or not isinstance(truth_age, int)
        or not 5 <= truth_age <= 120
    ):
        raise DumbMoneyWindowsServiceError(
            "broker_truth_max_age_seconds must be from 5 through 120"
        )
    return DummyKalshiRunnerConfig(
        release_id=release_id,
        core_readiness_path=_fixed_path(
            payload["core_readiness_path"],
            expected=program_data / CORE_READINESS_RELATIVE_PATH,
            field="core_readiness_path",
        ),
        data_root=_fixed_path(
            payload["data_root"],
            expected=program_data / DATA_ROOT_RELATIVE_PATH,
            field="data_root",
        ),
        readiness_path=_fixed_path(
            payload["readiness_path"],
            expected=program_data / READINESS_RELATIVE_PATH,
            field="readiness_path",
        ),
        core_public_keys=core,
        operator_public_keys=operator,
        promoter_public_keys=promoter,
        research_public_keys=research,
        evaluator_public_keys=evaluator,
        expected_account_hash=_digest(
            payload["expected_account_hash"],
            field="expected_account_hash",
        ),
        kalshi_subaccount_number=subaccount,
        fund_lock_sha256=_digest(
            payload["fund_lock_sha256"],
            field="fund_lock_sha256",
        ),
        service_manifest_sha256=_digest(
            payload["service_manifest_sha256"],
            field="service_manifest_sha256",
        ),
        role_public_keys_sha256=_digest(
            payload["role_public_keys_sha256"],
            field="role_public_keys_sha256",
        ),
        core_runner_config_sha256=_digest(
            payload["core_runner_config_sha256"],
            field="core_runner_config_sha256",
        ),
        risk_policy_sha256=_digest(
            payload["risk_policy_sha256"],
            field="risk_policy_sha256",
        ),
        readiness_signer_public_key_sha256=_digest(
            payload["readiness_signer_public_key_sha256"],
            field="readiness_signer_public_key_sha256",
        ),
        poll_interval_seconds=poll_interval,
        readiness_ttl_seconds=ttl,
        broker_truth_max_age_seconds=truth_age,
        config_sha256=expected_digest,
    )


def kalshi_account_hash(key_id: str, subaccount_number: int) -> str:
    """Bind public config to the exact Credential Manager key and subaccount."""
    if not isinstance(key_id, str) or not _KEY_ID_RE.fullmatch(key_id):
        raise DumbMoneyWindowsServiceError("Kalshi API key id is invalid")
    if (
        isinstance(subaccount_number, bool)
        or not isinstance(subaccount_number, int)
        or subaccount_number != 0
    ):
        raise DumbMoneyWindowsServiceError(
            "Kalshi subaccount must be 0 until end-to-end routing is sealed"
        )
    return hashlib.sha256(
        canonical_json(
            {
                "schema": "dummy.kalshi-account-binding.v1",
                "venue": "dummy_kalshi",
                "api_key_id": key_id,
                "subaccount_number": subaccount_number,
            }
        ).encode("utf-8")
    ).hexdigest()


def _credential_target(reference: str, expected: str) -> str:
    if reference != expected or not reference.startswith("credential-target:"):
        raise DumbMoneyWindowsServiceError(
            "credential reference is not the sealed target"
        )
    return reference.removeprefix("credential-target:")


def _secret_text(raw: bytes, *, label: str, minimum: int = 16) -> str:
    try:
        value = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DumbMoneyWindowsServiceError(
            f"{label} credential is not UTF-8"
        ) from exc
    if (
        not minimum <= len(value) <= 65_536
        or value != value.strip()
        or "\0" in value
    ):
        raise DumbMoneyWindowsServiceError(
            f"{label} credential shape is invalid"
        )
    return value


def _readiness_private_key(raw: bytes) -> Ed25519PrivateKey:
    if len(raw) == 32:
        return Ed25519PrivateKey.from_private_bytes(raw)
    try:
        key = serialization.load_pem_private_key(raw, password=None)
    except (TypeError, ValueError) as exc:
        raise DumbMoneyWindowsServiceError(
            "readiness signing credential is not a private key"
        ) from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise DumbMoneyWindowsServiceError(
            "readiness signing credential must be Ed25519"
        )
    return key


def load_secrets(
    provider: CredentialProvider,
    config: DummyKalshiRunnerConfig,
) -> RunnerSecrets:
    """Load exactly four sealed targets; there is no env or file fallback."""
    cell_token = _secret_text(
        provider.read_bytes(
            _credential_target(
                CELL_TOKEN_TARGET_REF,
                CELL_TOKEN_TARGET_REF,
            )
        ),
        label="cell bearer",
        minimum=32,
    )
    key_id = _secret_text(
        provider.read_bytes(
            _credential_target(
                KALSHI_KEY_ID_TARGET_REF,
                KALSHI_KEY_ID_TARGET_REF,
            )
        ),
        label="Kalshi key id",
        minimum=8,
    )
    if not _KEY_ID_RE.fullmatch(key_id):
        raise DumbMoneyWindowsServiceError("Kalshi key id is invalid")
    private_pem = provider.read_bytes(
        _credential_target(
            KALSHI_PRIVATE_KEY_TARGET_REF,
            KALSHI_PRIVATE_KEY_TARGET_REF,
        )
    )
    if not 128 <= len(private_pem) <= 65_536:
        raise DumbMoneyWindowsServiceError(
            "Kalshi private-key credential size is invalid"
        )
    try:
        kalshi_private_key = serialization.load_pem_private_key(
            private_pem,
            password=None,
        )
    except (TypeError, ValueError) as exc:
        raise DumbMoneyWindowsServiceError(
            "Kalshi private-key credential is invalid"
        ) from exc
    if (
        not isinstance(kalshi_private_key, RSAPrivateKey)
        or kalshi_private_key.key_size < 2_048
    ):
        raise DumbMoneyWindowsServiceError(
            "Kalshi private-key credential must be RSA with at least 2048 bits"
        )
    readiness = _readiness_private_key(
        provider.read_bytes(
            _credential_target(
                READINESS_KEY_TARGET_REF,
                READINESS_KEY_TARGET_REF,
            )
        )
    )
    readiness_public = readiness.public_key().public_bytes_raw()
    if (
        hashlib.sha256(readiness_public).hexdigest()
        != config.readiness_signer_public_key_sha256
    ):
        raise DumbMoneyWindowsServiceError(
            "readiness signing credential does not match public config"
        )
    if (
        kalshi_account_hash(key_id, config.kalshi_subaccount_number)
        != config.expected_account_hash
    ):
        raise DumbMoneyWindowsServiceError(
            "Kalshi Credential Manager key/subaccount differs from account pin"
        )
    return RunnerSecrets(
        cell_token=cell_token,
        kalshi_key_id=key_id,
        kalshi_private_key_pem=bytes(private_pem),
        readiness_private_key=readiness,
    )


def _parse_utc(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise DumbMoneyWindowsServiceError(f"{field} must be RFC3339 UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise DumbMoneyWindowsServiceError(
            f"{field} must be RFC3339 UTC"
        ) from exc
    return parsed.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _core_endpoint_from_readiness(
    config: DummyKalshiRunnerConfig,
    *,
    now: datetime,
) -> CoreEndpoint:
    try:
        raw = config.core_readiness_path.read_bytes()
    except OSError as exc:
        raise DumbMoneyWindowsServiceError(
            "signed Core readiness is unavailable"
        ) from exc
    if not 1 <= len(raw) <= MAXIMUM_READINESS_BYTES:
        raise DumbMoneyWindowsServiceError(
            "signed Core readiness size is invalid"
        )
    envelope = _strict_json(raw, label="signed Core readiness")
    from live_firewall.dumbmoney_capital import verify_signed_envelope

    try:
        signed = verify_signed_envelope(
            envelope,
            trusted_public_keys=config.core_public_keys,
            now=now,
            expected_body_schema=READINESS_SCHEMA,
            max_ttl=timedelta(seconds=120),
        )
    except ValueError as exc:
        raise DumbMoneyWindowsServiceError(
            f"signed Core readiness is invalid: {exc}"
        ) from exc
    body = signed.body
    if set(body) != _CORE_READINESS_FIELDS:
        raise DumbMoneyWindowsServiceError(
            "Core readiness descriptor fields mismatch"
        )
    if (
        body["schema"] != READINESS_SCHEMA
        or body["service_name"] != "DumbMoneyCore"
        or body["release_id"] != config.release_id
    ):
        raise DumbMoneyWindowsServiceError(
            "Core readiness identity or release mismatch"
        )
    observed = _parse_utc(body["observed_at"], field="Core observed_at")
    valid = _parse_utc(body["valid_until"], field="Core valid_until")
    if (
        not observed <= now < valid
        or signed.not_before != observed
        or signed.expires_at != valid
    ):
        raise DumbMoneyWindowsServiceError(
            "Core readiness window is invalid"
        )
    if (
        body["fund_lock_sha256"] != config.fund_lock_sha256
        or body["service_manifest_sha256"]
        != config.service_manifest_sha256
    ):
        raise DumbMoneyWindowsServiceError("Core readiness release pin mismatch")
    authority = body["authority"]
    if authority != {
        "broker": "NONE",
        "mode": "OFFLINE",
        "execution_enabled": False,
    }:
        raise DumbMoneyWindowsServiceError(
            "Core readiness claims broker authority"
        )
    health = body["health"]
    if not isinstance(health, dict):
        raise DumbMoneyWindowsServiceError("Core health is invalid")
    expected_health = {
        "role_public_keys_sha256": config.role_public_keys_sha256,
        "runner_config_sha256": config.core_runner_config_sha256,
        "risk_policy_sha256": config.risk_policy_sha256,
    }
    for field, expected in expected_health.items():
        if health.get(field) != expected:
            raise DumbMoneyWindowsServiceError(
                f"Core health pin mismatch: {field}"
            )
    if health.get("status") not in {"READY", "DEGRADED"}:
        raise DumbMoneyWindowsServiceError("Core readiness is blocked")
    endpoint = body["endpoint"]
    if not isinstance(endpoint, dict) or set(endpoint) != {
        "transport",
        "host",
        "port",
        "base_path",
    }:
        raise DumbMoneyWindowsServiceError("Core endpoint is invalid")
    host = endpoint["host"]
    port = endpoint["port"]
    if (
        endpoint["transport"] != "http"
        or host not in {"127.0.0.1", "::1"}
        or endpoint["base_path"] != "/"
        or isinstance(port, bool)
        or not isinstance(port, int)
        or not 1024 <= port <= 65_535
    ):
        raise DumbMoneyWindowsServiceError(
            "Core endpoint is not literal loopback HTTP"
        )
    instance_id = body["instance_id"]
    try:
        if str(uuid.UUID(instance_id)) != instance_id:
            raise ValueError
    except (AttributeError, ValueError) as exc:
        raise DumbMoneyWindowsServiceError(
            "Core instance id is invalid"
        ) from exc
    base = f"http://[{host}]:{port}" if host == "::1" else f"http://{host}:{port}"
    return CoreEndpoint(
        base_url=base,
        instance_id=instance_id,
        observed_at=body["observed_at"],
        valid_until=body["valid_until"],
    )


class LoopbackCoreTransport:
    """No-proxy, no-redirect transport pinned to a validated Core endpoint."""

    def __init__(self) -> None:
        self._endpoint: CoreEndpoint | None = None
        self._client = httpx.Client(
            timeout=5.0,
            follow_redirects=False,
            trust_env=False,
        )

    def set_endpoint(self, endpoint: CoreEndpoint) -> None:
        parsed = urlsplit(endpoint.base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "::1"}
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise DumbMoneyWindowsServiceError(
                "Core transport endpoint is not literal loopback"
            )
        self._endpoint = endpoint

    def _get(
        self,
        path: str,
        headers: Mapping[str, str],
    ) -> tuple[int, bytes]:
        endpoint = self._endpoint
        if endpoint is None:
            raise DumbMoneyWindowsServiceError(
                "Core endpoint has not been authenticated"
            )
        if (
            not isinstance(path, str)
            or not path.startswith("/")
            or path.startswith("//")
            or "\\" in path
        ):
            raise DumbMoneyWindowsServiceError("Core request path is invalid")
        response = self._client.get(
            f"{endpoint.base_url}{path}",
            headers=dict(headers),
        )
        return response.status_code, bytes(response.content)

    def command_get(
        self,
        path: str,
        headers: Mapping[str, str],
    ) -> CommandFeedResponse:
        status, body = self._get(path, headers)
        return CommandFeedResponse(
            status_code=status,
            body=body,
        )

    def contract_get(
        self,
        path: str,
        headers: Mapping[str, str],
    ) -> ContractResolutionResponse:
        status, body = self._get(path, headers)
        return ContractResolutionResponse(
            status_code=status,
            body=body,
        )

    def journal_anchor_post(
        self,
        path: str,
        headers: Mapping[str, str],
        body: bytes,
    ) -> JournalAnchorResponse:
        endpoint = self._endpoint
        if endpoint is None:
            raise DumbMoneyWindowsServiceError(
                "Core endpoint has not been authenticated"
            )
        if (
            path
            != "/v1/cells/dummy_kalshi/journal-heads:anchor"
            or not isinstance(body, bytes)
            or not 1 <= len(body) <= 262_144
        ):
            raise DumbMoneyWindowsServiceError(
                "Core journal anchor request is invalid"
            )
        response = self._client.post(
            f"{endpoint.base_url}{path}",
            headers=dict(headers),
            content=body,
        )
        return JournalAnchorResponse(
            status_code=response.status_code,
            body=bytes(response.content),
        )

    def liveness(self) -> None:
        endpoint = self._endpoint
        if endpoint is None:
            raise DumbMoneyWindowsServiceError(
                "Core endpoint has not been authenticated"
            )
        response = self._client.get(
            f"{endpoint.base_url}/health/live",
            headers={"Accept": "application/json"},
        )
        if response.status_code != 200 or len(response.content) > 16_384:
            raise DumbMoneyWindowsServiceError("Core liveness probe failed")
        if _strict_json(
            bytes(response.content),
            label="Core liveness",
        ) != {"schema": HEALTH_SCHEMA, "status": "LIVE"}:
            raise DumbMoneyWindowsServiceError(
                "Core liveness payload is invalid"
            )

    def close(self) -> None:
        self._client.close()


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    )
    encoded = canonical_json(dict(payload)).encode("utf-8") + b"\n"
    try:
        with temporary.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class _HealthServer:
    def __init__(self, state_reader: Callable[[], RunnerState]) -> None:
        read_state = state_reader

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/health/live":
                    self._write(
                        200,
                        {"schema": HEALTH_SCHEMA, "status": "LIVE"},
                    )
                    return
                if self.path == "/health/ready":
                    state = read_state()
                    ready = (
                        state.health_status == "READY"
                        and state.reconciled_once
                    )
                    self._write(
                        200 if ready else 503,
                        {
                            "schema": HEALTH_SCHEMA,
                            "status": "READY" if ready else "NOT_READY",
                            "reason_codes": [] if ready else [state.reason],
                        },
                    )
                    return
                self._write(
                    404,
                    {"schema": HEALTH_SCHEMA, "status": "NOT_FOUND"},
                )

            def _write(self, status: int, payload: Mapping[str, Any]) -> None:
                encoded = canonical_json(dict(payload)).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, _format: str, *_args: Any) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            name=f"{SERVICE_NAME}-health",
            daemon=True,
        )

    @property
    def port(self) -> int:
        return int(self.server.server_address[1])

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5.0)


class DumbMoneyDummyKalshiService:
    """Continuous control/reconciliation supervisor; never a second order sink."""

    def __init__(
        self,
        config: DummyKalshiRunnerConfig,
        secrets: RunnerSecrets,
        *,
        core_transport: LoopbackCoreTransport,
        broker_truth: BrokerTruthProvider,
        execution_cycle: ExecutionCycle | None = None,
        reconciliation_sweeper: (
            DumbMoneyKalshiReconciliationSweeper | None
        ) = None,
        journal_anchor_client: CoreJournalAnchorClient | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.config = config
        self.secrets = secrets
        self.core_transport = core_transport
        self.broker_truth = broker_truth
        self.execution_cycle = execution_cycle
        self._reconciliation_sweeper = reconciliation_sweeper
        self._journal_anchor_client = journal_anchor_client
        self.clock = clock
        self.instance_id = str(uuid.uuid4())
        self._state = RunnerState()
        self._state_lock = threading.Lock()
        self._readiness_sequence = 0
        self._health = _HealthServer(self.state)
        self._components_ready = False
        self._capital_adapter: CapitalEnvelopeAdapter | None = None
        self._command_feed: CoreCommandFeedConsumer | None = None
        self._capital_journal: SQLiteOperationalJournal | None = None
        self._command_journal: SQLiteOperationalJournal | None = None
        self._exposure_tracker: ExposureTracker | None = None

    def state(self) -> RunnerState:
        with self._state_lock:
            return RunnerState(**self._state.__dict__)

    def _set_state(self, **changes: Any) -> None:
        with self._state_lock:
            for field, value in changes.items():
                setattr(self._state, field, value)

    def _clock(self) -> datetime:
        now = self.clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise DumbMoneyWindowsServiceError(
                "runner clock must be timezone-aware"
            )
        return now.astimezone(timezone.utc)

    def start(self) -> None:
        """Publish blocked readiness without any Core or broker call."""
        self.config.data_root.mkdir(parents=True, exist_ok=True)
        self.config.readiness_path.parent.mkdir(parents=True, exist_ok=True)
        self._health.start()
        self.write_readiness()

    def close(self) -> None:
        try:
            broker_close = getattr(self.broker_truth, "close", None)
            if callable(broker_close):
                broker_close()
        finally:
            try:
                self._health.close()
            finally:
                try:
                    if self._command_journal is not None:
                        self._command_journal.close()
                        self._command_journal = None
                finally:
                    try:
                        if self._capital_journal is not None:
                            self._capital_journal.close()
                            self._capital_journal = None
                    finally:
                        self.core_transport.close()

    def _initialize_components(self) -> None:
        if self._components_ready:
            return
        capital_journal = SQLiteOperationalJournal(
            self.config.data_root / "capital-operational.db",
            now_fn=self._clock,
        )
        if not capital_journal.healthy:
            capital_journal.close()
            raise DumbMoneyWindowsServiceError(
                "capital operational journal is unhealthy"
            )
        command_journal: SQLiteOperationalJournal | None = None
        try:
            resolver = CoreAuthorityContractResolver(
                transport=self.core_transport.contract_get,
                cell_token_provider=lambda: self.secrets.cell_token,
                trusted_core_public_keys=self.config.core_public_keys,
                trusted_research_public_keys=self.config.research_public_keys,
                trusted_promoter_public_keys=self.config.promoter_public_keys,
                trusted_evaluator_public_keys=self.config.evaluator_public_keys,
                now_fn=self._clock,
            )
            adapter = CapitalEnvelopeAdapter(
                journal=capital_journal,
                trusted_public_keys=self.config.core_public_keys,
                expected_venue="dummy_kalshi",
                expected_account_hash=self.config.expected_account_hash,
                lineage_resolver=resolver,
                trusted_broker_witness_public_keys={
                    self.config.readiness_signer_public_key_sha256: (
                        self.secrets.readiness_private_key.public_key()
                    )
                },
                now_fn=self._clock,
                max_bootstrap_age=timedelta(
                    seconds=self.config.broker_truth_max_age_seconds
                ),
            )

            def reduce_authority(_command: Any) -> None:
                self._set_state(
                    mode=START_MODE,
                    health_status="BLOCKED",
                    reason="CORE_AUTHORITY_REDUCED",
                    execution_enabled=False,
                )

            def fail_closed(reason: str) -> None:
                self._set_state(
                    mode=START_MODE,
                    health_status="BLOCKED",
                    reason=reason,
                    core_ready=False,
                    execution_enabled=False,
                )

            command_journal = SQLiteOperationalJournal(
                self.config.data_root / "command-feed.db",
                now_fn=self._clock,
            )
            if not command_journal.healthy:
                raise DumbMoneyWindowsServiceError(
                    "command-feed operational journal is unhealthy"
                )
            command_feed = CoreCommandFeedConsumer(
                transport=self.core_transport.command_get,
                cell_token_provider=lambda: self.secrets.cell_token,
                state_journal=command_journal,
                trusted_operator_public_keys=self.config.operator_public_keys,
                trusted_checkpoint_public_keys=self.config.core_public_keys,
                capital_adapter=adapter,
                kill_handler=reduce_authority,
                mode_handler=reduce_authority,
                fail_closed_handler=fail_closed,
                now_fn=self._clock,
            )
            exposure = ExposureTracker(
                persist=True,
                state_path=(
                    self.config.data_root
                    / "live-exposure-state.json"
                ),
            )
            if not exposure.state_healthy:
                raise DumbMoneyWindowsServiceError(
                    "live exposure projection is unhealthy"
                )
            if (
                self._reconciliation_sweeper is None
                and isinstance(
                    self.broker_truth,
                    KalshiBrokerTruthProvider,
                )
            ):
                reader = KalshiReconciliationReader(
                    broker_truth=self.broker_truth,
                    witness_signing_private_key=(
                        self.secrets.readiness_private_key
                    ),
                )
                self._reconciliation_sweeper = (
                    DumbMoneyKalshiReconciliationSweeper(
                        capital_adapter=adapter,
                        broker_reader=reader,
                        exposure_tracker=exposure,
                    )
                )
            if self._journal_anchor_client is None:
                self._journal_anchor_client = CoreJournalAnchorClient(
                    transport=self.core_transport.journal_anchor_post,
                    cell_token_provider=lambda: self.secrets.cell_token,
                    trusted_core_public_keys=self.config.core_public_keys,
                    expected_account_hash=(
                        self.config.expected_account_hash
                    ),
                    now_fn=self._clock,
                )
        except BaseException:
            if command_journal is not None:
                command_journal.close()
            capital_journal.close()
            raise
        self._capital_adapter = adapter
        self._command_feed = command_feed
        self._capital_journal = capital_journal
        self._command_journal = command_journal
        self._exposure_tracker = exposure
        self._components_ready = True

    def _anchor_local_state(self) -> None:
        client = self._journal_anchor_client
        capital = self._capital_journal
        command = self._command_journal
        exposure = self._exposure_tracker
        if (
            client is None
            or capital is None
            or command is None
            or exposure is None
        ):
            raise DumbMoneyWindowsServiceError(
                "rollback anchor components are unavailable"
            )
        capital_sequence, capital_head = capital.head()
        command_sequence, command_head = command.head()
        exposure_sequence, exposure_head = exposure.anchor_head()
        sources = (
            (
                "capital-operational",
                "dummy.sqlite-operational-journal.v1",
                capital_sequence,
                capital_head,
            ),
            (
                "command-feed",
                "dummy.sqlite-operational-journal.v1",
                command_sequence,
                command_head,
            ),
            (
                "live-exposure",
                EXPOSURE_STATE_ANCHOR_SCHEMA,
                exposure_sequence,
                exposure_head,
            ),
        )
        for name, schema, sequence, head in sources:
            client.anchor(
                journal_name=name,
                journal_schema=schema,
                journal_sequence=sequence,
                journal_head_sha256=head,
            )

    def _record_broker_truth(self, raw: Mapping[str, Any]) -> tuple[int, int]:
        payload = json.loads(canonical_json(dict(raw)))
        required = {
            "schema",
            "venue",
            "account_hash",
            "subaccount_number",
            "observed_at",
            "broker_snapshot_sha256",
            "flat_book_observed",
            "total_exposure_cents",
            "open_order_count",
            "market_exposure_cents",
            "correlated_exposure_cents",
            "unresolved_open_orders",
            "unresolved_positions",
        }
        if set(payload) != required:
            raise DumbMoneyWindowsServiceError(
                "broker truth snapshot fields mismatch"
            )
        if (
            payload["schema"] != "dummy.kalshi-broker-truth.v1"
            or payload["venue"] != "dummy_kalshi"
            or payload["account_hash"] != self.config.expected_account_hash
            or payload["subaccount_number"]
            != self.config.kalshi_subaccount_number
        ):
            raise DumbMoneyWindowsServiceError(
                "broker truth identity mismatch"
            )
        observed = _parse_utc(
            payload["observed_at"],
            field="broker truth observed_at",
        )
        now = self._clock()
        if (
            observed > now + timedelta(seconds=5)
            or now - observed
            > timedelta(seconds=self.config.broker_truth_max_age_seconds)
        ):
            raise DumbMoneyWindowsServiceError("broker truth is stale")
        _digest(
            payload["broker_snapshot_sha256"],
            field="broker_snapshot_sha256",
        )
        integers = (
            "total_exposure_cents",
            "open_order_count",
            "unresolved_open_orders",
            "unresolved_positions",
        )
        for field in integers:
            value = payload[field]
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise DumbMoneyWindowsServiceError(
                    f"broker truth {field} is invalid"
                )
        unresolved_orders = payload["unresolved_open_orders"]
        unresolved_positions = payload["unresolved_positions"]
        flat = (
            payload["flat_book_observed"] is True
            and payload["total_exposure_cents"] == 0
            and payload["open_order_count"] == 0
            and unresolved_orders == 0
            and unresolved_positions == 0
            and payload["market_exposure_cents"] == {}
            and payload["correlated_exposure_cents"] == {}
        )
        if payload["flat_book_observed"] is not flat:
            raise DumbMoneyWindowsServiceError(
                "broker flat-book projection is inconsistent"
            )
        assert self._capital_adapter is not None
        receipt = {
            "schema": (
                "dummy.broker-bootstrap.flat.v1"
                if flat
                else "dummy.broker-bootstrap.inherited-exposure.v1"
            ),
            "receipt_id": sha256_json(payload),
            "venue": payload["venue"],
            "account_hash": payload["account_hash"],
            "observed_at": payload["observed_at"],
            "broker_snapshot_sha256": payload["broker_snapshot_sha256"],
            "flat_book_observed": flat,
            "total_exposure_cents": payload["total_exposure_cents"],
            "open_order_count": payload["open_order_count"],
            "market_exposure_cents": payload["market_exposure_cents"],
            "correlated_exposure_cents": payload[
                "correlated_exposure_cents"
            ],
        }
        self._capital_adapter.record_broker_bootstrap(receipt)
        return unresolved_orders, unresolved_positions

    def run_once(self) -> Mapping[str, Any]:
        """Poll controls and broker truth once; writes remain disabled on pass one."""
        now = self._clock()
        prior = self.state()
        try:
            endpoint = _core_endpoint_from_readiness(
                self.config,
                now=now,
            )
            self.core_transport.set_endpoint(endpoint)
            self.core_transport.liveness()
            self._initialize_components()
            self._anchor_local_state()
            assert self._command_feed is not None
            poll = self._command_feed.poll_once()
            core_ready = (
                poll.page_accepted
                and poll.submission_allowed
                and self._command_feed.submission_allowed()
            )
            truth = self.broker_truth.snapshot()
            unresolved_orders, unresolved_positions = (
                self._record_broker_truth(truth)
            )
            if self._reconciliation_sweeper is not None:
                sweep = self._reconciliation_sweeper.run_once()
                unresolved_orders += int(
                    sweep["unresolved_reservations"]
                )
                unresolved_positions += int(
                    sweep["unresolved_positions"]
                )
            flat = unresolved_orders == 0 and unresolved_positions == 0
            reconciled = flat and core_ready
            # Reconciliation-only is sticky for the first successful pass.
            cycle = self.execution_cycle
            may_execute = (
                prior.reconciled_once
                and reconciled
                and cycle is not None
            )
            cycle_result: Mapping[str, Any] = {
                "schema": "dummy.dumbmoney-execution-cycle.v1",
                "status": "RECONCILIATION_COMPLETE"
                if reconciled
                else "RECONCILIATION_BLOCKED",
                "broker_contacted": True,
                "orders_submitted": 0,
                "broker_snapshot_sha256": truth[
                    "broker_snapshot_sha256"
                ],
            }
            if may_execute:
                assert self._capital_adapter is not None
                assert cycle is not None
                cycle_result = cycle(
                    capital_adapter=self._capital_adapter,
                    command_feed=self._command_feed,
                    broker_snapshot=truth,
                )
                if set(cycle_result) != {
                    "schema",
                    "status",
                    "broker_contacted",
                    "orders_submitted",
                    "broker_snapshot_sha256",
                }:
                    raise DumbMoneyWindowsServiceError(
                        "execution cycle result fields mismatch"
                    )
                if (
                    cycle_result["schema"]
                    != "dummy.dumbmoney-execution-cycle.v1"
                    or cycle_result["status"]
                    not in {"COMPLETE", "BLOCKED"}
                    or not isinstance(
                        cycle_result["broker_contacted"],
                        bool,
                    )
                    or isinstance(cycle_result["orders_submitted"], bool)
                    or not isinstance(
                        cycle_result["orders_submitted"],
                        int,
                    )
                    or cycle_result["orders_submitted"] < 0
                    or cycle_result["broker_snapshot_sha256"]
                    != truth["broker_snapshot_sha256"]
                ):
                    raise DumbMoneyWindowsServiceError(
                        "execution cycle result is invalid"
                    )
            self._anchor_local_state()
            execution_enabled = bool(
                may_execute
                and cycle_result.get("status") == "COMPLETE"
                and unresolved_orders == 0
                and unresolved_positions == 0
            )
            cycle_blocked = (
                may_execute
                and cycle_result.get("status") != "COMPLETE"
            )
            reason = (
                "UNRESOLVED_BROKER_ORDERS_OR_POSITIONS"
                if not flat
                else (
                    "CORE_CONTROLS_NOT_CURRENT"
                    if not core_ready
                    else (
                        "EXECUTION_CYCLE_BLOCKED"
                        if cycle_blocked
                        else (
                            "EXECUTION_CYCLE_NOT_SEALED"
                            if cycle is None
                            else (
                                "INITIAL_RECONCILIATION_COMPLETE"
                                if not prior.reconciled_once
                                else "ALL_CURRENT_CONTROLS_ALLOW"
                            )
                        )
                    )
                )
            )
            self._set_state(
                mode=(
                    "AGGRESSIVE_BOUNDED"
                    if execution_enabled
                    else START_MODE
                ),
                health_status=(
                    "READY"
                    if execution_enabled
                    else "BLOCKED"
                ),
                reason=reason,
                core_ready=core_ready,
                broker_truth_fresh=True,
                rollback_anchor_current=True,
                reconciled_once=reconciled,
                execution_enabled=execution_enabled,
                unresolved_open_orders=unresolved_orders,
                unresolved_positions=unresolved_positions,
                last_cycle_status=str(
                    cycle_result.get("status", "unknown")
                ),
            )
            self.write_readiness()
            return cycle_result
        except Exception as exc:
            self._set_state(
                mode=START_MODE,
                health_status="BLOCKED",
                reason=f"cycle_failed_closed:{type(exc).__name__}",
                core_ready=False,
                broker_truth_fresh=False,
                rollback_anchor_current=False,
                reconciled_once=False,
                execution_enabled=False,
                last_cycle_status="cycle_failed_closed",
            )
            self.write_readiness()
            raise

    def write_readiness(self) -> dict[str, Any]:
        now = self._clock()
        valid_until = now + timedelta(
            seconds=self.config.readiness_ttl_seconds
        )
        state = self.state()
        self._readiness_sequence += 1
        body = {
            "schema": READINESS_SCHEMA,
            "service_name": SERVICE_NAME,
            "release_id": self.config.release_id,
            "instance_id": self.instance_id,
            "process_id": os.getpid(),
            "generation": self._readiness_sequence,
            "observed_at": _format_utc(now),
            "valid_until": _format_utc(valid_until),
            "endpoint": {
                "transport": "http",
                "host": "127.0.0.1",
                "port": self._health.port,
                "base_path": "/",
            },
            "fund_lock_sha256": self.config.fund_lock_sha256,
            "service_manifest_sha256": (
                self.config.service_manifest_sha256
            ),
            "authority": {
                "broker": "KALSHI",
                "mode": state.mode,
                "execution_enabled": state.execution_enabled,
            },
            "health": {
                "status": state.health_status,
                "reason_codes": [state.reason],
                "core_ready": state.core_ready,
                "broker_truth_fresh": state.broker_truth_fresh,
                "rollback_anchor_current": (
                    state.rollback_anchor_current
                ),
                "reconciled_once": state.reconciled_once,
                "unresolved_open_orders": state.unresolved_open_orders,
                "unresolved_positions": state.unresolved_positions,
                "last_cycle_status": state.last_cycle_status,
                "runner_config_sha256": self.config.config_sha256,
                "readiness_public_key_sha256": (
                    self.config.readiness_signer_public_key_sha256
                ),
            },
            "capabilities": [
                "authenticated-promotion-resolution",
                "broker-reconciliation",
                "cell-command-checkpoints",
                "canonical-live-firewall-only",
                "core-journal-head-anchors",
            ],
        }
        unsigned = {
            "schema": SIGNED_ENVELOPE_SCHEMA,
            "source_id": SERVICE_NAME,
            "source_sequence": self._readiness_sequence,
            "correlation_id": f"readiness-{self.instance_id}",
            "causation_id": None,
            "nonce": hashlib.sha256(
                canonical_json(
                    {
                        "instance_id": self.instance_id,
                        "sequence": self._readiness_sequence,
                        "observed_at": body["observed_at"],
                    }
                ).encode("utf-8")
            ).hexdigest(),
            "not_before": body["observed_at"],
            "expires_at": body["valid_until"],
            "body_schema": READINESS_SCHEMA,
            "body_digest": sha256_json(body),
            "body": body,
            "signature_algorithm": "Ed25519",
            "signer_key_id": (
                self.config.readiness_signer_public_key_sha256
            ),
        }
        unsigned["event_id"] = sha256_json(unsigned)
        signature = self.secrets.readiness_private_key.sign(
            canonical_json(unsigned).encode("utf-8")
        )
        envelope = {
            **unsigned,
            "signature": base64.urlsafe_b64encode(signature)
            .decode("ascii")
            .rstrip("="),
        }
        _atomic_write_json(self.config.readiness_path, envelope)
        return envelope

    def run_forever(self, stop_event: threading.Event) -> None:
        self.start()
        try:
            while not stop_event.is_set():
                if stop_event.wait(self.config.poll_interval_seconds):
                    break
                try:
                    self.run_once()
                except Exception:
                    # run_once already persisted a short-lived signed blocked
                    # readiness descriptor. Continue polling for recovery.
                    continue
        finally:
            self.close()


class _DataRootLease:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle: Any = None

    def __enter__(self) -> "_DataRootLease":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        try:
            self.handle.seek(0)
            import msvcrt

            msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
        except (ImportError, OSError) as exc:
            self.handle.close()
            raise DumbMoneyWindowsServiceError(
                "another Dummy service owns the ProgramData root"
            ) from exc
        return self

    def __exit__(self, *_args: Any) -> None:
        if self.handle is None or self.handle.closed:
            return
        try:
            self.handle.seek(0)
            import msvcrt

            msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self.handle.close()


def _program_data_path() -> Path:
    value = os.environ.get("PROGRAMDATA", "")
    if not value:
        raise DumbMoneyWindowsServiceError(
            "PROGRAMDATA is required for the sealed Windows service"
        )
    path = Path(value).resolve()
    if not path.is_absolute():
        raise DumbMoneyWindowsServiceError("PROGRAMDATA must be absolute")
    return path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=SERVICE_NAME,
        description="Sealed DumbMoney Dummy/Kalshi venue-cell service",
        allow_abbrev=False,
    )
    parser.add_argument("--core-endpoint-ref", required=True)
    parser.add_argument("--core-cell-token-target", required=True)
    parser.add_argument("--kalshi-key-id-target", required=True)
    parser.add_argument("--kalshi-private-key-target", required=True)
    parser.add_argument("--readiness-signing-key-target", required=True)
    parser.add_argument("--start-mode", required=True)
    parser.add_argument("--readiness-ref", required=True)
    parser.add_argument("--config-sha256", required=True)
    return parser


def _validate_cli(arguments: argparse.Namespace) -> None:
    expected = {
        "core_endpoint_ref": CORE_ENDPOINT_REF,
        "core_cell_token_target": CELL_TOKEN_TARGET_REF,
        "kalshi_key_id_target": KALSHI_KEY_ID_TARGET_REF,
        "kalshi_private_key_target": KALSHI_PRIVATE_KEY_TARGET_REF,
        "readiness_signing_key_target": READINESS_KEY_TARGET_REF,
        "start_mode": START_MODE,
        "readiness_ref": READINESS_REF,
    }
    for field, value in expected.items():
        if getattr(arguments, field) != value:
            raise DumbMoneyWindowsServiceError(
                f"sealed service argument mismatch: {field}"
            )
    _digest(arguments.config_sha256, field="--config-sha256")


def main(argv: list[str] | None = None) -> int:
    """Synchronous sealed-packaging entry point."""
    try:
        arguments = _parser().parse_args(argv)
        _validate_cli(arguments)
        program_data = _program_data_path()
        config = load_runner_config(
            program_data / CONFIG_RELATIVE_PATH,
            arguments.config_sha256,
            program_data,
        )
        secrets_value = load_secrets(WindowsCredentialManager(), config)
        service = DumbMoneyDummyKalshiService(
            config,
            secrets_value,
            core_transport=LoopbackCoreTransport(),
            broker_truth=KalshiBrokerTruthProvider(
                api_key_id=secrets_value.kalshi_key_id,
                private_key_pem=secrets_value.kalshi_private_key_pem,
                expected_account_hash=config.expected_account_hash,
                subaccount_number=config.kalshi_subaccount_number,
            ),
            execution_cycle=SealedDisabledExecutionCycle(),
        )
        stop_event = threading.Event()

        def stop(_signum: int, _frame: Any) -> None:
            stop_event.set()

        for signal_name in ("SIGINT", "SIGTERM"):
            candidate = getattr(signal, signal_name, None)
            if candidate is not None:
                signal.signal(candidate, stop)
        with _DataRootLease(config.data_root / "service.lock"):
            service.run_forever(stop_event)
        return 0
    except KeyboardInterrupt:
        return 0
    except (
        DumbMoneyWindowsServiceError,
        KalshiBrokerTruthError,
        OSError,
        ValueError,
    ) as exc:
        print(
            f"{SERVICE_NAME} failed closed: {type(exc).__name__}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CELL_TOKEN_TARGET_REF",
    "CONFIG_RELATIVE_PATH",
    "CONFIG_SCHEMA",
    "CORE_ENDPOINT_REF",
    "DATA_ROOT_RELATIVE_PATH",
    "DumbMoneyDummyKalshiService",
    "DumbMoneyWindowsServiceError",
    "DummyKalshiRunnerConfig",
    "KALSHI_KEY_ID_TARGET_REF",
    "KALSHI_PRIVATE_KEY_TARGET_REF",
    "KalshiBrokerTruthProvider",
    "LoopbackCoreTransport",
    "READINESS_KEY_TARGET_REF",
    "READINESS_REF",
    "RunnerSecrets",
    "SealedDisabledExecutionCycle",
    "SERVICE_NAME",
    "START_MODE",
    "WindowsCredentialManager",
    "kalshi_account_hash",
    "load_runner_config",
    "load_secrets",
    "main",
]
