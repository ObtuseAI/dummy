"""Export Dummy's ledger to a read-only, hash-manifested Parquet snapshot."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autonomy.research_snapshot import export_research_snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("runtime/autonomy/ledger.db"))
    parser.add_argument("--out-dir", type=Path,
                        default=Path("artifacts/dummy/research_snapshots"))
    args = parser.parse_args()
    manifest_path, manifest = export_research_snapshot(args.db, args.out_dir)
    print(f"{manifest_path} rows={manifest['total_rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
