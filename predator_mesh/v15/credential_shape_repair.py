"""V15 Kalshi credential shape repair engine.

Diagnoses malformed environment-variable credential shapes and produces
report-safe, redacted repair guidance. Never prints or stores real secret
values or private key text; placeholders only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from predator_mesh.v14.credential_forensics import (
    KalshiCredentialFailureReason,
    KalshiCredentialForensics,
    KalshiKeyIdFormatCheck,
    KalshiPrivateKeyFormatCheck,
)


class KalshiMalformedEnvPattern(str, Enum):
    NONE = "NONE"
    LITERAL_BACKSLASH_N_IN_PEM = "LITERAL_BACKSLASH_N_IN_PEM"
    MISSING_PEM_HEADER_FOOTER = "MISSING_PEM_HEADER_FOOTER"
    PLACEHOLDER_KEY_ID = "PLACEHOLDER_KEY_ID"
    PEM_PATH_MISSING = "PEM_PATH_MISSING"
    PEM_PATH_NOT_READABLE = "PEM_PATH_NOT_READABLE"
    WHITESPACE_OR_QUOTES_WRAPPING = "WHITESPACE_OR_QUOTES_WRAPPING"
    CREDENTIALS_ABSENT = "CREDENTIALS_ABSENT"


class KalshiEnvRepairVerdict(str, Enum):
    SHAPE_VALID = "SHAPE_VALID"
    SHAPE_REPAIRABLE_LOCALLY = "SHAPE_REPAIRABLE_LOCALLY"
    SHAPE_REQUIRES_OPERATOR_ACTION = "SHAPE_REQUIRES_OPERATOR_ACTION"
    SHAPE_ABSENT = "SHAPE_ABSENT"


@dataclass(frozen=True)
class KalshiCredentialNormalizationHint:
    pattern: str
    hint: str
    placeholder_example: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern": self.pattern,
            "hint": self.hint,
            "placeholder_example": self.placeholder_example,
            "placeholder_examples_only": True,
        }


_HINTS: dict[KalshiMalformedEnvPattern, KalshiCredentialNormalizationHint] = {
    KalshiMalformedEnvPattern.LITERAL_BACKSLASH_N_IN_PEM: KalshiCredentialNormalizationHint(
        KalshiMalformedEnvPattern.LITERAL_BACKSLASH_N_IN_PEM.value,
        "Inline PEM contains literal backslash-n sequences instead of real newlines. "
        "Move the key to a file referenced by KALSHI_API_PRIVATE_KEY_PEM_PATH instead of inlining it.",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH=<path-to-private-key-pem>",
    ),
    KalshiMalformedEnvPattern.MISSING_PEM_HEADER_FOOTER: KalshiCredentialNormalizationHint(
        KalshiMalformedEnvPattern.MISSING_PEM_HEADER_FOOTER.value,
        "Value present but missing BEGIN/END PRIVATE KEY markers. Re-export the key from the Kalshi portal as PEM.",
        "-----BEGIN PRIVATE KEY-----\\n<redacted>\\n-----END PRIVATE KEY-----",
    ),
    KalshiMalformedEnvPattern.PLACEHOLDER_KEY_ID: KalshiCredentialNormalizationHint(
        KalshiMalformedEnvPattern.PLACEHOLDER_KEY_ID.value,
        "Key id looks like an unfilled placeholder token. Replace with the operator's real key id locally.",
        "KALSHI_API_KEY_ID=<your-key-id-here>",
    ),
    KalshiMalformedEnvPattern.PEM_PATH_MISSING: KalshiCredentialNormalizationHint(
        KalshiMalformedEnvPattern.PEM_PATH_MISSING.value,
        "Referenced PEM path does not exist on disk. Point KALSHI_API_PRIVATE_KEY_PEM_PATH at an existing local file.",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH=<path-to-private-key-pem>",
    ),
    KalshiMalformedEnvPattern.PEM_PATH_NOT_READABLE: KalshiCredentialNormalizationHint(
        KalshiMalformedEnvPattern.PEM_PATH_NOT_READABLE.value,
        "Referenced PEM path exists but is not a readable file. Verify path and file permissions.",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH=<path-to-private-key-pem>",
    ),
    KalshiMalformedEnvPattern.WHITESPACE_OR_QUOTES_WRAPPING: KalshiCredentialNormalizationHint(
        KalshiMalformedEnvPattern.WHITESPACE_OR_QUOTES_WRAPPING.value,
        "Value appears wrapped in stray quotes or whitespace. Strip surrounding quotes/whitespace in the local secret source.",
        "KALSHI_API_KEY_ID=<your-key-id-here>",
    ),
    KalshiMalformedEnvPattern.CREDENTIALS_ABSENT: KalshiCredentialNormalizationHint(
        KalshiMalformedEnvPattern.CREDENTIALS_ABSENT.value,
        "No credential material present. Add key id and private key path references in an approved local secret source.",
        "KALSHI_API_KEY_ID=<your-key-id-here>",
    ),
    KalshiMalformedEnvPattern.NONE: KalshiCredentialNormalizationHint(
        KalshiMalformedEnvPattern.NONE.value,
        "Credential shape looks valid; no repair required.",
        "",
    ),
}


@dataclass(frozen=True)
class KalshiEnvShapeProof:
    patterns_detected: list[str]
    verdict: str
    key_id_present: bool
    private_key_present: bool
    redacted: bool = True

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V15: Kalshi Env Shape Proof",
            "patterns_detected": self.patterns_detected,
            "verdict_state": self.verdict,
            "key_id_present": self.key_id_present,
            "private_key_present": self.private_key_present,
            "secret_values_exposed": False,
            "redacted": True,
            "verdict": "PASS" if self.verdict == KalshiEnvRepairVerdict.SHAPE_VALID.value else "PARTIAL",
        }


class KalshiCredentialShapeRepairEngine:
    """Diagnoses malformed credential shape and proposes safe, redacted repairs."""

    def __init__(self, *, forensics: KalshiCredentialForensics | None = None) -> None:
        self.forensics = forensics or KalshiCredentialForensics()

    def _secret_values(self) -> Mapping[str, str]:
        return self.forensics._secret_values()  # noqa: SLF001 - intentional reuse of redacted accessor

    def detect_patterns(self) -> list[KalshiMalformedEnvPattern]:
        values = self._secret_values()
        key_check = KalshiKeyIdFormatCheck.from_secret_values(values)
        private_check = KalshiPrivateKeyFormatCheck.from_secret_values(values)
        patterns: list[KalshiMalformedEnvPattern] = []

        if not key_check.present and not private_check.present:
            patterns.append(KalshiMalformedEnvPattern.CREDENTIALS_ABSENT)
            return patterns

        inline = values.get("KALSHI_API_PRIVATE_KEY_PEM") or ""
        if inline and "\\n" in inline:
            patterns.append(KalshiMalformedEnvPattern.LITERAL_BACKSLASH_N_IN_PEM)
        elif inline and not ("BEGIN" in inline and "PRIVATE KEY" in inline and "END" in inline):
            patterns.append(KalshiMalformedEnvPattern.MISSING_PEM_HEADER_FOOTER)
        if private_check.reference_kind == "pem_path":
            if private_check.failure_reason == KalshiCredentialFailureReason.FILE_PATH_MISSING.value:
                patterns.append(KalshiMalformedEnvPattern.PEM_PATH_MISSING)
            elif private_check.failure_reason == KalshiCredentialFailureReason.FILE_NOT_READABLE.value:
                patterns.append(KalshiMalformedEnvPattern.PEM_PATH_NOT_READABLE)
        if not private_check.present:
            patterns.append(KalshiMalformedEnvPattern.CREDENTIALS_ABSENT)

        key_id = values.get("KALSHI_API_KEY_ID") or ""
        if key_id:
            stripped = key_id.strip().strip('"').strip("'")
            if stripped != key_id:
                patterns.append(KalshiMalformedEnvPattern.WHITESPACE_OR_QUOTES_WRAPPING)
            if not key_check.likely_valid:
                patterns.append(KalshiMalformedEnvPattern.PLACEHOLDER_KEY_ID)
        elif not key_check.present:
            patterns.append(KalshiMalformedEnvPattern.CREDENTIALS_ABSENT)

        if not patterns:
            patterns.append(KalshiMalformedEnvPattern.NONE)
        # dedupe preserving order
        seen: set[str] = set()
        ordered: list[KalshiMalformedEnvPattern] = []
        for pattern in patterns:
            if pattern.value not in seen:
                seen.add(pattern.value)
                ordered.append(pattern)
        return ordered

    def verdict(self) -> KalshiEnvRepairVerdict:
        patterns = self.detect_patterns()
        if patterns == [KalshiMalformedEnvPattern.NONE]:
            return KalshiEnvRepairVerdict.SHAPE_VALID
        if KalshiMalformedEnvPattern.CREDENTIALS_ABSENT in patterns and len(patterns) == 1:
            return KalshiEnvRepairVerdict.SHAPE_ABSENT
        locally_repairable = {
            KalshiMalformedEnvPattern.WHITESPACE_OR_QUOTES_WRAPPING,
            KalshiMalformedEnvPattern.LITERAL_BACKSLASH_N_IN_PEM,
        }
        if all(p in locally_repairable for p in patterns):
            return KalshiEnvRepairVerdict.SHAPE_REPAIRABLE_LOCALLY
        return KalshiEnvRepairVerdict.SHAPE_REQUIRES_OPERATOR_ACTION

    def hints(self) -> list[KalshiCredentialNormalizationHint]:
        return [_HINTS[p] for p in self.detect_patterns()]

    def shape_proof(self) -> KalshiEnvShapeProof:
        values = self._secret_values()
        key_check = KalshiKeyIdFormatCheck.from_secret_values(values)
        private_check = KalshiPrivateKeyFormatCheck.from_secret_values(values)
        return KalshiEnvShapeProof(
            patterns_detected=[p.value for p in self.detect_patterns()],
            verdict=self.verdict().value,
            key_id_present=key_check.present,
            private_key_present=private_check.present,
        )

    def to_report(self) -> dict[str, Any]:
        verdict = self.verdict()
        return {
            "workstream": "V15: Kalshi Credential Shape Repair Engine",
            "patterns_detected": [p.value for p in self.detect_patterns()],
            "verdict_state": verdict.value,
            "hints": [h.to_dict() for h in self.hints()],
            "secret_values_exposed": False,
            "redacted": True,
            "verdict": "PASS" if verdict == KalshiEnvRepairVerdict.SHAPE_VALID else "PARTIAL",
        }
