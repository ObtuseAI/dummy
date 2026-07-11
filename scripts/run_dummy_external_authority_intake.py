"""Consolidated runner: external authority intake V2 (V228). Validate-only. No submit, no approval writes, no runtime/approvals."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from archive.report_scripts.generate_v228_reports import main as generate_main


def main() -> dict:
    final = generate_main()
    return {
        "runner": "external_authority_intake",
        "verdict": final.get("verdict"),
        "external_authority_intake_v2_controller_status": final.get("external_authority_intake_v2_controller_status"),
        "intake_valid": final.get("intake_valid", False),
        "approval_files_written": final.get("approval_files_written", 0),
        "runtime_approvals_created_by_dummy": final.get("runtime_approvals_created_by_dummy", False),
        "current_next_action": final.get("current_next_action"),
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
