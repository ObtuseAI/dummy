"""Declarative, no-shell supervision for Dummy's one-shot operational jobs.

This module does not register or modify Windows scheduled tasks.  It is the
safe child boundary those tasks can eventually invoke one migration at a time:
fixed allowlisted entrypoints, one ownership field, per-job timeout/lock, exact
exit propagation, bounded logs, and an atomic result receipt.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from autonomy.proclock import acquire_lock, release_lock

REGISTRY_VERSION = 1
ALLOWED_ENTRYPOINTS = frozenset({
    "scripts/run_dummy_grading_worker.py",
    "scripts/run_dummy_ledger_retention.py",
    "scripts/run_dummy_signal_prune.py",
})
_DENIED_ARGUMENT_FRAGMENTS = (
    "operator_authority_pack",
    "configs/live_submit",
    "live_submit.json",
    "--submit",
    "--place-order",
    "--cancel-order",
    "--arm",
)
_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class JobRegistryError(ValueError):
    """The registry or requested job violates the supervisor contract."""


@dataclass(frozen=True)
class JobSpec:
    name: str
    argv: tuple[str, ...]
    cwd: str
    cadence: str
    timeout_seconds: float
    lock_group: str
    privilege: str
    ownership: str
    enabled: bool
    artifact_contract: tuple[str, ...] = ()


@dataclass(frozen=True)
class JobResult:
    name: str
    status: str
    exit_code: int
    started_at: str
    completed_at: str
    duration_seconds: float
    argv: tuple[str, ...]
    stdout_tail: str
    stderr_tail: str
    ownership: str
    execution_authority: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_spec(raw: Mapping[str, Any]) -> JobSpec:
    expected = {
        "name", "argv", "cwd", "cadence", "timeout_seconds", "lock_group",
        "privilege", "ownership", "enabled", "artifact_contract",
    }
    unknown = set(raw) - expected
    if unknown:
        raise JobRegistryError(f"unknown JobSpec fields: {sorted(unknown)}")
    name = str(raw.get("name", ""))
    lock_group = str(raw.get("lock_group", ""))
    if not _NAME.fullmatch(name) or not _NAME.fullmatch(lock_group):
        raise JobRegistryError("job name and lock_group must be safe identifiers")
    argv_raw = raw.get("argv")
    if not isinstance(argv_raw, list) or any(not isinstance(item, str) for item in argv_raw):
        raise JobRegistryError(f"{name}: argv must be a string list")
    argv = tuple(argv_raw)
    if len(argv) < 2 or argv[0] != "{python}":
        raise JobRegistryError(f"{name}: argv must start with {{python}} and an entrypoint")
    entrypoint = argv[1].replace("\\", "/")
    if entrypoint not in ALLOWED_ENTRYPOINTS:
        raise JobRegistryError(f"{name}: entrypoint is not allowlisted: {entrypoint}")
    joined = " ".join(argv).replace("\\", "/").casefold()
    if any(fragment in joined for fragment in _DENIED_ARGUMENT_FRAGMENTS):
        raise JobRegistryError(f"{name}: authority/order argument is forbidden")
    cwd = str(raw.get("cwd", ".")).replace("\\", "/")
    if cwd != ".":
        raise JobRegistryError(f"{name}: cwd must be repository root")
    timeout = float(raw.get("timeout_seconds", 0))
    if not 1.0 <= timeout <= 14_400.0:
        raise JobRegistryError(f"{name}: timeout_seconds outside 1..14400")
    privilege = str(raw.get("privilege", ""))
    if privilege not in {"standard", "maintenance"}:
        raise JobRegistryError(f"{name}: invalid privilege")
    ownership = str(raw.get("ownership", ""))
    if ownership not in {"legacy", "registry", "disabled"}:
        raise JobRegistryError(f"{name}: invalid ownership")
    artifacts = raw.get("artifact_contract", [])
    if not isinstance(artifacts, list) or any(not isinstance(item, str) for item in artifacts):
        raise JobRegistryError(f"{name}: artifact_contract must be a string list")
    for artifact in artifacts:
        normalized = artifact.replace("\\", "/")
        if normalized.startswith("/") or ".." in Path(normalized).parts:
            raise JobRegistryError(f"{name}: artifact path escapes repository")
    return JobSpec(
        name=name,
        argv=argv,
        cwd=cwd,
        cadence=str(raw.get("cadence", "")),
        timeout_seconds=timeout,
        lock_group=lock_group,
        privilege=privilege,
        ownership=ownership,
        enabled=bool(raw.get("enabled", False)),
        artifact_contract=tuple(artifacts),
    )


def load_registry(path: Path | str) -> dict[str, JobSpec]:
    registry_path = Path(path)
    try:
        raw = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise JobRegistryError(f"unreadable registry: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("version") != REGISTRY_VERSION:
        raise JobRegistryError("unsupported job registry version")
    rows = raw.get("jobs")
    if not isinstance(rows, list):
        raise JobRegistryError("registry jobs must be a list")
    specs: dict[str, JobSpec] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise JobRegistryError("each registry job must be an object")
        spec = _parse_spec(row)
        if spec.name in specs:
            raise JobRegistryError(f"duplicate job name: {spec.name}")
        specs[spec.name] = spec
    return specs


def _atomic_result(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(dict(payload), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _tail(value: str | None, limit: int = 16_384) -> str:
    return str(value or "")[-limit:]


def run_job(
    spec: JobSpec,
    *,
    repo_root: Path | str,
    result_root: Path | str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    now: Callable[[], datetime] = _utc_now,
) -> JobResult:
    """Run one registry-owned job and persist its exact terminal state."""
    root = Path(repo_root).resolve()
    results = Path(result_root).resolve()
    started_dt = now()
    started_at = started_dt.astimezone(timezone.utc).isoformat()
    if not spec.enabled:
        raise JobRegistryError(f"{spec.name}: job is disabled")
    if spec.ownership != "registry":
        raise JobRegistryError(
            f"{spec.name}: ownership={spec.ownership}; refusing duplicate execution"
        )
    entrypoint = (root / spec.argv[1]).resolve()
    if root not in entrypoint.parents or not entrypoint.is_file():
        raise JobRegistryError(f"{spec.name}: entrypoint missing or escaped repository")
    lock_path = results / ".locks" / f"{spec.lock_group}.lock"
    descriptor = acquire_lock(lock_path, stale_seconds=spec.timeout_seconds * 2)
    if descriptor is None:
        completed_dt = now()
        result = JobResult(
            name=spec.name,
            status="BUSY",
            exit_code=75,
            started_at=started_at,
            completed_at=completed_dt.astimezone(timezone.utc).isoformat(),
            duration_seconds=max(0.0, (completed_dt - started_dt).total_seconds()),
            argv=spec.argv,
            stdout_tail="",
            stderr_tail=f"lock group already active: {spec.lock_group}",
            ownership=spec.ownership,
        )
        _atomic_result(results / f"{spec.name}.json", result.to_dict())
        return result
    try:
        argv = [sys.executable, str(entrypoint), *spec.argv[2:]]
        environment = dict(os.environ)
        environment["DUMMY_SUPERVISED_JOB"] = spec.name
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            completed = runner(
                argv,
                cwd=str(root),
                env=environment,
                shell=False,
                capture_output=True,
                text=True,
                timeout=spec.timeout_seconds,
                check=False,
                creationflags=creationflags,
            )
            exit_code = int(completed.returncode)
            status = "SUCCEEDED" if exit_code == 0 else "FAILED"
            stdout_tail = _tail(completed.stdout)
            stderr_tail = _tail(completed.stderr)
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            status = "TIMED_OUT"
            stdout_tail = _tail(exc.stdout.decode() if isinstance(exc.stdout, bytes) else exc.stdout)
            stderr_tail = _tail(exc.stderr.decode() if isinstance(exc.stderr, bytes) else exc.stderr)
        except OSError as exc:
            exit_code = 127
            status = "FAILED_TO_START"
            stdout_tail = ""
            stderr_tail = f"{type(exc).__name__}:{exc}"
        completed_dt = now()
        result = JobResult(
            name=spec.name,
            status=status,
            exit_code=exit_code,
            started_at=started_at,
            completed_at=completed_dt.astimezone(timezone.utc).isoformat(),
            duration_seconds=max(0.0, (completed_dt - started_dt).total_seconds()),
            argv=spec.argv,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
            ownership=spec.ownership,
        )
        _atomic_result(results / f"{spec.name}.json", result.to_dict())
        return result
    finally:
        release_lock(descriptor, lock_path)
