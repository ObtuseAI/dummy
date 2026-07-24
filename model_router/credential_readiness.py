from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModelCredentialStatus:
    """Read-only credential status for a model provider.

    The actual API key is intentionally absent.  `redacted` is always True to
    signal that this structure is safe to log, serialize, and store.
    """

    present: bool
    base_url: str
    model: str
    source: str
    redacted: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "present": self.present,
            "base_url": self.base_url,
            "model": self.model,
            "source": self.source,
            "redacted": True,
        }


def _present(key_name: str) -> bool:
    """Presence/shape only: a key must exist and be non-blank.  The value is
    never returned, logged, or compared against anything."""
    return bool((os.environ.get(key_name) or "").strip())


class CredentialReadiness:
    """Detect whether the model-provider credentials are available.

    Reads environment variables and exposes redacted status objects.  No API
    key value is ever retained or returned.

    OpenRouter is included because it is the key the live LLM panel actually
    authenticates with (every entry in ``configs/model_routing.json`` routes
    ``route_mode: openrouter`` against ``OPENROUTER_API_KEY``).  Without it a
    missing panel credential surfaced only downstream, as a router fallback
    (``<provider>_credentials_missing``), never as a readiness failure.

    Environment variables:
      - DEEPSEEK_API_KEY (required for "present")
      - DEEPSEEK_BASE_URL (optional, default https://api.deepseek.com)
      - DEEPSEEK_MODEL (optional, default deepseekv4flash)
      - MINIMAX_API_KEY (required for "present")
      - MINIMAX_BASE_URL (optional, default https://api.minimax.chat)
      - MINIMAX_MODEL (optional, default minimaxm3)
      - OPENROUTER_API_KEY (required for "present")
      - OPENROUTER_BASE_URL (optional, default https://openrouter.ai/api)
      - OPENROUTER_MODEL (optional, default openrouter/auto)
    """

    def deepseek_status(self) -> ModelCredentialStatus:
        return ModelCredentialStatus(
            present=_present("DEEPSEEK_API_KEY"),
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.environ.get("DEEPSEEK_MODEL", "deepseekv4flash"),
            source="env",
        )

    def minimax_status(self) -> ModelCredentialStatus:
        return ModelCredentialStatus(
            present=_present("MINIMAX_API_KEY"),
            base_url=os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.chat"),
            model=os.environ.get("MINIMAX_MODEL", "minimaxm3"),
            source="env",
        )

    def openrouter_status(self) -> ModelCredentialStatus:
        return ModelCredentialStatus(
            present=_present("OPENROUTER_API_KEY"),
            base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api"),
            model=os.environ.get("OPENROUTER_MODEL", "openrouter/auto"),
            source="env",
        )

    def all_statuses(self) -> dict[str, ModelCredentialStatus]:
        return {
            "deepseek": self.deepseek_status(),
            "minimax": self.minimax_status(),
            "openrouter": self.openrouter_status(),
        }

    def ready(self) -> bool:
        """Fail-closed: every surfaced provider credential must be present."""
        return all(s.present for s in self.all_statuses().values())
