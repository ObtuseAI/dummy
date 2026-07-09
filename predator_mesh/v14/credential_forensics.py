"""V14 redacted Kalshi credential forensics.

The checks in this module inspect credential shape only inside process memory.
Reports intentionally serialize source, presence, and failure category, never
raw key ids or private key material.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from predator_mesh.v13.credential_bridge import KalshiReadOnlyCredentialBridge


class KalshiCredentialFailureReason(str, Enum):
    NONE = "NONE"
    CREDENTIALS_MISSING = "CREDENTIALS_MISSING"
    MALFORMED_ENVIRONMENT_VARIABLE = "MALFORMED_ENVIRONMENT_VARIABLE"
    UNSUPPORTED_PRIVATE_KEY_ENCODING = "UNSUPPORTED_PRIVATE_KEY_ENCODING"
    AUTH_SIGNATURE_FAILURE_LIKELY = "AUTH_SIGNATURE_FAILURE_LIKELY"
    KEY_ID_PRIVATE_KEY_MISMATCH_LIKELY = "KEY_ID_PRIVATE_KEY_MISMATCH_LIKELY"
    BASE_URL_MISMATCH_LIKELY = "BASE_URL_MISMATCH_LIKELY"
    PERMISSION_OR_ACCOUNT_ISSUE_LIKELY = "PERMISSION_OR_ACCOUNT_ISSUE_LIKELY"
    CLOCK_DRIFT_LIKELY = "CLOCK_DRIFT_LIKELY"
    ENDPOINT_BASE_URL_MISMATCH_LIKELY = "ENDPOINT_BASE_URL_MISMATCH_LIKELY"
    FILE_PATH_MISSING = "FILE_PATH_MISSING"
    FILE_NOT_READABLE = "FILE_NOT_READABLE"


_REPORT_SAFE_FAILURES = {
    KalshiCredentialFailureReason.NONE,
    KalshiCredentialFailureReason.CREDENTIALS_MISSING,
    KalshiCredentialFailureReason.MALFORMED_ENVIRONMENT_VARIABLE,
    KalshiCredentialFailureReason.UNSUPPORTED_PRIVATE_KEY_ENCODING,
    KalshiCredentialFailureReason.AUTH_SIGNATURE_FAILURE_LIKELY,
    KalshiCredentialFailureReason.KEY_ID_PRIVATE_KEY_MISMATCH_LIKELY,
    KalshiCredentialFailureReason.BASE_URL_MISMATCH_LIKELY,
    KalshiCredentialFailureReason.PERMISSION_OR_ACCOUNT_ISSUE_LIKELY,
    KalshiCredentialFailureReason.CLOCK_DRIFT_LIKELY,
    KalshiCredentialFailureReason.ENDPOINT_BASE_URL_MISMATCH_LIKELY,
}


def _report_safe_reason(reason: str | KalshiCredentialFailureReason) -> str:
    try:
        parsed = KalshiCredentialFailureReason(reason)
    except ValueError:
        return KalshiCredentialFailureReason.UNSUPPORTED_PRIVATE_KEY_ENCODING.value
    if parsed in _REPORT_SAFE_FAILURES:
        return parsed.value
    if parsed in {KalshiCredentialFailureReason.FILE_PATH_MISSING, KalshiCredentialFailureReason.FILE_NOT_READABLE}:
        return KalshiCredentialFailureReason.CREDENTIALS_MISSING.value
    return KalshiCredentialFailureReason.UNSUPPORTED_PRIVATE_KEY_ENCODING.value


@dataclass(frozen=True)
class KalshiPrivateKeyFormatCheck:
    present: bool
    likely_valid: bool
    reference_kind: str
    failure_reason: str
    redacted: bool = True

    @classmethod
    def from_secret_values(cls, values: Mapping[str, str]) -> "KalshiPrivateKeyFormatCheck":
        inline = values.get("KALSHI_API_PRIVATE_KEY_PEM") or ""
        path_value = values.get("KALSHI_API_PRIVATE_KEY_PEM_PATH") or values.get("KALSHI_API_PRIVATE_KEY_PATH") or ""
        if inline:
            if "\\n" in inline:
                return cls(True, False, "inline_pem", KalshiCredentialFailureReason.MALFORMED_ENVIRONMENT_VARIABLE.value)
            if "BEGIN" in inline and "PRIVATE KEY" in inline and "END" in inline:
                return cls(True, True, "inline_pem", KalshiCredentialFailureReason.NONE.value)
            return cls(True, False, "inline_pem", KalshiCredentialFailureReason.UNSUPPORTED_PRIVATE_KEY_ENCODING.value)
        if path_value:
            path = Path(path_value)
            if not path.exists():
                return cls(True, False, "pem_path", KalshiCredentialFailureReason.FILE_PATH_MISSING.value)
            if not path.is_file():
                return cls(True, False, "pem_path", KalshiCredentialFailureReason.FILE_NOT_READABLE.value)
            return cls(True, True, "pem_path", KalshiCredentialFailureReason.NONE.value)
        return cls(False, False, "missing", KalshiCredentialFailureReason.CREDENTIALS_MISSING.value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "present": self.present,
            "likely_valid": self.likely_valid,
            "reference_kind": self.reference_kind,
            "failure_reason": _report_safe_reason(self.failure_reason),
            "redacted": True,
        }


@dataclass(frozen=True)
class KalshiKeyIdFormatCheck:
    present: bool
    likely_valid: bool
    failure_reason: str
    redacted: bool = True

    @classmethod
    def from_secret_values(cls, values: Mapping[str, str]) -> "KalshiKeyIdFormatCheck":
        value = values.get("KALSHI_API_KEY_ID") or ""
        if not value:
            return cls(False, False, KalshiCredentialFailureReason.CREDENTIALS_MISSING.value)
        lowered = value.lower()
        likely_placeholder = any(token in lowered for token in ("example", "placeholder", "<", ">"))
        return cls(True, not likely_placeholder, KalshiCredentialFailureReason.NONE.value if not likely_placeholder else KalshiCredentialFailureReason.AUTH_SIGNATURE_FAILURE_LIKELY.value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "present": self.present,
            "likely_valid": self.likely_valid,
            "failure_reason": _report_safe_reason(self.failure_reason),
            "redacted": True,
        }


@dataclass(frozen=True)
class KalshiAuthProbeClassification:
    failure_reason: str
    safe_to_retry_real_readonly: bool
    retry_requires_operator_repair: bool
    verdict: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_reason": _report_safe_reason(self.failure_reason),
            "safe_to_retry_real_readonly": self.safe_to_retry_real_readonly,
            "retry_requires_operator_repair": self.retry_requires_operator_repair,
            "verdict": self.verdict,
        }


class KalshiAuthProbeClassifier:
    def classify_exception(self, exc: BaseException) -> KalshiAuthProbeClassification:
        message = str(exc).lower()
        if "pem" in message or "invalidbyte" in message or "private key" in message:
            reason = KalshiCredentialFailureReason.MALFORMED_ENVIRONMENT_VARIABLE.value
        elif "401" in message or "signature" in message or "unauthorized" in message:
            reason = KalshiCredentialFailureReason.AUTH_SIGNATURE_FAILURE_LIKELY.value
        elif "403" in message or "permission" in message or "forbidden" in message:
            reason = KalshiCredentialFailureReason.PERMISSION_OR_ACCOUNT_ISSUE_LIKELY.value
        elif "clock" in message or "timestamp" in message:
            reason = KalshiCredentialFailureReason.CLOCK_DRIFT_LIKELY.value
        elif "base url" in message or "endpoint" in message:
            reason = KalshiCredentialFailureReason.ENDPOINT_BASE_URL_MISMATCH_LIKELY.value
        else:
            reason = KalshiCredentialFailureReason.AUTH_SIGNATURE_FAILURE_LIKELY.value
        return KalshiAuthProbeClassification(
            failure_reason=reason,
            safe_to_retry_real_readonly=False,
            retry_requires_operator_repair=True,
            verdict="PARTIAL",
        )


@dataclass(frozen=True)
class KalshiCredentialRepairHint:
    failure_reason: str
    repair_steps: list[str]
    placeholder_examples: list[str]
    placeholder_examples_only: bool = True

    @classmethod
    def for_reason(cls, reason: str) -> "KalshiCredentialRepairHint":
        safe_reason = _report_safe_reason(reason)
        if safe_reason == KalshiCredentialFailureReason.MALFORMED_ENVIRONMENT_VARIABLE.value:
            steps = [
                "Replace literal backslash-n inline PEM values with a file-path based private key reference.",
                "Keep the private key in a local secret file outside reports, prompts, and dashboard payloads.",
                "Rerun the bounded V14 READ_ONLY report generator after the operator updates the local secret source.",
            ]
        elif safe_reason == KalshiCredentialFailureReason.CREDENTIALS_MISSING.value:
            steps = [
                "Add a local Kalshi key id and private-key path reference in an approved local secret source.",
                "Do not paste the private key value into chat, reports, logs, or dashboards.",
            ]
        else:
            steps = [
                "Verify the key id and private key belong together in the Kalshi operator portal.",
                "Run the V14 READ_ONLY retest after correcting the local secret source.",
            ]
        return cls(
            failure_reason=safe_reason,
            repair_steps=steps,
            placeholder_examples=[
                "KALSHI_API_KEY_ID=<kalshi-key-id>",
                "KALSHI_API_PRIVATE_KEY_PEM_PATH=<path-to-private-key-pem>",
            ],
        )

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V14: Kalshi Credential Repair Hints",
            "failure_reason": self.failure_reason,
            "repair_steps": self.repair_steps,
            "placeholder_examples": self.placeholder_examples,
            "placeholder_examples_only": self.placeholder_examples_only,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }


class KalshiCredentialForensics:
    def __init__(self, *, credential_bridge: KalshiReadOnlyCredentialBridge | None = None) -> None:
        self.credential_bridge = credential_bridge or KalshiReadOnlyCredentialBridge()

    def _secret_values(self) -> dict[str, str]:
        try:
            return self.credential_bridge.secret_environment()
        except Exception:
            return {}

    def _failure_reason(self, key_check: KalshiKeyIdFormatCheck, private_check: KalshiPrivateKeyFormatCheck) -> str:
        if not key_check.present or not private_check.present:
            return KalshiCredentialFailureReason.CREDENTIALS_MISSING.value
        if not key_check.likely_valid:
            return KalshiCredentialFailureReason.AUTH_SIGNATURE_FAILURE_LIKELY.value
        if not private_check.likely_valid:
            return _report_safe_reason(private_check.failure_reason)
        return KalshiCredentialFailureReason.NONE.value

    def to_report(self) -> dict[str, Any]:
        readiness = self.credential_bridge.resolve()
        values = self._secret_values()
        key_check = KalshiKeyIdFormatCheck.from_secret_values(values)
        private_check = KalshiPrivateKeyFormatCheck.from_secret_values(values)
        reason = self._failure_reason(key_check, private_check)
        credentials_valid = readiness.ready and reason == KalshiCredentialFailureReason.NONE.value
        return {
            "workstream": "V14: Kalshi Credential Forensics",
            "credential_source": readiness.source.value,
            "selected_source": readiness.source.value,
            "key_id_shape": key_check.to_dict(),
            "private_key_shape": private_check.to_dict(),
            "failure_reason": reason,
            "credentials_valid_for_retry": credentials_valid,
            "safe_to_retry_real_readonly": credentials_valid,
            "secret_values_exposed": False,
            "redacted": True,
            "verdict": "PASS" if credentials_valid else "PARTIAL",
        }

    def private_key_shape_report(self) -> dict[str, Any]:
        report = KalshiPrivateKeyFormatCheck.from_secret_values(self._secret_values()).to_dict()
        report.update({"workstream": "V14: Kalshi Private Key Shape", "verdict": "PASS" if report["likely_valid"] else "PARTIAL"})
        return report

    def auth_probe_classifier_report(self) -> dict[str, Any]:
        report = self.to_report()
        if report["failure_reason"] == KalshiCredentialFailureReason.NONE.value:
            classified = KalshiAuthProbeClassification("NONE", True, False, "PASS").to_dict()
        else:
            classified = KalshiAuthProbeClassification(report["failure_reason"], False, True, "PARTIAL").to_dict()
        classified.update({"workstream": "V14: Kalshi Auth Probe Classifier"})
        return classified

    def repair_hints_report(self) -> dict[str, Any]:
        return KalshiCredentialRepairHint.for_reason(self.to_report()["failure_reason"]).to_report()
