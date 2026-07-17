"""Deployed-code drift detection.

The ops watchdog (``autonomy/watchdog.py``) checks that ARTIFACTS are fresh, but
a daemon can be cycling happily on stale CODE -- the deployed checkout drifting
commits behind ``origin/main`` while every heartbeat still looks healthy. This
module is the missing check: given the local and remote HEADs and how far behind
the checkout is, it decides whether to raise a drift alert.

Pure core (``code_drift_status``) so it is fully testable; the thin git/alert
shell lives in ``scripts/check_code_drift.py``.
"""
from __future__ import annotations

from typing import Any

# Behind by more than this many commits escalates the alert severity.
DRIFT_WARN_COMMITS = 1
DRIFT_CRITICAL_COMMITS = 20


def code_drift_status(
    *,
    local_head: str | None,
    remote_head: str | None,
    commits_behind: int,
    remote_ref: str = "origin/main",
    dirty: bool = False,
) -> dict[str, Any]:
    """Decide whether the deployed checkout has drifted from the remote.

    ``commits_behind`` is ``git rev-list --count <local>..<remote>``. Drift is
    true when the checkout is behind the remote or the HEADs differ. Severity is
    ``critical`` once the checkout is far behind (a whole program can be missing,
    as happened when live ran ~58 commits stale), else ``warning``.
    """
    behind = max(0, int(commits_behind))
    heads_known = bool(local_head) and bool(remote_head)
    drifted = behind > 0 or (heads_known and local_head != remote_head)

    if not drifted:
        severity = "info"
        message = f"deployed code current with {remote_ref}"
    elif behind >= DRIFT_CRITICAL_COMMITS:
        severity = "critical"
        message = (
            f"deployed code is {behind} commits behind {remote_ref} -- a whole "
            "program may be missing; redeploy"
        )
    else:
        severity = "warning"
        message = f"deployed code is {behind} commit(s) behind {remote_ref}; redeploy"

    return {
        "drifted": drifted,
        "commits_behind": behind,
        "local_head": local_head,
        "remote_head": remote_head,
        "remote_ref": remote_ref,
        "dirty": bool(dirty),
        "severity": severity,
        "message": message,
    }
