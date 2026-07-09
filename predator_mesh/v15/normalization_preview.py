"""V15 Kalshi credential normalization preview.

Preview only: never auto-edits .env, never leaks real secret text. All
examples use placeholders like KALSHI_API_KEY_ID=<your-key-id-here>.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from predator_mesh.v15.credential_shape_repair import (
    KalshiCredentialShapeRepairEngine,
    KalshiMalformedEnvPattern,
)


@dataclass(frozen=True)
class KalshiCredentialTemplate:
    name: str
    lines: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "lines": self.lines, "placeholder_examples_only": True}


@dataclass(frozen=True)
class KalshiCredentialRepairExample:
    pattern: str
    before_placeholder: str
    after_placeholder: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern": self.pattern,
            "before_placeholder": self.before_placeholder,
            "after_placeholder": self.after_placeholder,
            "placeholder_examples_only": True,
        }


_TEMPLATE = KalshiCredentialTemplate(
    name="kalshi_read_only_env_template",
    lines=[
        "KALSHI_API_KEY_ID=<your-key-id-here>",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH=<path-to-private-key-pem>",
    ],
)

_EXAMPLES: dict[KalshiMalformedEnvPattern, KalshiCredentialRepairExample] = {
    KalshiMalformedEnvPattern.LITERAL_BACKSLASH_N_IN_PEM: KalshiCredentialRepairExample(
        KalshiMalformedEnvPattern.LITERAL_BACKSLASH_N_IN_PEM.value,
        "KALSHI_API_PRIVATE_KEY_PEM=<pem-with-literal-backslash-n>",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH=<path-to-private-key-pem>",
    ),
    KalshiMalformedEnvPattern.PLACEHOLDER_KEY_ID: KalshiCredentialRepairExample(
        KalshiMalformedEnvPattern.PLACEHOLDER_KEY_ID.value,
        "KALSHI_API_KEY_ID=<example-placeholder>",
        "KALSHI_API_KEY_ID=<your-key-id-here>",
    ),
    KalshiMalformedEnvPattern.WHITESPACE_OR_QUOTES_WRAPPING: KalshiCredentialRepairExample(
        KalshiMalformedEnvPattern.WHITESPACE_OR_QUOTES_WRAPPING.value,
        'KALSHI_API_KEY_ID="<your-key-id-here> "',
        "KALSHI_API_KEY_ID=<your-key-id-here>",
    ),
    KalshiMalformedEnvPattern.PEM_PATH_MISSING: KalshiCredentialRepairExample(
        KalshiMalformedEnvPattern.PEM_PATH_MISSING.value,
        "KALSHI_API_PRIVATE_KEY_PEM_PATH=<missing-path>",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH=<path-to-private-key-pem>",
    ),
    KalshiMalformedEnvPattern.CREDENTIALS_ABSENT: KalshiCredentialRepairExample(
        KalshiMalformedEnvPattern.CREDENTIALS_ABSENT.value,
        "# no KALSHI_* variables set",
        "KALSHI_API_KEY_ID=<your-key-id-here>",
    ),
}


class KalshiCredentialNormalizationPreview:
    """Renders a preview-only, non-mutating repair plan. Never writes .env."""

    def __init__(self, *, repair_engine: KalshiCredentialShapeRepairEngine | None = None) -> None:
        self.repair_engine = repair_engine or KalshiCredentialShapeRepairEngine()

    def template(self) -> KalshiCredentialTemplate:
        return _TEMPLATE

    def examples(self) -> list[KalshiCredentialRepairExample]:
        patterns = self.repair_engine.detect_patterns()
        examples = [_EXAMPLES[p] for p in patterns if p in _EXAMPLES]
        if not examples:
            examples = [
                KalshiCredentialRepairExample(
                    KalshiMalformedEnvPattern.NONE.value,
                    "KALSHI_API_KEY_ID=<your-key-id-here>",
                    "KALSHI_API_KEY_ID=<your-key-id-here>",
                )
            ]
        return examples

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V15: Kalshi Credential Normalization Preview",
            "template": self.template().to_dict(),
            "examples": [e.to_dict() for e in self.examples()],
            "auto_edits_env": False,
            "writes_env_file": False,
            "secret_values_exposed": False,
            "placeholder_examples_only": True,
            "verdict": "PASS",
        }
