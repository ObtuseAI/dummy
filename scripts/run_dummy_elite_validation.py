#!/usr/bin/env python
"""Print Dummy's fail-closed readiness axes without mutating runtime state.

This command is deliberately a reader, not a report writer.  It never imports
the broker, resolves credentials, evaluates an order, writes an artifact, or
turns evidence into execution authority.  Missing, malformed, stale, or
future-dated evidence blocks only the axis that depends on it.

The retired paper/shadow canary embedded in dashboard snapshots is not an input.
Only explicit forward canary and scale-readiness artifacts can satisfy those
axes, and even a fully passing report means "ready for separate operator
authority review" -- never permission to submit an order.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = Path("runtime/autonomy")
AUTORESEARCH_DIR = RUNTIME_DIR / "autoresearch"

OPS_MAX_AGE = timedelta(minutes=20)
RESEARCH_MAX_AGE = timedelta(hours=2)
OBSERVATORY_MAX_AGE = timedelta(hours=26)
LAUNCH_EVIDENCE_MAX_AGE = timedelta(hours=24)
MAX_FUTURE_SKEW = timedelta(minutes=5)

MIN_FORWARD_CLUSTERS = 40
MIN_GRADING_COVERAGE = 0.95
MIN_GREEN_DAYS = 14


@dataclass(frozen=True)
class JsonArtifact:
    path: Path
    value: dict[str, Any] | None
    error: str | None


def _load_json(root: Path, relative: Path) -> JsonArtifact:
    path = root / relative
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return JsonArtifact(relative, None, "missing")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return JsonArtifact(relative, None, f"unreadable:{type(exc).__name__}")
    if not isinstance(value, dict):
        return JsonArtifact(relative, None, "not_an_object")
    return JsonArtifact(relative, value, None)


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _freshness_blocker(
    artifact: JsonArtifact,
    *,
    timestamp_fields: tuple[str, ...],
    max_age: timedelta,
    now: datetime,
) -> tuple[str | None, str | None]:
    if artifact.error:
        return f"{artifact.path.as_posix()}:{artifact.error}", None
    assert artifact.value is not None
    for field in timestamp_fields:
        timestamp = _parse_utc(artifact.value.get(field))
        if timestamp is None:
            continue
        age = now - timestamp
        if age < -MAX_FUTURE_SKEW:
            return f"{artifact.path.as_posix()}:{field}:future_dated", timestamp.isoformat()
        if age > max_age:
            return f"{artifact.path.as_posix()}:{field}:stale", timestamp.isoformat()
        return None, timestamp.isoformat()
    return (
        f"{artifact.path.as_posix()}:missing_timezone_aware_timestamp",
        None,
    )


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _object_field(
    payload: dict[str, Any],
    key: str,
    *,
    label: str,
    blockers: list[str],
) -> dict[str, Any]:
    value = payload.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        blockers.append(f"{label}:{key}_not_an_object")
        return {}
    return value


def _string_list_field(
    payload: dict[str, Any],
    key: str,
    *,
    label: str,
    blockers: list[str],
) -> list[str]:
    value = payload.get(key)
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        blockers.append(f"{label}:{key}_not_a_string_list")
        return []
    return value


def _axis(
    *,
    blockers: list[str],
    evidence: dict[str, Any],
    artifact_paths: list[Path],
) -> dict[str, Any]:
    return {
        "status": "PASS" if not blockers else "BLOCKED",
        "ready": not blockers,
        "blockers": sorted(set(blockers)),
        "artifacts": [path.as_posix() for path in artifact_paths],
        "evidence": evidence,
        "execution_authority": False,
        "capital_authority": False,
    }


def _require_false(
    payload: dict[str, Any],
    *,
    keys: tuple[str, ...],
    label: str,
    blockers: list[str],
) -> None:
    for key in keys:
        if payload.get(key) is not False:
            blockers.append(f"{label}:{key}_must_be_false")


def _operations_axis(root: Path, now: datetime) -> dict[str, Any]:
    heartbeat_path = RUNTIME_DIR / "heartbeat.json"
    watchdog_path = RUNTIME_DIR / "watchdog_status.json"
    heartbeat = _load_json(root, heartbeat_path)
    watchdog = _load_json(root, watchdog_path)
    blockers: list[str] = []
    evidence: dict[str, Any] = {}

    freshness, stamp = _freshness_blocker(
        heartbeat,
        timestamp_fields=("last_cycle_at",),
        max_age=OPS_MAX_AGE,
        now=now,
    )
    if freshness:
        blockers.append(freshness)
    if heartbeat.value is not None:
        last_success = _parse_utc(heartbeat.value.get("last_success_at"))
        if last_success is None:
            blockers.append(f"{heartbeat_path.as_posix()}:last_success_at:invalid")
        elif now - last_success > OPS_MAX_AGE:
            blockers.append(f"{heartbeat_path.as_posix()}:last_success_at:stale")
        if heartbeat.value.get("alive") is not True:
            blockers.append(f"{heartbeat_path.as_posix()}:alive_not_true")
        last_status = str(heartbeat.value.get("last_status") or "")
        if not last_status or last_status.startswith(("CYCLE_ERROR", "HALTED")):
            blockers.append(f"{heartbeat_path.as_posix()}:last_status_not_healthy")
        evidence.update(
            {
                "heartbeat_at": stamp,
                "last_success_at": (
                    last_success.isoformat() if last_success is not None else None
                ),
                "last_status": last_status or None,
            }
        )

    freshness, stamp = _freshness_blocker(
        watchdog,
        timestamp_fields=("generated_at",),
        max_age=OPS_MAX_AGE,
        now=now,
    )
    if freshness:
        blockers.append(freshness)
    if watchdog.value is not None:
        if watchdog.value.get("healthy") is not True:
            blockers.append(f"{watchdog_path.as_posix()}:healthy_not_true")
        evidence.update(
            {
                "watchdog_generated_at": stamp,
                "stale_tasks": _string_list_field(
                    watchdog.value,
                    "stale_tasks",
                    label=watchdog_path.as_posix(),
                    blockers=blockers,
                ),
                "uncovered_failing_tasks": _string_list_field(
                    watchdog.value,
                    "uncovered_failing_tasks",
                    label=watchdog_path.as_posix(),
                    blockers=blockers,
                ),
                "kill_file_present": watchdog.value.get("kill_file_present"),
                "ledger_over_threshold": watchdog.value.get(
                    "ledger_over_threshold"
                ),
                "disk_below_floor": watchdog.value.get("disk_below_floor"),
            }
        )

    return _axis(
        blockers=blockers,
        evidence=evidence,
        artifact_paths=[heartbeat_path, watchdog_path],
    )


def _research_axis(root: Path, now: datetime) -> dict[str, Any]:
    status_path = RUNTIME_DIR / "autoresearch_status.json"
    observatory_path = AUTORESEARCH_DIR / "intelligence_lab" / "observatory_report.json"
    control_path = (
        AUTORESEARCH_DIR / "intelligence_lab" / "research_control_plane_report.json"
    )
    status = _load_json(root, status_path)
    observatory = _load_json(root, observatory_path)
    control = _load_json(root, control_path)
    blockers: list[str] = []
    evidence: dict[str, Any] = {}

    freshness, stamp = _freshness_blocker(
        status,
        timestamp_fields=("last_success_at",),
        max_age=RESEARCH_MAX_AGE,
        now=now,
    )
    if freshness:
        blockers.append(freshness)
    if status.value is not None:
        if status.value.get("status") != "OK":
            blockers.append(f"{status_path.as_posix()}:status_not_ok")
        _require_false(
            status.value,
            keys=(
                "orders_placed",
                "execution_authority",
                "capital_authority",
                "automatic_promotion",
            ),
            label=status_path.as_posix(),
            blockers=blockers,
        )
        evidence.update(
            {
                "autoresearch_last_success_at": stamp,
                "highest_supported_level": status.value.get(
                    "highest_supported_level"
                ),
                "forward_settlements": status.value.get("forward_settlements"),
            }
        )

    freshness, stamp = _freshness_blocker(
        observatory,
        timestamp_fields=("cycle_observed_at",),
        max_age=OBSERVATORY_MAX_AGE,
        now=now,
    )
    if freshness:
        blockers.append(freshness)
    if observatory.value is not None:
        _require_false(
            observatory.value,
            keys=(
                "orders_placed",
                "execution_authority",
                "capital_authority",
                "automatic_positive_promotion",
            ),
            label=observatory_path.as_posix(),
            blockers=blockers,
        )
        evidence.update(
            {
                "observatory_at": stamp,
                "observatory_highest_supported_level": observatory.value.get(
                    "highest_supported_level"
                ),
                "claims": _object_field(
                    observatory.value,
                    "claims",
                    label=observatory_path.as_posix(),
                    blockers=blockers,
                ),
            }
        )

    freshness, stamp = _freshness_blocker(
        control,
        timestamp_fields=("generated_at",),
        max_age=RESEARCH_MAX_AGE,
        now=now,
    )
    if freshness:
        blockers.append(freshness)
    if control.value is not None:
        if control.value.get("status") != "COMPLETE":
            blockers.append(f"{control_path.as_posix()}:status_not_complete")
        if control.value.get("negative_controls_passed") is not True:
            blockers.append(
                f"{control_path.as_posix()}:negative_controls_not_passed"
            )
        _require_false(
            control.value,
            keys=(
                "execution_authority",
                "capital_authority",
                "automatic_promotion",
                "source_edits_applied",
                "orders_placed",
            ),
            label=control_path.as_posix(),
            blockers=blockers,
        )
        evidence.update(
            {
                "control_plane_generated_at": stamp,
                "queue_id": control.value.get("queue_id"),
                "protocols_seen": control.value.get("protocols_seen"),
                "runs_created": control.value.get("runs_created"),
                "runs_reused": control.value.get("runs_reused"),
                "verdict_counts": _object_field(
                    control.value,
                    "verdict_counts",
                    label=control_path.as_posix(),
                    blockers=blockers,
                ),
                "journal_tip": control.value.get("journal_tip"),
            }
        )

    return _axis(
        blockers=blockers,
        evidence=evidence,
        artifact_paths=[status_path, observatory_path, control_path],
    )


def _forward_canary_axis(root: Path, now: datetime) -> dict[str, Any]:
    path = RUNTIME_DIR / "live_canary_readiness.json"
    artifact = _load_json(root, path)
    blockers: list[str] = []
    evidence: dict[str, Any] = {}
    freshness, stamp = _freshness_blocker(
        artifact,
        timestamp_fields=("generated_at",),
        max_age=LAUNCH_EVIDENCE_MAX_AGE,
        now=now,
    )
    if freshness:
        blockers.append(freshness)
    if artifact.value is not None:
        payload = artifact.value
        if payload.get("schema_version") != 1:
            blockers.append(f"{path.as_posix()}:unsupported_schema")
        if payload.get("status") != "PASS" or payload.get("ready") is not True:
            blockers.append(f"{path.as_posix()}:not_ready")
        _require_false(
            payload,
            keys=("execution_authority", "capital_authority"),
            label=path.as_posix(),
            blockers=blockers,
        )
        raw_evidence = payload.get("evidence")
        if not isinstance(raw_evidence, dict):
            blockers.append(f"{path.as_posix()}:evidence_not_an_object")
            raw_evidence = {}
        clusters = raw_evidence.get("independent_realized_post_fee_clusters")
        coverage = _finite_number(raw_evidence.get("grading_coverage"))
        ci_lower = _finite_number(raw_evidence.get("post_fee_edge_ci_lower"))
        if isinstance(clusters, bool) or not isinstance(clusters, int):
            blockers.append(f"{path.as_posix()}:clusters_invalid")
        elif clusters < MIN_FORWARD_CLUSTERS:
            blockers.append(f"{path.as_posix()}:clusters_below_minimum")
        if coverage is None or coverage < MIN_GRADING_COVERAGE:
            blockers.append(f"{path.as_posix()}:grading_coverage_below_minimum")
        if ci_lower is None or ci_lower <= 0:
            blockers.append(f"{path.as_posix()}:post_fee_edge_ci_not_positive")
        if raw_evidence.get("scope_bounded") is not True:
            blockers.append(f"{path.as_posix()}:scope_not_bounded")
        evidence = {
            "generated_at": stamp,
            "independent_realized_post_fee_clusters": clusters,
            "grading_coverage": coverage,
            "post_fee_edge_ci_lower": ci_lower,
            "scope_bounded": raw_evidence.get("scope_bounded"),
        }

    axis = _axis(blockers=blockers, evidence=evidence, artifact_paths=[path])
    axis["paper_or_shadow_canary_can_substitute"] = False
    return axis


def _scale_axis(
    root: Path,
    now: datetime,
    *,
    canary: dict[str, Any],
) -> dict[str, Any]:
    path = RUNTIME_DIR / "live_scale_readiness.json"
    artifact = _load_json(root, path)
    blockers: list[str] = []
    evidence: dict[str, Any] = {}
    if canary.get("ready") is not True:
        blockers.append("forward_canary_not_ready")
    freshness, stamp = _freshness_blocker(
        artifact,
        timestamp_fields=("generated_at",),
        max_age=LAUNCH_EVIDENCE_MAX_AGE,
        now=now,
    )
    if freshness:
        blockers.append(freshness)
    if artifact.value is not None:
        payload = artifact.value
        if payload.get("schema_version") != 1:
            blockers.append(f"{path.as_posix()}:unsupported_schema")
        if payload.get("status") != "PASS" or payload.get("ready") is not True:
            blockers.append(f"{path.as_posix()}:not_ready")
        _require_false(
            payload,
            keys=("execution_authority", "capital_authority"),
            label=path.as_posix(),
            blockers=blockers,
        )
        raw_evidence = payload.get("evidence")
        if not isinstance(raw_evidence, dict):
            blockers.append(f"{path.as_posix()}:evidence_not_an_object")
            raw_evidence = {}
        green_days = _finite_number(raw_evidence.get("operational_green_days"))
        if green_days is None or green_days < MIN_GREEN_DAYS:
            blockers.append(f"{path.as_posix()}:operational_soak_too_short")
        required_true = (
            "restore_drill_verified",
            "scheduler_soak_passed",
            "maker_taker_policy_decided",
            "verified_shadow_fills",
            "money_gate_mutation_tests_passed",
            "operator_demo_place_cancel_verified",
            "kill_reconciliation_verified",
        )
        for key in required_true:
            if raw_evidence.get(key) is not True:
                blockers.append(f"{path.as_posix()}:{key}_not_true")
        evidence = {
            "generated_at": stamp,
            "operational_green_days": green_days,
            **{key: raw_evidence.get(key) for key in required_true},
        }

    return _axis(blockers=blockers, evidence=evidence, artifact_paths=[path])


def _authority_summary(root: Path) -> tuple[dict[str, Any], list[str]]:
    path = Path("configs/live_submit.json")
    artifact = _load_json(root, path)
    blockers: list[str] = []
    if artifact.error:
        state = "UNKNOWN_BLOCKED"
        blockers.append(f"{path.as_posix()}:{artifact.error}")
    elif artifact.value is not None and artifact.value.get("enabled") is False:
        state = "DEFAULT_DISABLED"
    else:
        state = "SEPARATE_AUTHORITY_EVALUATION_REQUIRED"
        blockers.append(
            f"{path.as_posix()}:not_default_disabled_for_readiness_review"
        )
    return (
        {
            "state": state,
            "source": path.as_posix(),
            "execution_authority": False,
            "credentials_read": False,
            "broker_contacted": False,
        },
        blockers,
    )


def evaluate_readiness(
    root: Path = REPO_ROOT,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return the four-axis readiness report using only bounded file reads."""
    observed_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    operations = _operations_axis(root, observed_at)
    research = _research_axis(root, observed_at)
    canary = _forward_canary_axis(root, observed_at)
    scale = _scale_axis(root, observed_at, canary=canary)
    authority, authority_blockers = _authority_summary(root)
    axes = {
        "operations": operations,
        "research": research,
        "canary": canary,
        "scale": scale,
    }
    blockers = [
        f"{axis_name}:{blocker}"
        for axis_name, axis in axes.items()
        for blocker in axis["blockers"]
    ]
    blockers.extend(f"authority:{blocker}" for blocker in authority_blockers)
    ready = not blockers
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": observed_at.isoformat(),
        "mode": "READ_ONLY_VALIDATION",
        "status": (
            "READY_FOR_SEPARATE_OPERATOR_AUTHORITY_REVIEW"
            if ready
            else "BLOCKED"
        ),
        "ready_for_separate_operator_authority_review": ready,
        "axes": axes,
        "authority": authority,
        "blockers": sorted(set(blockers)),
        "execution_authority": False,
        "capital_authority": False,
        "orders_placed": False,
        "broker_contacted": False,
        "runtime_mutated": False,
    }


def _parse_now(value: str) -> datetime:
    parsed = _parse_utc(value)
    if parsed is None:
        raise argparse.ArgumentTypeError(
            "--now must be a timezone-aware ISO-8601 timestamp"
        )
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="repository root to inspect (default: this checkout)",
    )
    parser.add_argument(
        "--now",
        type=_parse_now,
        default=None,
        help="fixed timezone-aware clock for deterministic offline validation",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="print compact JSON instead of indented JSON",
    )
    args = parser.parse_args(argv)
    report = evaluate_readiness(args.root, now=args.now)
    print(
        json.dumps(
            report,
            indent=None if args.compact else 2,
            sort_keys=True,
            allow_nan=False,
        )
    )
    return 0 if report["ready_for_separate_operator_authority_review"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
