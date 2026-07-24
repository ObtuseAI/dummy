#!/usr/bin/env python
"""Nightly self-improvement chain (Wave-20).

One invocation runs, in order, the diagnostic + self-correction loops that
have no scheduled home of their own, then assembles the ranked improvement
plan from every artifact on disk:

  1. loss engine            -> loss_attribution.json      (where we bleed)
  2. negative controls      -> negative_control_report.json + no_edge_map.json
                               (fabrication tripwires; feeds the fusion floor)
  3. tuner --auto-promote   -> tuning_proposals.json + tuned_params.json
                               (walk-forward-proven, step-capped overrides)
  4. improvement planner    -> self_improvement_plan.json (the ranked plan)

Each step runs as its own subprocess, crash-isolated with a bounded
timeout: one failing loop never costs the rest, and the plan records every
step's outcome so a silently-dead loop is visible on the dashboard instead
of just quietly missing. Step failures PROPAGATE (2026-07-24 audit: on
Jul 23 all three steps exited 1 while this wrapper exited 0, so Task
Scheduler showed success): the wrapper exits ``EXIT_STEP_FAILED`` when any
step exits nonzero, times out, or fails to spawn -- after the plan artifact
(including per-step status) is written.

Read-only against the ledger throughout; no session, execution, or capital
authority anywhere in this chain.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Windows: a console child spawned from a windowless (pythonw) task otherwise
# gets its own new console window. CREATE_NO_WINDOW keeps every step silent
# regardless of whether this runs under python.exe or pythonw.exe.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STEPS: list[tuple[str, list[str], float]] = [
    ("loss_engine", ["scripts/run_dummy_loss_engine.py"], 900.0),
    ("negative_controls", ["scripts/run_negative_controls.py"], 900.0),
    ("tuner", ["scripts/run_dummy_tuner.py", "--auto-promote"], 900.0),
]

# Distinct exit code for "the chain ran but at least one step failed", so a
# Task Scheduler run with dead loops shows red instead of green (a wrapper
# crash keeps Python's own exit 1 and stays distinguishable).
EXIT_STEP_FAILED = 3


def main() -> int:
    outcomes: dict[str, dict] = {}
    for name, argv, timeout in STEPS:
        try:
            completed = subprocess.run(
                [sys.executable, *argv], cwd=ROOT, timeout=timeout,
                capture_output=True, text=True, creationflags=_NO_WINDOW,
            )
            tail = (completed.stdout or "").strip().splitlines()
            outcomes[name] = {
                "exit": completed.returncode,
                "status": "OK" if completed.returncode == 0 else "FAILED",
                "last_line": tail[-1][:400] if tail else "",
            }
            if completed.returncode != 0:
                err_tail = (completed.stderr or "").strip().splitlines()
                outcomes[name]["stderr_last"] = (
                    err_tail[-1][:400] if err_tail else ""
                )
        except subprocess.TimeoutExpired:
            outcomes[name] = {"exit": None, "status": "FAILED",
                              "error": f"timeout after {timeout}s"}
        except Exception as exc:
            outcomes[name] = {"exit": None, "status": "FAILED",
                              "error": f"{type(exc).__name__}: {exc}"[:200]}

    failed_steps = [
        name for name, outcome in outcomes.items() if outcome.get("exit") != 0
    ]

    from autonomy.improvement_planner import assemble_plan, write_plan

    plan = assemble_plan()
    plan["chain"] = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "steps": outcomes,
        "failed_steps": failed_steps,
        "ok": not failed_steps,
    }
    path = write_plan(plan)
    print(json.dumps({
        "status": "OK" if not failed_steps else "STEP_FAILURES",
        "steps": {name: outcome.get("exit") for name, outcome in outcomes.items()},
        "failed_steps": failed_steps,
        "plan_items": len(plan.get("items") or []),
        "plan": str(path),
    }))
    return EXIT_STEP_FAILED if failed_steps else 0


if __name__ == "__main__":
    raise SystemExit(main())
