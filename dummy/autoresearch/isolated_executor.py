"""Bounded subprocess executor for the code-owned research plugin allowlist."""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .control_models import EvidenceSnapshot, ResearchDefinition, RunStatus
from .models import AutoresearchValidationError


@dataclass(frozen=True, slots=True)
class WorkerExecution:
    status: RunStatus
    started_at: datetime
    completed_at: datetime
    wall_seconds: float
    result: dict[str, Any]


class _WindowsJob:
    """Minimal Job Object enforcing process memory/time and kill-on-close."""

    def __init__(self, process: subprocess.Popen[bytes], definition: ResearchDefinition):
        self.handle: int | None = None
        if os.name != "nt":
            return
        from ctypes import wintypes

        class BasicLimitInformation(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IoCounters(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class ExtendedLimitInformation(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BasicLimitInformation),
                ("IoInfo", IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel32.AssignProcessToJobObject.argtypes = [
            wintypes.HANDLE,
            wintypes.HANDLE,
        ]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            process.terminate()
            raise AutoresearchValidationError(
                "unable to create a Windows research Job Object"
            )
        information = ExtendedLimitInformation()
        information.BasicLimitInformation.PerProcessUserTimeLimit = (
            int(definition.budget.maximum_cpu_seconds) * 10_000_000
        )
        information.ProcessMemoryLimit = (
            int(definition.budget.maximum_memory_mb) * 1024 * 1024
        )
        information.JobMemoryLimit = information.ProcessMemoryLimit
        information.BasicLimitInformation.LimitFlags = (
            0x00000002  # JOB_OBJECT_LIMIT_PROCESS_TIME
            | 0x00000100  # JOB_OBJECT_LIMIT_PROCESS_MEMORY
            | 0x00000200  # JOB_OBJECT_LIMIT_JOB_MEMORY
            | 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        if not kernel32.SetInformationJobObject(
            handle,
            9,
            ctypes.byref(information),
            ctypes.sizeof(information),
        ):
            kernel32.CloseHandle(handle)
            process.terminate()
            raise AutoresearchValidationError(
                "unable to set Windows research Job Object limits"
            )
        if not kernel32.AssignProcessToJobObject(handle, process._handle):  # type: ignore[attr-defined]
            kernel32.CloseHandle(handle)
            process.terminate()
            raise AutoresearchValidationError(
                "unable to assign research worker to its Job Object"
            )
        self.handle = int(handle)
        self._kernel32 = kernel32

    def close(self) -> None:
        if self.handle is not None:
            self._kernel32.CloseHandle(self.handle)
            self.handle = None


def _posix_limits(definition: ResearchDefinition):
    if os.name == "nt":
        return None

    def apply_limits() -> None:
        import resource

        cpu = int(definition.budget.maximum_cpu_seconds)
        memory = int(definition.budget.maximum_memory_mb) * 1024 * 1024
        output = int(definition.budget.maximum_output_bytes)
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        resource.setrlimit(resource.RLIMIT_FSIZE, (output, output))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    return apply_limits


class IsolatedResearchExecutor:
    """Executes only ``protected_worker.py`` with a sanitized environment."""

    def __init__(self, worker_path: Path | None = None) -> None:
        self.worker_path = worker_path or Path(__file__).with_name(
            "protected_worker.py"
        )

    @staticmethod
    def sanitized_environment() -> dict[str, str]:
        # Start from an explicit empty environment. Even iterating over the
        # parent mapping would expose credential names and values to this
        # package before an allowlist filter could discard them. The worker is
        # launched through an absolute interpreter path and needs no PATH,
        # shell, home directory, provider credential, or inherited temp path.
        return {
            "DUMMY_RESEARCH_SANDBOX": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        }

    def execute(
        self,
        definition: ResearchDefinition,
        evidence: EvidenceSnapshot,
    ) -> WorkerExecution:
        request = {
            "definition": definition.to_dict(),
            "evidence": evidence.to_dict(),
        }
        input_bytes = json.dumps(
            request,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        if len(input_bytes) > definition.budget.maximum_input_bytes:
            raise AutoresearchValidationError(
                "research input exceeds its preregistered byte budget"
            )
        started_at = datetime.now(timezone.utc)
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="dummy-research-") as sandbox:
            creationflags = (
                subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
                if os.name == "nt"
                else 0
            )
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    str(self.worker_path.resolve()),
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=sandbox,
                env=self.sanitized_environment(),
                shell=False,
                creationflags=creationflags,
                preexec_fn=_posix_limits(definition),
            )
            job: _WindowsJob | None = None
            try:
                job = _WindowsJob(process, definition)
                try:
                    stdout, stderr = process.communicate(
                        input=input_bytes,
                        timeout=definition.budget.maximum_wall_seconds,
                    )
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
                    completed_at = datetime.now(timezone.utc)
                    return WorkerExecution(
                        status=RunStatus.TIMED_OUT,
                        started_at=started_at,
                        completed_at=completed_at,
                        wall_seconds=time.monotonic() - started,
                        result={
                            "worker_status": "TIMED_OUT",
                            "outcome": "FAIL",
                            "reason": "WALL_TIME_BUDGET_EXCEEDED",
                            "source_edit_applied": False,
                            "runtime_application": False,
                            "automatic_promotion": False,
                            "execution_authority": False,
                            "capital_authority": False,
                            "orders_placed": False,
                        },
                    )
            finally:
                if job is not None:
                    job.close()
            completed_at = datetime.now(timezone.utc)
            wall_seconds = time.monotonic() - started
            disk_bytes = sum(
                item.stat().st_size
                for item in Path(sandbox).rglob("*")
                if item.is_file()
            )
            if disk_bytes > definition.budget.maximum_disk_bytes:
                return WorkerExecution(
                    status=RunStatus.FAILED,
                    started_at=started_at,
                    completed_at=completed_at,
                    wall_seconds=wall_seconds,
                    result={
                        "worker_status": "FAILED",
                        "outcome": "FAIL",
                        "reason": "EPHEMERAL_DISK_BUDGET_EXCEEDED",
                        "disk_bytes_written": disk_bytes,
                        "source_edit_applied": False,
                        "runtime_application": False,
                        "automatic_promotion": False,
                        "execution_authority": False,
                        "capital_authority": False,
                        "orders_placed": False,
                    },
                )
            if len(stdout) > definition.budget.maximum_output_bytes:
                return WorkerExecution(
                    status=RunStatus.FAILED,
                    started_at=started_at,
                    completed_at=completed_at,
                    wall_seconds=wall_seconds,
                    result={
                        "worker_status": "FAILED",
                        "outcome": "FAIL",
                        "reason": "OUTPUT_BYTE_BUDGET_EXCEEDED",
                        "source_edit_applied": False,
                        "runtime_application": False,
                        "automatic_promotion": False,
                        "execution_authority": False,
                        "capital_authority": False,
                        "orders_placed": False,
                    },
                )
            try:
                result = json.loads(stdout.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                result = {
                    "worker_status": "FAILED",
                    "outcome": "FAIL",
                    "reason": "INVALID_WORKER_OUTPUT",
                    "stderr_type": "present" if stderr else "empty",
                    "source_edit_applied": False,
                    "runtime_application": False,
                    "automatic_promotion": False,
                    "execution_authority": False,
                    "capital_authority": False,
                    "orders_placed": False,
                }
            worker_status = str(result.get("worker_status") or "FAILED")
            sandbox_report = result.get("sandbox")
            if isinstance(sandbox_report, dict):
                sandbox_report["ephemeral_disk_bytes"] = disk_bytes
                sandbox_report["maximum_disk_bytes"] = (
                    definition.budget.maximum_disk_bytes
                )
            status = {
                "COMPLETE": RunStatus.COMPLETE,
                "BLOCKED": RunStatus.BLOCKED,
                "FAILED": RunStatus.FAILED,
            }.get(worker_status, RunStatus.FAILED)
            if process.returncode != 0:
                status = RunStatus.FAILED
            return WorkerExecution(
                status=status,
                started_at=started_at,
                completed_at=completed_at,
                wall_seconds=wall_seconds,
                result=dict(result),
            )


__all__ = ["IsolatedResearchExecutor", "WorkerExecution"]
