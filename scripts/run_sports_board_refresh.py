#!/usr/bin/env python
"""Bounded scheduled MLB/WNBA display-board refresh.

Public GETs and local display artifacts only.  This process has no ledger,
session, broker, order, promotion, trust, or capital authority.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.sports_board_refresh import run_scheduled_refresh  # noqa: E402


def main() -> int:
    code, status = run_scheduled_refresh()
    print(json.dumps(status, sort_keys=True))
    # IgnoreNew plus the OS-held lock makes overlap an expected supervised
    # skip, not a task failure.  All actual refresh failures remain non-zero.
    return 0 if code in {0, 75} else code


if __name__ == "__main__":
    raise SystemExit(main())
