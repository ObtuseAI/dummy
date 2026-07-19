#!/usr/bin/env python
"""Operator switchboard: show and flip the system's on/off switches.

Usage:
    python scripts/dummy_switches.py                 # show current state
    python scripts/dummy_switches.py main off        # idle the whole brain
    python scripts/dummy_switches.py crypto off
    python scripts/dummy_switches.py sports on
    python scripts/dummy_switches.py league mlb off
    python scripts/dummy_switches.py llm claude on   # claude/codex/openrouter

Writes configs/switches.json (the source of truth). A per-key env var
(DUMMY_MAIN_ENABLED, ...) still overrides the file if set. Scheduled tasks pick
up the change on their next fire -- no restart.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.switches import (  # noqa: E402
    CONFIG_PATH,
    KNOWN_LEAGUES,
    LLM_BACKENDS,
    Switches,
)


def _load_raw() -> dict:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_raw(data: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(CONFIG_PATH)


def _flag(value: str) -> bool:
    v = value.strip().lower()
    if v in ("on", "true", "1", "yes"):
        return True
    if v in ("off", "false", "0", "no"):
        return False
    raise SystemExit(f"expected on/off, got {value!r}")


def _show() -> int:
    state = Switches.load().summary()
    print(json.dumps(state, indent=2, sort_keys=True))
    return 0


def main(argv: list[str]) -> int:
    if not argv:
        return _show()
    data = _load_raw()
    domain = argv[0].lower()

    if domain in ("main", "crypto", "sports") and len(argv) == 2:
        data[domain] = _flag(argv[1])
    elif domain == "league" and len(argv) == 3:
        league = argv[1].lower()
        if league not in KNOWN_LEAGUES:
            raise SystemExit(f"unknown league {league!r}; known: {', '.join(KNOWN_LEAGUES)}")
        data.setdefault("leagues", {})[league] = _flag(argv[2])
    elif domain == "llm" and len(argv) == 3:
        backend = argv[1].lower()
        if backend not in LLM_BACKENDS:
            raise SystemExit(f"unknown backend {backend!r}; known: {', '.join(LLM_BACKENDS)}")
        data.setdefault("llm", {})[backend] = _flag(argv[2])
    else:
        raise SystemExit(__doc__)

    _save_raw(data)
    print(f"set {' '.join(argv)}")
    return _show()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
