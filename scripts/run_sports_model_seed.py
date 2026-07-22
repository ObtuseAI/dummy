#!/usr/bin/env python
"""Run one bounded, display-only MLB/WNBA sports-model seed refresh."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.sports_model_seed import run_scheduled_seed  # noqa: E402


def main() -> int:
    code, status = run_scheduled_seed()
    print(json.dumps(status, sort_keys=True))
    # IgnoreNew plus the OS-held lock makes overlap an expected supervised
    # skip. Every real producer failure remains non-zero.
    return 0 if code in {0, 75} else code


if __name__ == "__main__":
    raise SystemExit(main())
