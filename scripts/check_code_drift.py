#!/usr/bin/env python
"""Deployed-code drift check (thin git/alert shell over autonomy.code_drift).

Compares the running checkout's HEAD to origin/main and, if the checkout has
drifted behind, emits a CODE_DRIFT alert and writes runtime/autonomy/
code_drift_status.json. Intended to run on the same schedule as the daemon so a
healthy-looking-but-stale deployment is surfaced.

Exit 0 = current; exit 1 = drifted (for a scheduler/monitor to key on).
Read-only: fetches and inspects; never checks out or mutates the tree.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.code_drift import code_drift_status  # noqa: E402

REMOTE_REF = "origin/main"
STATUS_PATH = Path("runtime/autonomy/code_drift_status.json")


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=60, check=True
        )
        return out.stdout.strip()
    except Exception:
        return None


def main() -> int:
    # Best-effort fetch so the comparison is against the live remote; a failed
    # fetch still compares against the last-known remote ref (fail-closed-ish).
    _git("fetch", "origin", "main", "--quiet")
    local_head = _git("rev-parse", "HEAD")
    remote_head = _git("rev-parse", REMOTE_REF)
    behind_raw = _git("rev-list", "--count", f"HEAD..{REMOTE_REF}")
    try:
        commits_behind = int(behind_raw) if behind_raw is not None else 0
    except ValueError:
        commits_behind = 0
    dirty = bool(_git("status", "--porcelain"))

    status = code_drift_status(
        local_head=local_head,
        remote_head=remote_head,
        commits_behind=commits_behind,
        remote_ref=REMOTE_REF,
        dirty=dirty,
    )

    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(status, indent=2, sort_keys=True), encoding="utf-8")

    if status["drifted"]:
        try:
            from autonomy.alerts import emit_alert

            emit_alert("CODE_DRIFT", status["message"], detail=status)
        except Exception:
            pass
        print(status["message"], file=sys.stderr)
        return 1
    print(status["message"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
