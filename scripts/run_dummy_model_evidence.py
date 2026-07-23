"""Build the model-authority evidence artifact + eligibility report.

Measurement only: writes the inert canonical forward-calibration artifact and
an eligibility report from settled llm_debate rows. Never authors the
authority dossier (that stays an explicit governance action), so it can grant
no authority. Runs read-only against the ledger.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from forecasting.model_evidence_builder import build_and_write  # noqa: E402

DEFAULT_DB = Path("runtime/autonomy/ledger.db")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    if not args.db.exists():
        print(json.dumps({"status": "NO_DB", "db": str(args.db)}))
        return 1
    report = build_and_write(args.db)
    print(json.dumps({
        "status": "OK",
        "scopes_measured": len(report["scopes"]),
        "governance_eligible_scopes": report["governance_eligible_scopes"],
        "dossier_authored": report["dossier_authored"],
        "evidence_artifact_sha256": report["evidence_artifact_sha256"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
