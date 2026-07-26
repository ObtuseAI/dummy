"""Run Dummy's bounded real-ledger autoresearch and forward-paper cycle.

Unattended-execution contract (2026-07-24 audit, s6 -- the lab had an
installer but no scheduled task, and its artifacts sat 9 days stale):

* READ-ONLY over the ledger. ``connect_ledger_readonly`` opens ``ledger.db``
  with ``mode=ro`` + ``PRAGMA query_only=ON``; this process never writes it.
* NO NETWORK, NO SPEND. Nothing under ``dummy/autoresearch`` performs HTTP or
  model calls -- the whole cycle is local SQLite reads plus CPU.
* BOUNDED RUNTIME. ``--max-seconds`` is a cooperative deadline: cohorts not
  reached are marked deferred rather than dropped or faked. The scheduler's
  ExecutionTimeLimit remains the hard backstop.
* BOUNDED DISK. The append-only ignition-trial ledger is tail-capped by
  ``--max-trial-lines``; any truncation is disclosed in the status artifact.
* FAIL-SOFT. Every failure (missing ledger, insufficient evidence, unexpected
  error) writes a status artifact and exits without a traceback; a genuine
  error exits non-zero so the scheduler's Last Result surfaces it.
* OBSERVABLE. ``runtime/autonomy/autoresearch_status.json`` carries
  ``generated_at`` / ``last_success_at`` so the watchdog can see staleness.

It proposes and shadow-evaluates only: no orders, no execution authority, no
automatic promotion.
"""

from __future__ import annotations

import argparse
import os
import tempfile
import time
import traceback
from datetime import datetime, timezone
import json
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dummy.autoresearch.campaign import write_campaign_report  # noqa: E402
from dummy.autoresearch.forward_paper import (  # noqa: E402
    build_forward_registry,
    grade_forward_observations,
    issue_forward_observations,
    write_forward_artifact,
)
from dummy.autoresearch.ledger_pipeline import load_ledger_evidence  # noqa: E402
from dummy.autoresearch.multi_cohort import (  # noqa: E402
    run_multi_cohort_campaigns,
)
from dummy.autoresearch.operational_ignition import (  # noqa: E402
    operational_ignition_report,
    record_campaign_ignition_trial,
    write_ignition_report,
)
from dummy.autoresearch.research_coordinator import (  # noqa: E402
    consume_intelligence_queue,
)
from dummy.autoresearch.research_plugins import (  # noqa: E402
    intelligence_evidence_snapshot,
)
from dummy.genome import ForecastGenome  # noqa: E402
from dummy.intelligence_lab import run_intelligence_research_cycle  # noqa: E402


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return value if isinstance(value, dict) else None


class InsufficientEvidence(RuntimeError):
    """Not enough settled evidence for a campaign -- a normal, non-error state."""


DEFAULT_OUTPUT_DIR = ROOT / "runtime" / "autonomy" / "autoresearch"
STATUS_FILENAME = "autoresearch_status.json"
DEFAULT_MAX_SECONDS = 600.0
DEFAULT_MAX_TRIAL_LINES = 50_000


def default_status_path(output_dir: Path) -> Path:
    """Status artifact sits beside the output dir, never at a fixed location.

    For the production output dir this resolves to
    ``runtime/autonomy/autoresearch_status.json`` (flat, where the watchdog
    reads task artifacts). For a test or ad-hoc ``--output-dir`` it stays in
    that tree, so an offline run can never stamp the live runtime status.
    """
    return output_dir.parent / STATUS_FILENAME


def _write_status(path: Path, status: dict[str, object]) -> None:
    """Atomically write the status artifact; never raise into the caller."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(status, stream, indent=2, sort_keys=True, default=str)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    except OSError as exc:  # pragma: no cover - disk-level failure
        print(f"status write failed: {exc}", file=sys.stderr)


def _previous_success(path: Path) -> str | None:
    previous = _read_json(path)
    if not previous:
        return None
    value = previous.get("last_success_at")
    return str(value) if value else None


def cap_trial_ledger(path: Path, max_lines: int) -> dict[str, object]:
    """Tail-cap the append-only ignition-trial ledger.

    One run appends one line per completed cohort campaign, so an unattended
    schedule grows this file forever. The newest ``max_lines`` trials are kept
    (the ignition report reads recent history), the drop count is reported so
    the truncation is never silent, and a locked or unreadable file is left
    alone.
    """
    result: dict[str, object] = {
        "path": str(path),
        "max_lines": max_lines,
        "truncated": False,
        "lines_dropped": 0,
    }
    if max_lines <= 0 or not path.exists():
        return result
    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError:
        result["error"] = "unreadable"
        return result
    if len(lines) <= max_lines:
        result["lines_retained"] = len(lines)
        return result
    keep = lines[-max_lines:]
    try:
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.writelines(keep)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    except OSError:
        result["error"] = "rotation_failed_left_intact"
        return result
    result["truncated"] = True
    result["lines_dropped"] = len(lines) - len(keep)
    result["lines_retained"] = len(keep)
    return result


def _parse_time(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("--issued-at must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def run_cycle(
    *,
    ledger_path: Path,
    output_dir: Path,
    ticker_prefix: str,
    issued_at: datetime,
    deadline: Callable[[], bool] | None = None,
) -> dict[str, object]:
    rows = load_ledger_evidence(ledger_path)
    multi = run_multi_cohort_campaigns(
        rows=rows,
        output_dir=output_dir,
        deadline=deadline,
    )
    campaign_path = output_dir / "campaign_report.json"
    registry_path = output_dir / "forward_registry.json"
    forward_path = output_dir / "forward_report.json"
    trial_path = output_dir / "ignition_trials.jsonl"
    ignition_path = output_dir / "ignition_report.json"
    forward_cohorts: list[dict[str, object]] = []
    trials = []
    primary: dict[str, object] | None = None
    normalized_prefix = ticker_prefix.upper()
    for entry in multi["campaigns"]:
        campaign = entry["campaign"]
        base = ForecastGenome.from_dict(entry["base_genome"])
        cohort_dir = Path(entry["cohort_output_dir"])
        cohort_registry_path = cohort_dir / "forward_registry.json"
        observation_path = cohort_dir / "forward_observations.jsonl"
        cohort_forward_path = cohort_dir / "forward_report.json"
        registry = build_forward_registry(
            campaign,
            base_genome=base,
            ticker_prefix=str(entry["ticker_prefix"]),
            existing=_read_json(cohort_registry_path),
        )
        write_forward_artifact(registry, cohort_registry_path)
        issuance = issue_forward_observations(
            registry,
            ledger_path=ledger_path,
            observation_ledger_path=observation_path,
            issued_at=issued_at,
        )
        forward = grade_forward_observations(
            registry,
            ledger_path=ledger_path,
            observation_ledger_path=observation_path,
        )
        forward["latest_issuance"] = issuance
        write_forward_artifact(forward, cohort_forward_path)
        trial = record_campaign_ignition_trial(
            campaign,
            trial_ledger_path=trial_path,
        )
        trials.append(trial)
        forward_cohorts.append(
            {
                "scope": entry["scope"],
                "registry_id": registry["registry_id"],
                "new_observations": issuance["new_observations"],
                "forward_settlements": forward["forward_paper_candidate_settlements"],
                "ready_for_human_promotion_review": forward[
                    "ready_for_human_promotion_review"
                ],
                "orders_placed": False,
                "execution_authority": False,
            }
        )
        if primary is None and (
            normalized_prefix.startswith(str(entry["ticker_prefix"]).upper())
            or str(entry["ticker_prefix"]).upper().startswith(normalized_prefix)
        ):
            if "15M" not in normalized_prefix or str(entry["scope"]).endswith("|15m"):
                primary = {
                    "campaign": campaign,
                    "registry": registry,
                    "forward": forward,
                    "issuance": issuance,
                    "trial": trial,
                    "scope": entry["scope"],
                }
    if primary is None and multi["campaigns"]:
        entry = multi["campaigns"][0]
        cohort_dir = Path(entry["cohort_output_dir"])
        primary = {
            "campaign": entry["campaign"],
            "registry": _read_json(cohort_dir / "forward_registry.json"),
            "forward": _read_json(cohort_dir / "forward_report.json"),
            "issuance": {},
            "trial": trials[0],
            "scope": entry["scope"],
        }
    if primary is None:
        raise InsufficientEvidence(
            "no exact cohort has enough evidence for autoresearch"
        )

    write_campaign_report(primary["campaign"], campaign_path)
    write_forward_artifact(primary["registry"], registry_path)
    write_forward_artifact(primary["forward"], forward_path)
    aggregate_forward = {
        "schema_version": 1,
        "exact_cohorts": forward_cohorts,
        "forward_paper_candidate_settlements": sum(
            int(item["forward_settlements"]) for item in forward_cohorts
        ),
        "event_clusters": 0,
        "verified_settled_fills": 0,
        "ready_for_human_promotion_review": False,
        "orders_placed": False,
        "execution_authority": False,
    }
    write_forward_artifact(
        aggregate_forward,
        output_dir / "multi_forward_report.json",
    )
    ignition = operational_ignition_report(
        trial_ledger_path=trial_path,
        forward_report=aggregate_forward,
    )
    write_ignition_report(ignition, ignition_path)
    intelligence = run_intelligence_research_cycle(
        multi_cohort_report=multi,
        forward_report=aggregate_forward,
        ignition_report=ignition,
        output_dir=output_dir / "intelligence_lab",
        observed_at=issued_at,
    )
    control_dir = output_dir / "intelligence_lab"
    control_report_path = control_dir / "research_control_plane_report.json"
    try:
        control_report = consume_intelligence_queue(
            queue_path=control_dir / "research_queue.json",
            journal_path=control_dir / "research_journal.sqlite3",
            report_path=control_report_path,
            evidence=intelligence_evidence_snapshot(
                multi_cohort_report=multi,
                forward_report=aggregate_forward,
                ignition_report=ignition,
                captured_at=issued_at,
            ),
            generated_at=issued_at,
        )
    except Exception as exc:  # noqa: BLE001 - forecast cycle remains fail-soft
        control_report = {
            "schema_version": 1,
            "generated_at": issued_at.isoformat(),
            "status": "ERROR",
            "error_type": type(exc).__name__,
            "negative_controls_passed": False,
            "source_edits_applied": False,
            "runtime_application": False,
            "automatic_promotion": False,
            "execution_authority": False,
            "capital_authority": False,
            "orders_placed": False,
        }
        _write_status(control_report_path, control_report)
    campaign = primary["campaign"]
    issuance = primary["issuance"]
    forward = primary["forward"]
    trial = primary["trial"]
    return {
        "campaign_id": campaign["campaign_id"],
        "scope": primary["scope"],
        "evidence_rows": len(rows),
        "private_trials": campaign["genuine_private_candidate_trials"],
        "private_survivors": campaign["private_survivors"],
        "external_survivors": campaign["external_survivors"],
        "forward_observations_issued": int(issuance.get("new_observations", 0)),
        "forward_settlements": forward["forward_paper_candidate_settlements"],
        "ignition_trial_id": trial.trial_id,
        "highest_supported_level": ignition[
            "highest_supported_recursive_improvement_level"
        ],
        "intelligence_research": {
            "report_id": intelligence["report_id"],
            "opportunities": intelligence["cognitive_state"]["opportunities"],
            "proposed_experiments": intelligence["cognitive_state"][
                "proposed_experiments"
            ],
            "validated_theories": (
                intelligence["cognitive_state"]["provisional_theories"]
                + intelligence["cognitive_state"]["general_laws"]
            ),
            "highest_supported_level": intelligence["highest_supported_level"],
            "control_plane_status": control_report["status"],
            "control_plane_runs_created": int(
                control_report.get("runs_created") or 0
            ),
            "control_plane_runs_reused": int(
                control_report.get("runs_reused") or 0
            ),
        },
        "orders_placed": False,
        "execution_authority": False,
        "multi_cohort": {
            "discovered": multi["discovered_cohorts"],
            "campaigns_completed": multi["campaigns_completed"],
            "forward_cohorts": len(forward_cohorts),
            "run_deadline_reached": bool(multi.get("run_deadline_reached")),
            "cohorts_deferred_by_deadline": int(
                multi.get("cohorts_deferred_by_deadline") or 0
            ),
        },
        "outputs": {
            "campaign": str(campaign_path),
            "forward_registry": str(registry_path),
            "forward_report": str(forward_path),
            "ignition_report": str(ignition_path),
            "multi_cohort_report": str(output_dir / "multi_cohort_report.json"),
            "multi_forward_report": str(output_dir / "multi_forward_report.json"),
            "intelligence_observatory": str(
                output_dir / "intelligence_lab" / "observatory_report.json"
            ),
            "scientific_memory": str(
                output_dir / "intelligence_lab" / "scientific_memory.jsonl"
            ),
            "intelligence_research_queue": str(
                output_dir / "intelligence_lab" / "research_queue.json"
            ),
            "research_control_plane": str(control_report_path),
            "research_journal": str(
                output_dir / "intelligence_lab" / "research_journal.sqlite3"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ledger",
        type=Path,
        default=ROOT / "runtime" / "autonomy" / "ledger.db",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument("--ticker-prefix", default="KXBTC15M")
    parser.add_argument("--issued-at")
    parser.add_argument(
        "--status-path",
        type=Path,
        default=None,
        help=(
            "status artifact the watchdog reads for staleness "
            "(default: <output-dir>/../autoresearch_status.json)"
        ),
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=DEFAULT_MAX_SECONDS,
        help="cooperative run deadline; 0 disables (scheduler limit still applies)",
    )
    parser.add_argument(
        "--max-trial-lines",
        type=int,
        default=DEFAULT_MAX_TRIAL_LINES,
        help="tail cap for the append-only ignition trial ledger; 0 disables",
    )
    args = parser.parse_args()
    if args.status_path is None:
        args.status_path = default_status_path(args.output_dir)

    started = time.monotonic()
    started_at = datetime.now(timezone.utc)
    status: dict[str, object] = {
        "schema_version": 1,
        "task": "DummyAutoresearch",
        "started_at": started_at.isoformat(),
        "generated_at": started_at.isoformat(),
        "last_success_at": _previous_success(args.status_path),
        "status": "RUNNING",
        "ledger_access": "read-only",
        "network_calls": False,
        "orders_placed": False,
        "execution_authority": False,
        "capital_authority": False,
        "automatic_promotion": False,
        "max_seconds": args.max_seconds,
    }
    _write_status(args.status_path, status)

    def _deadline() -> bool:
        if args.max_seconds <= 0:
            return False
        return (time.monotonic() - started) >= args.max_seconds

    try:
        if not args.ledger.exists():
            raise InsufficientEvidence(f"ledger not found: {args.ledger}")
        if _deadline():
            raise InsufficientEvidence("run deadline reached before cycle started")
        summary = run_cycle(
            ledger_path=args.ledger,
            output_dir=args.output_dir,
            ticker_prefix=args.ticker_prefix,
            issued_at=_parse_time(args.issued_at),
            deadline=_deadline,
        )
    except InsufficientEvidence as exc:
        # Normal state, not a failure: nothing to research yet -- or the run
        # deadline arrived before any cohort started.
        finished = datetime.now(timezone.utc)
        status.update({
            "status": (
                "DEFERRED_RUN_DEADLINE"
                if _deadline()
                else "SKIPPED_INSUFFICIENT_EVIDENCE"
            ),
            "generated_at": finished.isoformat(),
            "duration_seconds": round(time.monotonic() - started, 3),
            "detail": str(exc),
        })
        _write_status(args.status_path, status)
        print(json.dumps({"status": status["status"], "detail": str(exc)}))
        # Neither state is an error: exit 0 so the scheduler's Last Result
        # stays clean and only real failures raise the watchdog.
        return 0
    except Exception as exc:  # fail-soft: an unattended run must not hang open
        finished = datetime.now(timezone.utc)
        status.update({
            "status": "ERROR",
            "generated_at": finished.isoformat(),
            "duration_seconds": round(time.monotonic() - started, 3),
            "error_type": type(exc).__name__,
            "error": str(exc)[:2000],
            "traceback_tail": "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            )[-2000:],
        })
        _write_status(args.status_path, status)
        print(json.dumps({"status": "ERROR", "error": str(exc)[:500]}), file=sys.stderr)
        return 1

    rotation = cap_trial_ledger(
        args.output_dir / "ignition_trials.jsonl", args.max_trial_lines,
    )
    finished = datetime.now(timezone.utc)
    status.update({
        "status": "OK",
        "generated_at": finished.isoformat(),
        "last_success_at": finished.isoformat(),
        "duration_seconds": round(time.monotonic() - started, 3),
        "evidence_rows": summary.get("evidence_rows"),
        "multi_cohort": summary.get("multi_cohort"),
        "forward_observations_issued": summary.get("forward_observations_issued"),
        "forward_settlements": summary.get("forward_settlements"),
        "highest_supported_level": summary.get("highest_supported_level"),
        "trial_ledger_rotation": rotation,
        "output_dir": str(args.output_dir),
    })
    _write_status(args.status_path, status)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
