#!/usr/bin/env python
"""Archive old settled-market signals after exact verification (dry-run by default)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.retention import (  # noqa: E402
    DEFAULT_BATCH_SIZE,
    DEFAULT_RETENTION_DAYS,
    enforce_retention,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("runtime/autonomy/ledger.db"))
    parser.add_argument("--archive", type=Path, default=None)
    parser.add_argument("--retention-days", type=float, default=DEFAULT_RETENTION_DAYS)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--apply", action="store_true", help="perform verified archive+delete")
    parser.add_argument("--vacuum", action="store_true", help="reclaim hot-ledger pages after apply")
    args = parser.parse_args()
    if args.vacuum and not args.apply:
        parser.error("--vacuum requires --apply")
    try:
        report = enforce_retention(
            args.db,
            archive_path=args.archive,
            retention_days=args.retention_days,
            apply=args.apply,
            batch_size=args.batch_size,
            vacuum=args.vacuum,
        )
    except Exception as exc:
        print(json.dumps({
            "status": "REFUSED",
            "error": str(exc),
            "execution_authority": False,
        }, sort_keys=True))
        return 1
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
