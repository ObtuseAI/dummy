"""LLM backend on/off, read by the router without importing the autonomy
package. Same source of truth as autonomy.switches -- configs/switches.json's
``llm`` block, with a ``DUMMY_LLM_<BACKEND>_ENABLED`` (0/1) env override.

Backends: ``openrouter`` (the six HTTP models), ``claude`` and ``codex`` (the
local CLIs). Fail-safe defaults: openrouter ON, the CLI backends OFF (they
bill personal subscriptions).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

SWITCHES_PATH = Path(__file__).parent.parent / "configs" / "switches.json"
_DEFAULTS = {"openrouter": True, "claude": False, "codex": False}


def llm_backend_enabled(backend: str) -> bool:
    backend = (backend or "").lower()
    raw = os.environ.get(f"DUMMY_LLM_{backend.upper()}_ENABLED")
    if raw is not None and raw.strip() in ("0", "1"):
        return raw.strip() == "1"
    default = _DEFAULTS.get(backend, False)
    try:
        data = json.loads(SWITCHES_PATH.read_text(encoding="utf-8"))
        llm = data.get("llm") if isinstance(data, dict) else None
        if isinstance(llm, dict) and backend in llm and isinstance(llm[backend], bool):
            return llm[backend]
    except (OSError, ValueError, TypeError):
        pass
    return default
