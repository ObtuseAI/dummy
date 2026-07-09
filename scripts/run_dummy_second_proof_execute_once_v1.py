"""Execute exactly one second controlled real-broker proof attempt.

Thin CLI wrapper around core.second_proof_runner.run_second_proof_execute_once.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.second_proof_runner import run_second_proof_execute_once


def main() -> int:
    report = run_second_proof_execute_once()
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"].startswith("SECOND_PROOF_EXECUTED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
