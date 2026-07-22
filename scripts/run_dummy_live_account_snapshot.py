"""Refresh Dummy's sanitized authenticated Kalshi account snapshot."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import IO


def _redirect_supervised_stdio() -> IO[str] | None:
    raw_path = os.environ.get("DUMMY_LIVE_ACCOUNT_STDIO_LOG", "").strip()
    if not raw_path:
        return None
    path = Path(raw_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a", encoding="utf-8", buffering=1)
    os.dup2(handle.fileno(), 1)
    os.dup2(handle.fileno(), 2)
    return handle


_SUPERVISED_LOG_HANDLE = _redirect_supervised_stdio()

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.live_account_snapshot import (  # noqa: E402
    LIVE_ACCOUNT_SNAPSHOT_PATH,
    load_live_account_env,
    refresh_live_account_snapshot,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write the sanitized GET-only Kalshi account snapshot."
    )
    parser.add_argument("--output", type=Path, default=LIVE_ACCOUNT_SNAPSHOT_PATH)
    parser.add_argument(
        "--no-fills",
        action="store_true",
        help="skip the optional GET /portfolio/fills aggregate",
    )
    args = parser.parse_args()

    load_live_account_env(ROOT / ".env")
    snapshot = asyncio.run(
        refresh_live_account_snapshot(
            args.output,
            include_fills=not args.no_fills,
        )
    )
    proof = snapshot.get("http_proof") or {}
    print(
        json.dumps(
            {
                "artifact": str(args.output),
                "status": snapshot.get("status"),
                "stale": snapshot.get("stale"),
                "get_only": proof.get("get_only"),
                "total_requests": proof.get("total_requests"),
                "methods": proof.get("methods"),
                "path_families": proof.get("path_families"),
            },
            sort_keys=True,
        )
    )
    if snapshot.get("status") == "ERROR":
        return 1
    if snapshot.get("status") == "STALE":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
