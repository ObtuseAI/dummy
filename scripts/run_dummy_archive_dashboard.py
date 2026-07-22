"""Launch the historical V3-V304 dashboard on an explicit loopback-only port.

This is a development/archive viewer, not a production or execution surface.
Do not provide broker or provider credentials to this process.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()
    os.environ["DUMMY_DASHBOARD_ARCHIVE_SURFACE"] = "offline-dev"
    import uvicorn

    uvicorn.run(
        "dashboard.backend.archive_app:app",
        host="127.0.0.1",
        port=args.port,
        log_level="warning",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
