"""Verified online SQLite backup and restore-drill support.

Maintenance never copies a live ``ledger.db`` with a filesystem copy: in WAL
mode that can omit committed pages still resident in ``-wal``. SQLite's
transactional ``VACUUM INTO`` creates a consistent online snapshot without the
backup API's restart starvation under Dummy's continuous external writer. Each
backup set is staged, integrity-checked, hashed, restore-drilled, and only then
atomically published with a manifest.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

BACKUP_FORMAT_VERSION = 1


class BackupRefused(RuntimeError):
    """A backup or restore precondition failed closed."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _nearest_existing(path: Path) -> Path:
    candidate = path.resolve()
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def _same_volume(left: Path, right: Path) -> bool:
    left_resolved = left.resolve()
    right_resolved = _nearest_existing(right)
    if os.name == "nt":
        return left_resolved.drive.casefold() == right_resolved.drive.casefold()
    return left_resolved.stat().st_dev == right_resolved.stat().st_dev


def _quick_check(path: Path) -> list[str]:
    connection = sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=10.0,
    )
    try:
        return [str(row[0]) for row in connection.execute("PRAGMA quick_check")]
    finally:
        connection.close()


def _table_counts(path: Path) -> dict[str, int]:
    connection = sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=10.0,
    )
    try:
        tables = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        return {
            table: int(connection.execute(
                f'SELECT COUNT(*) FROM "{table.replace(chr(34), chr(34) * 2)}"'
            ).fetchone()[0])
            for table in tables
        }
    finally:
        connection.close()


def _online_backup(source: Path, destination: Path) -> None:
    """Take a compact, transactionally consistent snapshot of a live WAL DB.

    The online-backup API automatically restarts when another connection
    writes. Dummy's continuously active writer can therefore starve even a
    nominal one-step backup and pin WAL growth indefinitely. ``VACUUM INTO`` is
    SQLite's documented live-backup alternative: it holds one logical snapshot
    while WAL writers continue, writes a new database, and never mutates the
    source.
    """
    source_connection = sqlite3.connect(
        f"file:{source.resolve().as_posix()}?mode=ro",
        uri=True,
        timeout=30.0,
    )
    try:
        source_connection.execute("VACUUM INTO ?", (str(destination.resolve()),))
    finally:
        source_connection.close()


def create_verified_backup(
    source: Path | str,
    destination_root: Path | str,
    *,
    archive: Path | str | None = None,
    require_distinct_volume: bool = True,
    free_space_multiplier: float = 1.2,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create and atomically publish a verified backup set.

    ``destination_root`` is explicit; there is deliberately no same-directory
    default.  Production callers require a distinct volume unless an operator
    explicitly opts into a same-volume *interim* snapshot.
    """
    source_path = Path(source).resolve()
    destination = Path(destination_root).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    inputs = [source_path]
    if archive is not None:
        archive_path = Path(archive).resolve()
        if not archive_path.is_file():
            raise FileNotFoundError(archive_path)
        inputs.append(archive_path)
    if require_distinct_volume and _same_volume(source_path, destination):
        raise BackupRefused(
            "backup destination is on the source volume; configure an off-volume "
            "destination or explicitly mark this as an interim same-volume copy"
        )
    if free_space_multiplier < 1.0:
        raise ValueError("free_space_multiplier must be at least 1")
    destination.mkdir(parents=True, exist_ok=True)
    required = int(sum(path.stat().st_size for path in inputs) * free_space_multiplier)
    free = int(shutil.disk_usage(destination).free)
    if free < required:
        raise BackupRefused(
            f"insufficient backup free space: required={required} available={free}"
        )

    created = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    backup_id = created.strftime("%Y%m%dT%H%M%S.%fZ")
    staging = destination / f".backup-{backup_id}.partial"
    published = destination / f"backup-{backup_id}"
    if staging.exists() or published.exists():
        raise FileExistsError(published)
    staging.mkdir()
    try:
        records: list[dict[str, Any]] = []
        used_names: set[str] = set()
        for index, input_path in enumerate(inputs):
            name = input_path.name
            if name in used_names:
                name = f"{index}-{name}"
            used_names.add(name)
            output = staging / name
            _online_backup(input_path, output)
            check = _quick_check(output)
            if check != ["ok"]:
                raise BackupRefused(f"backup quick_check failed for {input_path}: {check[:5]}")
            records.append({
                "source": str(input_path),
                "file": name,
                "bytes": int(output.stat().st_size),
                "sha256": _sha256(output),
                "quick_check": check,
                "table_counts": _table_counts(output),
            })
        manifest: dict[str, Any] = {
            "format_version": BACKUP_FORMAT_VERSION,
            "backup_id": backup_id,
            "created_at": created.isoformat(),
            "status": "VERIFIED",
            "off_volume": not _same_volume(source_path, destination),
            "databases": records,
            "execution_authority": False,
        }
        manifest_path = staging / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        verify_backup_set(manifest_path)
        os.replace(staging, published)
        manifest["manifest_path"] = str(published / "manifest.json")
        return manifest
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def verify_backup_set(
    manifest_path: Path | str,
    *,
    restore_root: Path | str | None = None,
) -> dict[str, Any]:
    """Hash-check and restore-drill every database in a backup set."""
    manifest_file = Path(manifest_path).resolve()
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BackupRefused(f"unreadable backup manifest: {exc}") from exc
    if manifest.get("format_version") != BACKUP_FORMAT_VERSION:
        raise BackupRefused("unsupported backup manifest format")
    if manifest.get("status") != "VERIFIED":
        raise BackupRefused("backup manifest is not VERIFIED")
    databases = manifest.get("databases")
    if not isinstance(databases, list) or not databases:
        raise BackupRefused("backup manifest has no databases")

    temporary: tempfile.TemporaryDirectory[str] | None = None
    if restore_root is None:
        temporary = tempfile.TemporaryDirectory(
            prefix="dummy-restore-drill-",
            dir=str(manifest_file.parent),
        )
        restore = Path(temporary.name)
    else:
        restore = Path(restore_root).resolve()
        restore.mkdir(parents=True, exist_ok=True)
    try:
        verified: list[dict[str, Any]] = []
        for record in databases:
            if not isinstance(record, dict):
                raise BackupRefused("malformed database record")
            source = manifest_file.parent / str(record.get("file", ""))
            if source.parent != manifest_file.parent or not source.is_file():
                raise BackupRefused(f"backup file missing or escaped set: {source}")
            if _sha256(source) != record.get("sha256"):
                raise BackupRefused(f"backup hash mismatch: {source.name}")
            restored = restore / source.name
            shutil.copy2(source, restored)
            check = _quick_check(restored)
            counts = _table_counts(restored)
            if check != ["ok"] or counts != record.get("table_counts"):
                raise BackupRefused(f"restore drill failed: {source.name}")
            verified.append({
                "file": source.name,
                "sha256": record["sha256"],
                "quick_check": check,
                "table_counts": counts,
            })
        return {
            "status": "RESTORE_VERIFIED",
            "backup_id": manifest.get("backup_id"),
            "databases": verified,
            "execution_authority": False,
        }
    finally:
        if temporary is not None:
            temporary.cleanup()


def require_recent_verified_backup(
    manifest_path: Path | str,
    sources: Iterable[Path | str],
    *,
    max_age_hours: float = 30.0,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate freshness, source coverage, hashes, and a restore drill."""
    manifest_file = Path(manifest_path).resolve()
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    created = datetime.fromisoformat(str(manifest.get("created_at")))
    clock = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if created.tzinfo is None:
        raise BackupRefused("backup created_at must be timezone-aware")
    age_hours = (clock - created.astimezone(timezone.utc)).total_seconds() / 3600.0
    if age_hours < 0 or age_hours > max_age_hours:
        raise BackupRefused(
            f"backup age {age_hours:.2f}h exceeds {max_age_hours:g}h maximum"
        )
    covered = {
        str(Path(record["source"]).resolve())
        for record in manifest.get("databases", [])
        if isinstance(record, dict) and record.get("source")
    }
    required = {str(Path(source).resolve()) for source in sources}
    missing = sorted(required - covered)
    if missing:
        raise BackupRefused(f"backup does not cover required sources: {missing}")
    return verify_backup_set(manifest_file)
