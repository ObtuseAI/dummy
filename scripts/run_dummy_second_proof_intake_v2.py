"""Second-proof-aware evidence intake, reconciliation, and routing.

Thin CLI wrapper around core.second_proof_intake. Read-only against all
canonical state; writes only a new timestamped route report.

Usage:
    python scripts/run_dummy_second_proof_intake_v2.py [--evidence-dir PATH]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.second_proof_intake import ingest_second_proof, write_route_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", default=None, help="Explicit second_real_proof_* dir")
    parser.add_argument("--no-write", action="store_true", help="Print the route report without persisting it")
    args = parser.parse_args()

    report = ingest_second_proof(evidence_dir=args.evidence_dir)
    if not args.no_write and report["route"] != "ROUTE_NO_PROOF_TO_INGEST":
        path = write_route_report(report)
        report["route_report_path"] = str(path)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["route"] != "ROUTE_NO_PROOF_TO_INGEST" else 3


if __name__ == "__main__":
    raise SystemExit(main())
