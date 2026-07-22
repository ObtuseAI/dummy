#!/usr/bin/env python
"""vNext shadow runtime pass (Wave-26 ignition).

One crash-isolated invocation per scheduled fire: complete every pending
organism episode whose market has settled (graded against verified ledger
truth with REAL held-out cases), then issue new shadow episodes from the
live bet-board artifact. Shadow-only by construction -- simulated execution,
no capital or session authority, promotion review human-only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Windowless launch (pythonw): stdio handles are None; keep prints alive.
if sys.stdout is None or sys.stderr is None:
    _log_dir = ROOT / "runtime" / "autonomy"
    _log_dir.mkdir(parents=True, exist_ok=True)
    _stream = open(_log_dir / "vnext_shadow_stdout.log", "a",
                   encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or _stream
    sys.stderr = sys.stderr or _stream


def main() -> int:
    from autonomy.session import PAPER_RESULTS_AUTHORITY
    from autonomy.vnext_runtime import run_shadow_pass

    summary = dict(run_shadow_pass())
    # Authority retirement disclosure: episodes keep accruing as research
    # evidence, but they can never enable or block live trading.
    summary["paper_results_authority"] = PAPER_RESULTS_AUTHORITY
    summary["execution_authority"] = False
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
