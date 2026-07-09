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


class CredentialReadiness:
    """Detect whether DeepSeekV4Flash and MinimaxM3 credentials are available.

    Reads environment variables and exposes redacted status objects.  No API
    key value is ever retained or returned.

    Environment variables:
      - DEEPSEEK_API_KEY (required for "present")
      - DEEPSEEK_BASE_URL (optional, default https://api.deepseek.com)
      - DEEPSEEK_MODEL (optional, default deepseekv4flash)
      - MINIMAX_API_KEY (required for "present")
      - MINIMAX_BASE_URL (optional, default https://api.minimax.chat)
      - MINIMAX_MODEL (optional, default minimaxm3)
    """

    def deepseek_status(self) -> ModelCredentialStatus:
        return ModelCredentialStatus(
            present=bool(os.environ.get("DEEPSEEK_API_KEY")),
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.environ.get("DEEPSEEK_MODEL", "deepseekv4flash"),
            source="env",
        )

    def minimax_status(self) -> ModelCredentialStatus:
        return ModelCredentialStatus(
            present=bool(os.environ.get("MINIMAX_API_KEY")),
            base_url=os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.chat"),
            model=os.environ.get("MINIMAX_MODEL", "minimaxm3"),
            source="env",
        )

    def all_statuses(self) -> dict[str, ModelCredentialStatus]:
        return {
            "deepseek": self.deepseek_status(),
            "minimax": self.minimax_status(),
        }

    def ready(self) -> bool:
        return all(s.present for s in self.all_statuses().values())
