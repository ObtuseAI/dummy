"""Evidence-earned runtime parameter overrides (Wave-20).

The WS-9 tuner is a proposer: it fits each registered scalar walk-forward
and writes proposals. Closing the self-tuning loop must not overturn its
"never write a constant back into a .py file" rule -- so promotions land in
a RUNTIME OVERRIDES artifact instead, consumed at model-construction time.
Code constants stay the authoritative defaults; an override is an
evidence-earned delta that is:

  * gated on the tuner's own walk-forward verdict ("candidate" = paired
    per-cluster out-of-sample improvement with a CI strictly above zero);
  * step-capped (one promotion per nightly run, each move at most
    MAX_STEP_FRACTION of the value in force -- a season of evidence walks a
    sigma, a single night cannot yank it);
  * fully audited (every applied move appends to tuned_params_log.jsonl
    with the evidence snapshot that justified it);
  * revertible by deleting the artifact (models fall back to code defaults).

Consumption is per-parameter opt-in: only parameters listed in
``CONSUMED_PARAMS`` are ever read back, so a proposal for an unconsumed
engine cannot silently change behavior.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OVERRIDES_PATH = Path("runtime/autonomy/tuned_params.json")
LOG_PATH = Path("runtime/autonomy/tuned_params_log.jsonl")

MAX_STEP_FRACTION = 0.20

# Parameters with a wired consumption point. Everything else the tuner
# proposes stays report-only until its consumer is built and tested.
CONSUMED_PARAMS = frozenset({
    "nfl_total_sigma",
    "ncaaf_total_sigma",
    "wnba_total_sigma",
})


def load_overrides(path: Path | None = None) -> dict[str, float]:
    """{param: value_in_force}. Fail-open: no/malformed artifact -> {}."""
    try:
        payload = json.loads((path or OVERRIDES_PATH).read_text(encoding="utf-8"))
        overrides = payload.get("overrides") or {}
        return {
            str(name): float(entry["value"])
            for name, entry in overrides.items()
            if isinstance(entry, dict) and isinstance(entry.get("value"), (int, float))
        }
    except (OSError, ValueError, TypeError):
        return {}


def value_in_force(name: str, default: float, path: Path | None = None) -> float:
    if name not in CONSUMED_PARAMS:
        return default
    return load_overrides(path).get(name, default)


def promote_from_report(
    report: dict[str, Any],
    *,
    now_iso: str,
    path: Path | None = None,
    log_path: Path | None = None,
) -> dict[str, Any]:
    """Apply walk-forward-proven proposals as capped overrides.

    Only ``verdict == "candidate"`` proposals for CONSUMED_PARAMS move
    anything; each moves at most MAX_STEP_FRACTION from the value in force
    toward the tuner's best, so convergence takes consecutive nights of
    consistent evidence. Returns {applied: [...], skipped: [...]}.
    """
    target = path or OVERRIDES_PATH
    payload: dict[str, Any] = {"overrides": {}}
    try:
        existing = json.loads(target.read_text(encoding="utf-8"))
        if isinstance(existing.get("overrides"), dict):
            payload["overrides"] = existing["overrides"]
    except (OSError, ValueError, TypeError):
        pass

    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for proposal in report.get("proposals") or []:
        name = str(proposal.get("name"))
        verdict = proposal.get("verdict")
        if verdict != "candidate":
            continue
        if name not in CONSUMED_PARAMS:
            skipped.append({"name": name, "reason": "no consumption point wired"})
            continue
        current_default = proposal.get("current")
        best = proposal.get("best")
        if not isinstance(current_default, (int, float)) or not isinstance(best, (int, float)):
            skipped.append({"name": name, "reason": "malformed proposal"})
            continue
        in_force = load_overrides(target).get(name, float(current_default))
        step_cap = abs(in_force) * MAX_STEP_FRACTION
        move = max(-step_cap, min(step_cap, float(best) - in_force))
        if abs(move) < 1e-9:
            skipped.append({"name": name, "reason": "already in force"})
            continue
        new_value = round(in_force + move, 6)
        entry = {
            "value": new_value,
            "updated_at": now_iso,
            "toward": float(best),
            "evidence": {
                "test_delta": proposal.get("test_delta"),
                "test_delta_ci": proposal.get("test_delta_ci"),
                "n_clusters": proposal.get("n_clusters"),
            },
        }
        payload["overrides"][name] = entry
        applied.append({"name": name, "from": in_force, "to": new_value,
                        "toward": float(best)})

    if applied:
        payload["generated_at"] = now_iso
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True),
                             encoding="utf-8")
        temporary.replace(target)
        log = log_path or LOG_PATH
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            for move_record in applied:
                fh.write(json.dumps({"at": now_iso, **move_record},
                                    sort_keys=True) + "\n")
    return {"applied": applied, "skipped": skipped}
