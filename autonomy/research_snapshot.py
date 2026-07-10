"""Read-only SQLite-to-Parquet research snapshots with a hash manifest."""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_TABLES = (
    "signals", "signal_rejections", "decisions", "outcomes", "settlements",
    "source_trust", "bankroll_curve", "lessons",
    "external_observations",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def export_research_snapshot(
    db_path: Path | str,
    output_root: Path | str,
    *,
    tables: Iterable[str] = DEFAULT_TABLES,
) -> tuple[Path, dict[str, Any]]:
    """Export present tables through a query-only connection; never migrate SQLite."""
    try:
        import polars as pl
    except ImportError as exc:
        raise RuntimeError("install the research extra to enable Parquet snapshots") from exc

    source = Path(db_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = Path(output_root).resolve() / f"SNAPSHOT_{stamp}"
    target.mkdir(parents=True, exist_ok=False)
    connection = sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)
    manifest_tables: list[dict[str, Any]] = []
    try:
        connection.execute("PRAGMA query_only=ON")
        present = {str(row[0]) for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        for table in tables:
            if table not in present:
                continue
            if not table.replace("_", "").isalnum():
                raise ValueError(f"unsafe table name: {table}")
            # Historical ledgers contain timestamp-like TEXT values in several
            # ISO variants. Inspect the full result before choosing a Polars
            # type so a late row cannot invalidate a partial snapshot.
            frame = pl.read_database(
                f'SELECT * FROM "{table}"', connection, infer_schema_length=None,
            )
            parquet = target / f"{table}.parquet"
            frame.write_parquet(parquet, compression="zstd", statistics=True)
            manifest_tables.append({
                "table": table,
                "rows": frame.height,
                "columns": frame.columns,
                "file": parquet.name,
                "bytes": parquet.stat().st_size,
                "sha256": _sha256(parquet),
            })
    except Exception:
        # A snapshot is atomic at the directory level: never leave a partial
        # research corpus that could be mistaken for complete evidence.
        shutil.rmtree(target, ignore_errors=True)
        raise
    finally:
        connection.close()

    manifest: dict[str, Any] = {
        "report_name": "DUMMY_RESEARCH_SNAPSHOT",
        "source_database": str(source),
        "sqlite_access": "mode=ro; PRAGMA query_only=ON",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_directory": str(target),
        "tables": manifest_tables,
        "total_rows": sum(int(item["rows"]) for item in manifest_tables),
    }
    manifest_path = target / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest_path, manifest
