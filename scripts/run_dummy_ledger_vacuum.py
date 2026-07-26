#!/usr/bin/env python
"""Run verified cooperative ledger VACUUM; never disables tasks or kills jobs."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.ledger_vacuum import vacuum_ledger  # noqa: E402


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("runtime/autonomy/ledger.db"))
    parser.add_argument("--backup-manifest", type=Path, required=True)
    parser.add_argument(
        "--min-free-gib",
        type=float,
        default=float(os.environ.get("DUMMY_VACUUM_MIN_FREE_GIB", "1.5")),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("runtime/autonomy/vacuum_report.json"),
    )
    args = parser.parse_args(argv)
    try:
        report = vacuum_ledger(
            args.db,
            backup_manifest=args.backup_manifest,
            min_freelist_bytes=max(0, int(args.min_free_gib * 1024 ** 3)),
        ).to_dict()
    except Exception as exc:
        report = {
            "status": "REFUSED",
            "error": f"{type(exc).__name__}:{exc}",
            "database": str(args.db),
            "backup_manifest": str(args.backup_manifest),
            "execution_authority": False,
        }
        _atomic_json(args.report, report)
        print(json.dumps(report, sort_keys=True))
        return 1
    _atomic_json(args.report, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
