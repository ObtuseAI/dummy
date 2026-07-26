from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from autonomy.job_supervisor import (
    JobRegistryError,
    JobSpec,
    load_registry,
    run_job,
)
from autonomy.ledger import AutonomyLedger, checkpoint_ledger_wal, ledger_health_probe
from autonomy.ledger_backup import (
    BackupRefused,
    _online_backup,
    create_verified_backup,
    require_recent_verified_backup,
    verify_backup_set,
)
from autonomy.ledger_vacuum import vacuum_ledger
from autonomy.maintenance import (
    MaintenanceBusy,
    acquire_maintenance,
    maintenance_active,
    release_maintenance,
    retry_sqlite_locked,
)


NOW = datetime(2026, 7, 26, 3, 0, tzinfo=timezone.utc)


def test_maintenance_lease_is_exclusive_bounded_and_released(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    db.touch()
    lease = acquire_maintenance(db, "retention", wait_seconds=0)
    try:
        active = maintenance_active(db)
        assert active is not None
        assert str(active["pid"]) == lease.path.read_text(
            encoding="utf-8"
        ).split("pid=", 1)[1].split()[0]
        with pytest.raises(MaintenanceBusy, match="unavailable"):
            acquire_maintenance(db, "prune", wait_seconds=0)
    finally:
        release_maintenance(lease)
    assert maintenance_active(db) is None
    replacement = acquire_maintenance(db, "prune", wait_seconds=0)
    release_maintenance(replacement)


def test_retry_sqlite_locked_retries_only_lock_errors(monkeypatch) -> None:
    monkeypatch.setattr("autonomy.maintenance.time.sleep", lambda _seconds: None)
    calls = 0

    def transient():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise sqlite3.OperationalError("database is locked")
        return "ok"

    assert retry_sqlite_locked(
        transient, deadline_monotonic=float("inf"),
    ) == "ok"
    assert calls == 3

    with pytest.raises(sqlite3.OperationalError, match="malformed"):
        retry_sqlite_locked(
            lambda: (_ for _ in ()).throw(sqlite3.OperationalError("malformed")),
            deadline_monotonic=float("inf"),
        )


def _seed_backup_db(path: Path) -> None:
    ledger = AutonomyLedger(path)
    try:
        ledger._conn.execute("CREATE TABLE IF NOT EXISTS backup_fixture(value TEXT)")  # noqa: SLF001
        ledger._conn.executemany(  # noqa: SLF001
            "INSERT INTO backup_fixture(value) VALUES (?)",
            [(f"row-{index}",) for index in range(200)],
        )
        ledger._conn.commit()  # noqa: SLF001
    finally:
        ledger.close()


def test_online_backup_is_hashed_and_restore_drilled(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    _seed_backup_db(db)
    report = create_verified_backup(
        db,
        tmp_path / "backups",
        require_distinct_volume=False,
        now=NOW,
    )
    manifest = Path(report["manifest_path"])
    verified = verify_backup_set(manifest)
    assert verified["status"] == "RESTORE_VERIFIED"
    assert verified["databases"][0]["table_counts"]["backup_fixture"] == 200
    assert require_recent_verified_backup(
        manifest, [db], max_age_hours=1, now=NOW + timedelta(minutes=30),
    )["status"] == "RESTORE_VERIFIED"

    blob = json.loads(manifest.read_text(encoding="utf-8"))
    backed_up = manifest.parent / blob["databases"][0]["file"]
    with backed_up.open("ab") as handle:
        handle.write(b"tamper")
    with pytest.raises(BackupRefused, match="hash mismatch"):
        verify_backup_set(manifest)


def test_online_backup_uses_transactional_vacuum_into(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The backup API can restart forever under Dummy's continuous writer."""

    calls: list[tuple[str, tuple[str, ...]]] = []

    class FakeConnection:
        def execute(self, statement, parameters):
            calls.append((statement, parameters))

        def close(self):
            return None

    source_connection = FakeConnection()
    monkeypatch.setattr(
        "autonomy.ledger_backup.sqlite3.connect",
        lambda *_args, **_kwargs: source_connection,
    )

    destination = tmp_path / "backup.db"
    _online_backup(tmp_path / "source.db", destination)

    assert calls == [("VACUUM INTO ?", (str(destination.resolve()),))]


def test_backup_rejects_stale_manifest(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    _seed_backup_db(db)
    report = create_verified_backup(
        db, tmp_path / "backups", require_distinct_volume=False, now=NOW,
    )
    with pytest.raises(BackupRefused, match="exceeds"):
        require_recent_verified_backup(
            report["manifest_path"],
            [db],
            max_age_hours=1,
            now=NOW + timedelta(hours=2),
        )


def test_vacuum_requires_backup_and_preserves_integrity(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    _seed_backup_db(db)
    connection = sqlite3.connect(db)
    try:
        connection.execute("DELETE FROM backup_fixture WHERE rowid > 10")
        connection.commit()
    finally:
        connection.close()
    backup = create_verified_backup(
        db, tmp_path / "backups", require_distinct_volume=False, now=NOW,
    )
    report = vacuum_ledger(
        db,
        backup_manifest=backup["manifest_path"],
        min_freelist_bytes=0,
        backup_max_age_hours=1,
        max_runtime_s=30,
        now=NOW,
    )
    assert report.status == "APPLIED"
    assert report.quick_check_before == report.quick_check_after == ("ok",)
    assert report.execution_authority is False


def _spec(**overrides) -> JobSpec:
    values = {
        "name": "grading-worker",
        "argv": ("{python}", "scripts/run_dummy_grading_worker.py"),
        "cwd": ".",
        "cadence": "test",
        "timeout_seconds": 30.0,
        "lock_group": "grading-worker",
        "privilege": "standard",
        "ownership": "registry",
        "enabled": True,
        "artifact_contract": (),
    }
    values.update(overrides)
    return JobSpec(**values)


def test_supervisor_propagates_child_exit_and_never_uses_shell(tmp_path: Path) -> None:
    seen = {}

    def runner(argv, **kwargs):
        seen["argv"] = argv
        seen.update(kwargs)
        return subprocess.CompletedProcess(argv, 7, stdout="out", stderr="failed")

    times = iter((NOW, NOW + timedelta(seconds=2)))
    result = run_job(
        _spec(),
        repo_root=Path(__file__).resolve().parent.parent,
        result_root=tmp_path,
        runner=runner,
        now=lambda: next(times),
    )
    assert result.status == "FAILED"
    assert result.exit_code == 7
    assert result.stderr_tail == "failed"
    assert seen["shell"] is False
    assert seen["check"] is False
    receipt = json.loads((tmp_path / "grading-worker.json").read_text(encoding="utf-8"))
    assert receipt["exit_code"] == 7
    assert receipt["execution_authority"] is False


def test_supervisor_timeout_and_ownership_are_fail_closed(tmp_path: Path) -> None:
    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(["python"], 1, output="partial")

    times = iter((NOW, NOW + timedelta(seconds=1)))
    result = run_job(
        _spec(),
        repo_root=Path(__file__).resolve().parent.parent,
        result_root=tmp_path,
        runner=timeout,
        now=lambda: next(times),
    )
    assert (result.status, result.exit_code) == ("TIMED_OUT", 124)
    with pytest.raises(JobRegistryError, match="duplicate execution"):
        run_job(
            _spec(ownership="legacy"),
            repo_root=Path(__file__).resolve().parent.parent,
            result_root=tmp_path,
        )


def test_registry_rejects_authority_commands_and_shipped_registry_is_valid(
    tmp_path: Path,
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "version": 1,
        "jobs": [{
            "name": "bad",
            "argv": [
                "{python}", "scripts/run_dummy_ledger_retention.py",
                "--submit",
            ],
            "cwd": ".",
            "cadence": "never",
            "timeout_seconds": 30,
            "lock_group": "bad",
            "privilege": "maintenance",
            "ownership": "registry",
            "enabled": True,
            "artifact_contract": [],
        }],
    }), encoding="utf-8")
    with pytest.raises(JobRegistryError, match="forbidden"):
        load_registry(bad)
    shipped = load_registry(
        Path(__file__).resolve().parent.parent / "ops" / "job_registry.json"
    )
    assert shipped["ledger-retention"].ownership == "legacy"
    assert shipped["grading-worker"].ownership == "registry"


def test_health_reports_wal_bytes_and_idle_checkpoint(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    ledger = AutonomyLedger(db)
    try:
        ledger._conn.execute(  # noqa: SLF001
            "INSERT INTO lessons(scope,lesson,created_at) "
            "VALUES ('x','y','2026-07-26T00:00:00+00:00')"
        )
        ledger._conn.commit()  # noqa: SLF001
        health = ledger.health()
        assert health["wal_autocheckpoint"] > 0
        assert health["wal_size_bytes"] >= 0
    finally:
        ledger.close()
    probe = ledger_health_probe(db)
    assert probe["wal_size_bytes"] >= 0
    assert checkpoint_ledger_wal(db)["status"] in {"OK", "BUSY"}


def test_maintenance_launchers_wait_and_propagate_exit_code() -> None:
    root = Path(__file__).resolve().parent.parent
    for name in (
        "launch_ledger_retention.vbs",
        "launch_signal_prune.vbs",
        "launch_ledger_vacuum.vbs",
    ):
        text = (root / "scripts" / "tasks" / name).read_text(encoding="utf-8")
        assert ", 0, True)" in text
        assert "WScript.Quit exitCode" in text
        assert ", 0, False)" not in text
    for launcher in (root / "scripts" / "tasks").glob("*.vbs"):
        assert ", 0, False)" not in launcher.read_text(encoding="utf-8"), launcher.name


def test_retention_apply_cli_refuses_without_verified_backup(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parent.parent
    db = tmp_path / "ledger.db"
    db.touch()
    environment = dict(os.environ)
    environment.pop("DUMMY_MAINTENANCE_BACKUP_MANIFEST", None)
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "run_dummy_ledger_retention.py"),
            "--db",
            str(db),
            "--apply",
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["status"] == "REFUSED"
    assert "backup-manifest" in payload["error"]
