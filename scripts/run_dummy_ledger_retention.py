#!/usr/bin/env python
"""Archive old settled-market signals after exact verification (dry-run by default)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.retention import (  # noqa: E402
    DEFAULT_BATCH_SIZE,
    DEFAULT_RETENTION_DAYS,
    default_archive_path,
    enforce_retention,
)
from autonomy.ledger_backup import require_recent_verified_backup  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("runtime/autonomy/ledger.db"))
    parser.add_argument("--archive", type=Path, default=None)
    parser.add_argument("--retention-days", type=float, default=DEFAULT_RETENTION_DAYS)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--apply", action="store_true", help="perform verified archive+delete")
    parser.add_argument("--vacuum", action="store_true", help="reclaim hot-ledger pages after apply")
    parser.add_argument(
        "--backup-manifest",
        type=Path,
        default=(
            Path(os.environ["DUMMY_MAINTENANCE_BACKUP_MANIFEST"])
            if os.environ.get("DUMMY_MAINTENANCE_BACKUP_MANIFEST")
            else None
        ),
    )
    args = parser.parse_args(argv)
    if args.vacuum and not args.apply:
        parser.error("--vacuum requires --apply")
    try:
        if args.apply:
            if args.backup_manifest is None:
                raise RuntimeError(
                    "--apply requires --backup-manifest (or "
                    "DUMMY_MAINTENANCE_BACKUP_MANIFEST)"
                )
            archive = args.archive or default_archive_path(args.db)
            required_sources = [args.db]
            if archive.exists():
                required_sources.append(archive)
            require_recent_verified_backup(
                args.backup_manifest,
                required_sources,
            )
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
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "error": str(exc),
            "execution_authority": False,
        }, sort_keys=True))
        return 1
    payload = report.to_dict()
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
