from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

from core.caps_authority import (
    CURRENT_CAPS_AUTHORITY_EPOCH,
    CURRENT_CAPS_SCHEMA_VERSION,
    CapsAuthorityStatus,
)


def install_registered_caps_authority(
    monkeypatch,
    caps_path: Path,
    *,
    patch_operator_appliance: bool = False,
) -> Callable[..., CapsAuthorityStatus]:
    """Install a dynamic, secret-free caps-v2 authority test double.

    The baseline is bound to the fixture file's initial bytes.  Mutating those
    bytes makes later evaluations fail configuration integrity, preserving the
    production fail-closed behavior in hash-change tests.
    """

    baseline_hash = hashlib.sha256(caps_path.read_bytes()).hexdigest().upper()
    registration_hash = "A" * 64

    def evaluate(*args, **kwargs) -> CapsAuthorityStatus:
        del args, kwargs
        try:
            current_hash = hashlib.sha256(caps_path.read_bytes()).hexdigest().upper()
        except OSError:
            current_hash = None
        config_valid = current_hash == baseline_hash
        registration_valid = config_valid
        return CapsAuthorityStatus(
            state=(
                "REGISTERED_FOR_SEPARATE_LIVE_GATE_EVALUATION"
                if registration_valid
                else "CONFIG_INTEGRITY_BLOCKED"
            ),
            current_caps_sha256=current_hash,
            protected_caps_sha256=baseline_hash,
            schema_version=CURRENT_CAPS_SCHEMA_VERSION,
            authority_epoch=CURRENT_CAPS_AUTHORITY_EPOCH,
            config_integrity_valid=config_valid,
            authority_registration_required=True,
            authority_registration_present=True,
            authority_registration_valid=registration_valid,
            authority_registration_sha256=registration_hash,
            legacy_authority_invalidated=True,
            errors=() if config_valid else ("CAPS_PROTECTED_HASH_MISMATCH",),
            execution_authority=False,
        )

    monkeypatch.setattr("core.proof_authority.evaluate_caps_authority", evaluate)
    if patch_operator_appliance:
        monkeypatch.setattr(
            "tools.operator_authority_appliance.operator_full_completion._caps_authority_status",
            evaluate,
        )
    return evaluate


def registered_caps_status() -> CapsAuthorityStatus:
    return CapsAuthorityStatus(
        state="REGISTERED_FOR_SEPARATE_LIVE_GATE_EVALUATION",
        current_caps_sha256="B" * 64,
        protected_caps_sha256="B" * 64,
        schema_version=CURRENT_CAPS_SCHEMA_VERSION,
        authority_epoch=CURRENT_CAPS_AUTHORITY_EPOCH,
        config_integrity_valid=True,
        authority_registration_required=True,
        authority_registration_present=True,
        authority_registration_valid=True,
        authority_registration_sha256="A" * 64,
        legacy_authority_invalidated=True,
        errors=(),
        execution_authority=False,
    )


def registered_caps_status_dict() -> dict[str, object]:
    return registered_caps_status().to_dict()
