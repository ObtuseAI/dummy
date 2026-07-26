#!/usr/bin/env python
"""Create an online, hashed, restore-drilled backup of Dummy's evidence DBs."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.ledger_backup import create_verified_backup  # noqa: E402
from autonomy.retention import default_archive_path  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("runtime/autonomy/ledger.db"))
    parser.add_argument("--archive", type=Path, default=None)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument(
        "--allow-same-volume",
        action="store_true",
        help="permit an interim snapshot that does not satisfy off-volume DR",
    )
    args = parser.parse_args(argv)
    archive = args.archive
    if archive is None:
        candidate = default_archive_path(args.db)
        archive = candidate if candidate.exists() else None
    try:
        report = create_verified_backup(
            args.db,
            args.destination,
            archive=archive,
            require_distinct_volume=not args.allow_same_volume,
        )
    except Exception as exc:
        print(json.dumps({
            "status": "REFUSED",
            "error": f"{type(exc).__name__}:{exc}",
            "execution_authority": False,
        }, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
