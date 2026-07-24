"""The self-improvement planner (Wave-20).

Every diagnostic loop in the system produces an artifact: where we bleed
(loss engine), where there is no edge (no-edge map), why promotions were
declined (declines dossiers), what the negative-control battery flagged,
what the tuner proposed and auto-applied, and how accurate the fused picks
are. This module reads them ALL and emits one ranked plan -- the machine's
own answer to "what should improve next" -- annotating each item with
whether a CLOSED loop already actions it autonomously (tuner overrides,
validated calibration maps, the fusion floor, the promotion ladder,
performance quarantines, auto-demotion) or whether it is genuinely
operator-gated (capital, new data sources, live deploys).

Read-only over artifacts; fail-open per input (a missing artifact
contributes nothing rather than an error). The plan is itself an artifact:
``runtime/autonomy/self_improvement_plan.json``, surfaced on the dashboard.

Wave-84 (2026-07-24 audit, P1 item 11) closes the plan's own loop -- until
now nothing diffed successive plans, so an item could silently vanish when
its source artifact changed and no one could tell "fixed" from "the writer
that measured it died":

  * every item carries a STABLE ``fingerprint`` (identity family + target,
    never severity or prose) plus ``first_seen_at``/``runs_seen``/``status``;
  * each run appends a versioned snapshot row to
    ``runtime/autonomy/improvement_plan_history.jsonl`` (append-only,
    line-capped, tail-preserved, atomic tmp+replace -- the same discipline
    ``scripts/run_dummy_log_rotation.py`` applies to allowlisted tapes);
  * the plan carries a ``history`` block diffing this run against the last
    row: ``new_items``, ``resolved_items`` (present before, absent now --
    their evidence cleared, so they are AUTO-CLOSED with the run id they
    resolved in) and ``persisting_items`` with an age in runs;
  * a dead measurement loop -- a crashed report writer in
    ``report_writer_failures.json`` or a failed self-improvement chain step
    -- is surfaced as a TOP_SEVERITY item, because a dead loop invalidates
    every finding ranked below it.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUNTIME_DIR = Path("runtime/autonomy")
PLAN_PATH = RUNTIME_DIR / "self_improvement_plan.json"

HISTORY_NAME = "improvement_plan_history.jsonl"
HISTORY_PATH = RUNTIME_DIR / HISTORY_NAME
WRITER_FAILURES_NAME = "report_writer_failures.json"

PLAN_SCHEMA_VERSION = 2

# A crashed writer or a dead chain step invalidates everything below it: the
# findings this plan ranks are only as true as the loops that wrote them. So
# measurement-loop deaths outrank even the fabricated-benchmark alarm (10.0)
# by an order of magnitude and can never sort below an ordinary finding.
TOP_SEVERITY = 100.0

# History file bounds. Rows are complete state snapshots, so dropping the
# oldest rows loses nothing the next run needs (it reads only the last row).
HISTORY_KEEP_ROWS = 200
HISTORY_MAX_TRACKED = 2000     # per-row fingerprint cap (severity order)
DIFF_LIST_CAP = 250            # per-section cap inside the plan artifact

# Out-of-band transport from assemble_plan() to write_plan(): the full
# fingerprint state (which spans items dropped by the artifact's top-100
# truncation) rides here and is POPPED before the plan is serialized, so it
# never bloats the dashboard payload.
HISTORY_ROW_KEY = "_history_row"

# Kinds that are the same item wearing a different state label -- the tuner
# trio flips as a parameter gets wired/applied, which is not a new finding.
_IDENTITY_FAMILIES = {
    "tuning_applied": "tuning",
    "tuning_pending": "tuning",
    "tuning_unconsumed": "tuning",
}


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def item_fingerprint(item: dict[str, Any]) -> str:
    """Stable identity hash for a plan item.

    Derived ONLY from the identity family and the target -- never from
    severity, evidence, or prose -- so an item whose numbers move is the
    same item next run and the diff stays meaningful.
    """
    kind = str((item or {}).get("kind") or "")
    family = _IDENTITY_FAMILIES.get(kind, kind)
    target = str((item or {}).get("target") or "")
    digest = hashlib.sha256(f"{family}\x1f{target}".encode("utf-8"))
    return digest.hexdigest()[:16]


# ---------------------------------------------------------------------------
# Measurement-loop integrity: dead writers and dead chain steps
# ---------------------------------------------------------------------------

def writer_failure_items(runtime_dir: Path) -> list[dict[str, Any]]:
    """TOP_SEVERITY items for every crashed report writer (Wave-83 artifact).

    ``report_writer_failures.json`` is written on EVERY readiness run, even
    when empty, so a missing artifact means the rail itself never ran and a
    non-empty ``failures`` list means some artifact this plan ranks is stale
    or absent. One entry per writer (the latest attempt wins).
    """
    payload = _load(runtime_dir / WRITER_FAILURES_NAME)
    failures = payload.get("failures")
    if not isinstance(failures, list):
        return []
    latest: dict[str, dict[str, Any]] = {}
    for entry in failures:
        if not isinstance(entry, dict):
            continue
        writer = str(entry.get("writer") or "unknown")
        known = latest.get(writer)
        if known is None or str(entry.get("at") or "") >= str(known.get("at") or ""):
            latest[writer] = entry
    items: list[dict[str, Any]] = []
    for writer, entry in sorted(latest.items()):
        trace = entry.get("traceback")
        items.append({
            "kind": "report_writer_dead",
            "target": writer,
            "severity": TOP_SEVERITY,
            "evidence": {
                "error": str(entry.get("error") or "")[:300],
                "at": entry.get("at"),
                "traceback_tail": [str(line)[:200] for line in trace[-3:]]
                if isinstance(trace, list) else [],
                "artifact": WRITER_FAILURES_NAME,
                "failures_generated_at": payload.get("generated_at"),
            },
            "closed_loops": [],
            "owner": "operator",
            "next": "the writer feeding this report CRASHED -- every finding"
                    " derived from its artifact is stale or absent, so repair"
                    " the writer before trusting anything ranked below it",
        })
    return items


def _chain_status(runtime_dir: Path,
                  chain: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    """The self-improvement chain's per-step status block, and its provenance.

    ``scripts/run_dummy_self_improvement.py`` attaches the block to the plan
    artifact AFTER assembling it, so on disk the freshest available status is
    the PREVIOUS run's. Callers that already hold this run's outcomes pass
    them in as ``chain`` and get live grading instead.
    """
    if isinstance(chain, dict):
        return chain, "live"
    prior = _load(runtime_dir / PLAN_PATH.name).get("chain")
    return (prior if isinstance(prior, dict) else {}), "previous_run"


def chain_step_items(block: dict[str, Any], source: str) -> list[dict[str, Any]]:
    """TOP_SEVERITY items for every self-improvement chain step that failed."""
    steps = (block or {}).get("steps")
    if not isinstance(steps, dict):
        return []
    items: list[dict[str, Any]] = []
    for name, outcome in sorted(steps.items()):
        if not isinstance(outcome, dict) or outcome.get("status") == "OK":
            continue
        items.append({
            "kind": "chain_step_dead",
            "target": str(name),
            "severity": TOP_SEVERITY,
            "evidence": {
                "status": outcome.get("status"),
                "exit": outcome.get("exit"),
                "error": str(outcome.get("error") or "")[:300] or None,
                "stderr_last": str(outcome.get("stderr_last") or "")[:300] or None,
                "chain_ran_at": (block or {}).get("ran_at"),
                "status_source": source,
            },
            "closed_loops": [],
            "owner": "operator",
            "next": "a self-improvement chain step is DEAD: the artifact it"
                    " writes is stale, so items ranked from that artifact are"
                    " declarations rather than measurements -- repair the step"
                    + ("" if source == "live" else
                       "; graded from the LAST recorded chain run, so a"
                       " repaired step clears on the next run"),
        })
    return items


# ---------------------------------------------------------------------------
# Plan history: versioned snapshots + the plan-vs-outcome diff
# ---------------------------------------------------------------------------

def _history_keep_rows() -> int:
    raw = (os.environ.get("DUMMY_PLAN_HISTORY_KEEP_ROWS") or "").strip()
    try:
        value = int(float(raw))
    except ValueError:
        return HISTORY_KEEP_ROWS
    return value if value > 0 else HISTORY_KEEP_ROWS


def read_last_history_row(path: Path | None = None) -> dict[str, Any]:
    """The newest valid snapshot row, or {} on any miss.

    Walks backwards past blank/corrupt trailing lines (a crash mid-append
    must not blind the next run's diff) and never raises.
    """
    target = Path(path) if path is not None else HISTORY_PATH
    try:
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    except (OSError, ValueError):
        return {}
    for raw in reversed(lines):
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except ValueError:
            continue
        if isinstance(row, dict):
            return row
    return {}


def _tracked(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tracked = (row or {}).get("tracked")
    if not isinstance(tracked, dict):
        return {}
    return {str(key): value for key, value in tracked.items()
            if isinstance(value, dict)}


def _diff_entry(fingerprint: str, state: dict[str, Any],
                **extra: Any) -> dict[str, Any]:
    entry = {
        "fingerprint": fingerprint,
        "kind": state.get("kind"),
        "target": state.get("target"),
        "first_seen_at": state.get("first_seen_at"),
    }
    entry.update(extra)
    return entry


def annotate_history(items: list[dict[str, Any]], previous: dict[str, Any],
                     run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Stamp identity/age onto every item and diff this run against ``previous``.

    Mutates each item in ``items`` (adds ``fingerprint``, ``first_seen_at``,
    ``runs_seen``, ``status``) and returns ``(history_block, snapshot_row)``.
    The diff runs over the FULL item list -- not the artifact's truncated
    top-100 -- so an item is never reported resolved merely for falling off
    the display cut.
    """
    prior = _tracked(previous)
    try:
        run_index = int(previous.get("run_index") or 0) + 1
    except (TypeError, ValueError):
        run_index = 1

    tracked: dict[str, dict[str, Any]] = {}
    new_items: list[dict[str, Any]] = []
    persisting_items: list[dict[str, Any]] = []
    for item in items:
        fingerprint = item_fingerprint(item)
        before = prior.get(fingerprint)
        first_seen = str((before or {}).get("first_seen_at") or "") or run_id
        try:
            runs_seen = int((before or {}).get("runs_seen") or 0) + 1
        except (TypeError, ValueError):
            runs_seen = 1
        item["fingerprint"] = fingerprint
        item["first_seen_at"] = first_seen
        item["runs_seen"] = runs_seen
        item["status"] = "persisting" if before else "new"
        if fingerprint in tracked:
            continue                      # duplicate identity within one run
        state = {
            "kind": item.get("kind"),
            "target": item.get("target"),
            "severity": item.get("severity"),
            "first_seen_at": first_seen,
            "runs_seen": runs_seen,
        }
        tracked[fingerprint] = state
        entry = _diff_entry(fingerprint, state, severity=item.get("severity"),
                            runs_seen=runs_seen)
        (persisting_items if before else new_items).append(entry)

    resolved_items = [
        _diff_entry(fingerprint, state, runs_seen=state.get("runs_seen"),
                    resolved_in_run=run_id,
                    last_seen_at=previous.get("run_id"))
        for fingerprint, state in sorted(prior.items())
        if fingerprint not in tracked
    ]

    first_run = not previous
    history = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "run_id": run_id,
        "run_index": run_index,
        "first_run": first_run,
        "previous_run_id": previous.get("run_id"),
        "counts": {
            "total": len(tracked),
            "new": len(new_items),
            "resolved": len(resolved_items),
            "persisting": len(persisting_items),
        },
        "new_items": new_items[:DIFF_LIST_CAP],
        "resolved_items": resolved_items[:DIFF_LIST_CAP],
        "persisting_items": persisting_items[:DIFF_LIST_CAP],
        "list_cap": DIFF_LIST_CAP,
        "truncated": max(len(new_items), len(resolved_items),
                         len(persisting_items)) > DIFF_LIST_CAP,
        "history_artifact": HISTORY_NAME,
    }

    ordered = sorted(tracked.items(),
                     key=lambda kv: -float(kv[1].get("severity") or 0.0))
    row = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "run_id": run_id,
        "run_index": run_index,
        "item_count": len(tracked),
        "counts": dict(history["counts"]),
        "tracked": dict(ordered[:HISTORY_MAX_TRACKED]),
        "resolved_items": resolved_items[:DIFF_LIST_CAP],
    }
    return history, row


def _bound_history(path: Path, keep_rows: int) -> None:
    """Tail-preserve the snapshot tape at ``keep_rows`` (atomic tmp+replace).

    Hysteresis at 1.5x so a steady-state run never rewrites the file, and a
    file another process holds (os.replace raises on Windows) is skipped and
    picked up next run. Never deletes, only tail-preserves.
    """
    try:
        lines = [line for line in
                 path.read_text(encoding="utf-8", errors="replace").splitlines()
                 if line.strip()]
    except (OSError, ValueError):
        return
    if len(lines) <= int(keep_rows * 1.5):
        return
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text("\n".join(lines[-keep_rows:]) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass


def append_history_row(row: dict[str, Any] | None,
                       path: Path | None = None) -> Path | None:
    """Append one snapshot row to the append-only history tape. Fail-soft."""
    if not isinstance(row, dict):
        return None
    target = Path(path) if path is not None else HISTORY_PATH
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    except (OSError, ValueError, TypeError):
        return None
    _bound_history(target, _history_keep_rows())
    return target


def assemble_plan(runtime_dir: Path | None = None, *,
                  chain: dict[str, Any] | None = None,
                  now_iso: str | None = None,
                  history_path: Path | None = None) -> dict[str, Any]:
    rd = runtime_dir or RUNTIME_DIR
    items: list[dict[str, Any]] = []

    # 0) Measurement-loop integrity FIRST (2026-07-24 audit): a crashed
    # report writer or a dead chain step means the artifacts ranked below are
    # stale or absent. Emitted at TOP_SEVERITY and placed ahead of every
    # other item so the stable sort keeps them at the head of the plan.
    writer_items = writer_failure_items(rd)
    chain_block, chain_source = _chain_status(rd, chain)
    step_items = chain_step_items(chain_block, chain_source)
    items.extend(writer_items)
    items.extend(step_items)

    # 1) Bleeding scopes: the loss engine's verdicts. Trust, the fusion
    # floor, and quarantines already contain these; a PERSISTENT bleeder is
    # a modeling gap worth a targeted build.
    loss = _load(rd / "loss_attribution.json")
    for entry in (loss.get("scopes") or []):
        if isinstance(entry, dict) and entry.get("verdict") == "bleeding":
            items.append({
                "kind": "bleeding_scope",
                "target": entry.get("scope"),
                "severity": abs(float(entry.get("cluster_edge") or 0.0)),
                "evidence": {"cluster_edge": entry.get("cluster_edge"),
                             "n_clusters": entry.get("n_clusters")},
                "closed_loops": ["trust_downweight", "fusion_floor",
                                 "performance_quarantine", "auto_demotion"],
                "owner": "machine",
                "next": "persistent bleeding after floor+trust = modeling gap;"
                        " candidate for a targeted model wave",
            })

    # 2) Significantly-negative scopes (the fusion floor consumes the same
    # map; listed so the plan shows WHAT is currently suppressed).
    no_edge = _load(rd / "no_edge_map.json")
    for entry in (no_edge.get("significantly_negative") or []):
        if isinstance(entry, dict):
            items.append({
                "kind": "significantly_negative_scope",
                "target": entry.get("scope"),
                "severity": abs(float(entry.get("edge_mean") or 0.0)),
                "evidence": {key: entry.get(key) for key in
                             ("edge_mean", "ci_upper", "clusters")},
                "closed_loops": ["fusion_floor"],
                "owner": "machine",
                "next": "excluded from fusion while negative; exits on evidence",
            })

    # 3) Declined promotions: the scopes worth accelerating, failing criteria
    # named (Wave-19 dossiers).
    declines = _load(rd / "promotion_declines.json")
    for entry in (declines.get("declined") or []):
        if isinstance(entry, dict):
            items.append({
                "kind": "promotion_declined",
                "target": entry.get("scope"),
                "severity": 0.5,
                "evidence": {"reason": entry.get("reason")},
                "closed_loops": ["promotion_ladder"],
                "owner": "machine",
                "next": "ladder re-evaluates nightly; failing criteria named"
                        " in the dossier",
            })

    # 4) Negative-control flags: measurement-integrity alarms (the Wave-5
    # fabricated-benchmark class) outrank everything.
    battery = _load(rd / "negative_control_report.json")
    for flagged in (battery.get("flagged_sources") or []):
        items.append({
            "kind": "negative_control_flag",
            "target": flagged if isinstance(flagged, str) else json.dumps(flagged),
            "severity": 10.0,
            "evidence": {"report": "negative_control_report.json"},
            "closed_loops": [],
            "owner": "operator",
            "next": "measurement-integrity alarm: investigate before trusting"
                    " this source's evidence",
        })

    # 5) Tuning: applied moves prove the loop closed; proven candidates
    # WITHOUT a consumption point are each one small build from self-tuning.
    from autonomy.tuned_params import CONSUMED_PARAMS

    tuned = _load(rd / "tuned_params.json")
    proposals = _load(rd / "tuning_proposals.json")
    consumed_now = set((tuned.get("overrides") or {}).keys())
    for proposal in (proposals.get("proposals") or []):
        if not isinstance(proposal, dict) or proposal.get("verdict") != "candidate":
            continue
        name = str(proposal.get("name"))
        if name in CONSUMED_PARAMS:
            items.append({
                "kind": "tuning_applied" if name in consumed_now else "tuning_pending",
                "target": name,
                "severity": 0.4,
                "evidence": {"test_delta": proposal.get("test_delta"),
                             "best": proposal.get("best")},
                "closed_loops": ["tuner_auto_promote"],
                "owner": "machine",
                "next": "override walks toward best at <=20%/night while the"
                        " walk-forward CI holds",
            })
        else:
            items.append({
                "kind": "tuning_unconsumed",
                "target": name,
                "severity": 0.6,
                "evidence": {"test_delta": proposal.get("test_delta"),
                             "best": proposal.get("best")},
                "closed_loops": [],
                "owner": "operator",
                "next": "walk-forward-proven improvement with NO consumption"
                        " point -- wire this parameter into tuned_params to"
                        " close its loop",
            })

    # 6) Pick-accuracy floor: any (league|market_type) cell measurably under
    # 50% hit rate on adequate volume is a mispriced pick side -- the most
    # direct violation of the operator's floor directive.
    readiness = _load(rd / "readiness_report.json")
    picks = (readiness.get("picks") or {}).get("sources") or []
    for source_block in picks:
        for scope, cell in (source_block.get("by_scope") or {}).items():
            hit = cell.get("hit_rate")
            if hit is not None and cell.get("picks", 0) >= 30 and hit < 0.5:
                items.append({
                    "kind": "pick_accuracy_below_floor",
                    "target": f"{source_block.get('source')}::{scope}",
                    "severity": 5.0 * (0.5 - float(hit)),
                    "evidence": dict(cell),
                    "closed_loops": ["fused_calibration_shadow"],
                    "owner": "machine",
                    "next": "calibration shadow measures the correction; if"
                            " the shadow also fails, this cell is a model gap",
                })

    # 7) USE sidecar (Wave-22): where the simulation partner stands -- how
    # much training tape it has accrued toward its first recursive tune, and
    # whether the predictions artifact is flowing.
    use_predictions = _load(rd / "use_predictions.json")
    try:
        with (rd / "use_outcomes.jsonl").open(encoding="utf-8") as fh:
            tape = sum(1 for _ in fh)
    except OSError:
        tape = 0
    if use_predictions or tape:
        status = use_predictions.get("status")
        items.append({
            "kind": "use_sidecar_status",
            "target": "universal-sports-engine",
            "severity": 1.0 if status == "ENGINE_ABSENT" else 0.3,
            "evidence": {"predictions_status": status,
                         "outcomes_on_tape": tape,
                         "tune_gate": 300},
            "closed_loops": ["use_recursive_tuning"],
            "owner": "operator" if status == "ENGINE_ABSENT" else "machine",
            "next": ("sidecar checkout missing -- restore it or set"
                     " DUMMY_USE_ENGINE_PATH" if status == "ENGINE_ABSENT"
                     else "USE's own recursive tuner fires at >=300 taped"
                          " outcomes; champions promote by its preregistered"
                          " gates"),
        })

    # 8) vNext shadow runtime (Wave-26): episode-evidence accrual toward the
    # six open sovereign-forecasting claims.
    vnext = _load(rd / "vnext_shadow_status.json")
    if vnext:
        errors = vnext.get("errors") or []
        items.append({
            "kind": "vnext_shadow_status",
            "target": "sovereign-forecasting",
            "severity": 2.0 if errors else 0.3,
            "evidence": {"episodes_on_ledger": vnext.get("episodes_on_ledger"),
                         "pending": vnext.get("pending"),
                         "errors": errors[:3]},
            "closed_loops": ["vnext_shadow_episodes"],
            "owner": "machine" if not errors else "operator",
            "next": ("episode errors need triage" if errors else
                     "episodes accrue toward the six open empirical claims;"
                     " promotion review stays human-only"),
        })

    items.sort(key=lambda item: -float(item.get("severity") or 0.0))
    counts: dict[str, int] = {}
    for item in items:
        counts[item["kind"]] = counts.get(item["kind"], 0) + 1

    generated_at = str(now_iso) if now_iso else datetime.now(timezone.utc).isoformat()
    hpath = Path(history_path) if history_path is not None else Path(rd) / HISTORY_NAME
    history, row = annotate_history(items, read_last_history_row(hpath),
                                    generated_at)
    dead_loops = [item["target"] for item in writer_items + step_items]
    measurement_health = {
        "measurement_trusted": not dead_loops,
        "dead_loops": dead_loops,
        "failed_writers": [item["target"] for item in writer_items],
        "failed_chain_steps": [item["target"] for item in step_items],
        "chain_status_source": chain_source,
        "chain_ran_at": chain_block.get("ran_at"),
        "chain_ok": chain_block.get("ok")
        if isinstance(chain_block.get("ok"), bool) else None,
        "writer_failures_artifact_present": bool(
            (rd / WRITER_FAILURES_NAME).exists()),
    }
    row["measurement_trusted"] = measurement_health["measurement_trusted"]
    row["dead_loops"] = dead_loops

    closed_loops_active = []
    if dead_loops:
        # The audit found this list naming loops that were in fact crashed.
        # It is a DECLARED roster, so say so out loud when a loop is dead.
        closed_loops_active.append(
            f"!! MEASUREMENT DEGRADED: {len(dead_loops)} dead loop(s)"
            f" ({', '.join(dead_loops[:6])}) -- entries below are declared,"
            " not verified")
    closed_loops_active.extend([
            "trust_learning (per-scope, contested-only)",
            "validated_calibration_maps (holdout-gated, nightly)",
            "fused_calibration_shadow (::cal, self-activating)",
            "fusion_floor (significantly-negative scopes excluded)",
            "performance_quarantine (contraction-safe cohort repair)",
            "promotion_ladder (auto promote/escalate/demote, dossiers kept)",
            "tuner_auto_promote (step-capped runtime overrides)",
            "strategy_miner (FDR-controlled rule mining, nightly)",
            "live_poller + burst_repricing (event-driven)",
            "use_sidecar (strengths -> simulation -> outcomes; USE's own"
            " champion governance tunes on our settled games)",
            "vnext_shadow_episodes (organism forecasts graded on verified"
            " settlements; claims gates open until proven)",
    ])

    return {
        "report_name": "SELF_IMPROVEMENT_PLAN",
        "schema_version": PLAN_SCHEMA_VERSION,
        "generated_at": generated_at,
        "counts": counts,
        "items": items[:100],
        "items_total": len(items),
        "history": history,
        "measurement_health": measurement_health,
        "closed_loops_active": closed_loops_active,
        HISTORY_ROW_KEY: row,
    }


def write_plan(plan: dict[str, Any], path: Path | None = None, *,
               history_path: Path | None = None) -> Path:
    """Write the plan artifact, then append its snapshot row to the history.

    The row rides in on ``HISTORY_ROW_KEY`` and is popped before serialization
    so it never lands in the dashboard payload. The plan artifact is written
    FIRST and the history append is fail-soft: a locked or unwritable tape
    costs the audit trail one row, never the plan itself.
    """
    target = Path(path) if path is not None else PLAN_PATH
    row = plan.pop(HISTORY_ROW_KEY, None) if isinstance(plan, dict) else None
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(plan, indent=2, sort_keys=True),
                         encoding="utf-8")
    temporary.replace(target)

    if isinstance(row, dict):
        chain = plan.get("chain") if isinstance(plan, dict) else None
        if isinstance(chain, dict):
            # The chain block is attached after assemble_plan(), so record
            # this run's real outcome on the row rather than the prior run's.
            row["chain_ok"] = chain.get("ok")
            row["chain_failed_steps"] = chain.get("failed_steps")
        append_history_row(row, history_path if history_path is not None
                           else target.parent / HISTORY_NAME)
    return target
