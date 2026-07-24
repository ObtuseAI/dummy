"""SQLite ledger: decisions, outcomes, calibration, source trust, bankroll curve.

The ledger is the substrate of recursive improvement — every weight update,
stage promotion, and Reflexion lesson traces back to rows here. Append-only
for facts; the only UPDATEs are settlement backfills onto their own rows.
"""
from __future__ import annotations

import json
import hashlib
import math
import os
import sqlite3
import time
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from autonomy.ontology import Decision, Signal, TradeOutcome
from autonomy.retention import install_signal_history

# Concurrency hardening. Wave-83: the ledger runs in WAL mode. The historical
# reason it was rollback-journal — retention.enforce_retention required a
# single atomic cross-database archive+delete transaction, which WAL cannot
# provide — was removed by rewriting retention as a two-phase idempotent
# protocol (each phase commits exactly one database; see autonomy/retention.py).
# Rollback-journal mode caused three escalating production failures (Waves
# 37/80/81/82 fought its symptoms): any long reader held SHARED and starved
# every writer, and a writer waiting at PENDING then locked out all new
# readers — observed live 2026-07-24 as a 4.5-hour full-database lockout
# (CYCLE_ERROR streak, dead report writers, stale heartbeat). Under WAL,
# readers never block writers and writers never block readers; only
# writer-vs-writer contention remains, which busy_timeout + bounded retry
# absorb. DUMMY_LEDGER_WAL=0 opts back out (the mode persists in the file, so
# opting out also requires a manual "PRAGMA journal_mode=DELETE").
def _ledger_busy_timeout_s() -> float:
    try:
        value = float(os.environ.get("DUMMY_LEDGER_BUSY_TIMEOUT_S", "60"))
        return value if value > 0 else 60.0
    except (TypeError, ValueError):
        return 60.0


LEDGER_BUSY_TIMEOUT_S = _ledger_busy_timeout_s()
LEDGER_LOCK_RETRIES = 5
LEDGER_LOCK_BACKOFF_S = 0.1


def _signal_write_chunk() -> int:
    """Rows per commit when persisting a cycle's signals. A cycle writes ~23k
    signals; on the non-WAL ledger a single transaction holds the whole-DB write
    lock for its entire duration (minutes on a multi-million-row table), which
    starves every other writer (the next cycle, the recal weight-write, the
    retention/prune) and was a core contention source. Committing in chunks
    releases + reacquires the lock at each boundary, so concurrent writers
    interleave instead of blocking for minutes. Env-tunable; 0/negative => one
    transaction (legacy behavior)."""
    import os

    try:
        return int(os.environ.get("DUMMY_SIGNAL_WRITE_CHUNK", "3000"))
    except (TypeError, ValueError):
        return 3000


LEDGER_SIGNAL_WRITE_CHUNK = _signal_write_chunk()
# A ledger past this size is flagged for operator maintenance (checkpoint /
# retention archival / VACUUM). The live ledger crossed 9 GiB before this guard.
LEDGER_BLOAT_WARN_BYTES = 8 * 1024 ** 3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    market_ticker TEXT NOT NULL,
    action TEXT NOT NULL,
    side TEXT NOT NULL,
    price_cents INTEGER NOT NULL,
    count INTEGER NOT NULL,
    ev_cents REAL NOT NULL,
    kelly REAL NOT NULL,
    notional_cents INTEGER NOT NULL,
    probability_yes REAL NOT NULL,
    forecast_uncertainty REAL NOT NULL DEFAULT 0.5,
    market_implied_yes REAL,
    sources_used TEXT NOT NULL,
    abstain_reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    tier_label TEXT,
    tier_policy_version TEXT,
    tier_score REAL,
    tier_reason TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id TEXT NOT NULL,
    market_ticker TEXT NOT NULL,
    kind TEXT NOT NULL,
    order_id TEXT,
    fill_count INTEGER NOT NULL DEFAULT 0,
    fill_price_cents INTEGER,
    pnl_cents INTEGER,
    broker_contacted INTEGER NOT NULL DEFAULT 0,
    detail TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decision_tier_attribution (
    decision_id TEXT PRIMARY KEY,
    policy_version TEXT NOT NULL,
    tier_label TEXT,
    tier_score REAL,
    tier_reason TEXT NOT NULL DEFAULT '',
    assigned_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    snapshot_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tier_policy_epochs (
    policy_version TEXT PRIMARY KEY,
    first_signal_id INTEGER NOT NULL,
    started_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    market_ticker TEXT NOT NULL,
    probability_yes REAL NOT NULL,
    uncertainty REAL NOT NULL,
    rationale TEXT NOT NULL,
    features TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'live',
    ingested_at TEXT NOT NULL,
    ingest_version INTEGER NOT NULL DEFAULT 2
);
CREATE TABLE IF NOT EXISTS signal_rejections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    market_ticker TEXT NOT NULL,
    probability_yes REAL,
    uncertainty REAL,
    signal_created_at TEXT,
    mode TEXT NOT NULL,
    reason TEXT NOT NULL,
    rejected_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settlements (
    market_ticker TEXT PRIMARY KEY,
    result_yes INTEGER NOT NULL,
    settled_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settlement_provenance (
    market_ticker TEXT PRIMARY KEY,
    source TEXT NOT NULL DEFAULT '',
    evidence TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS source_trust (
    source TEXT PRIMARY KEY,
    weight REAL NOT NULL,
    brier_sum REAL NOT NULL DEFAULT 0,
    brier_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bankroll_curve (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bankroll_cents INTEGER NOT NULL,
    open_exposure_cents INTEGER NOT NULL,
    stage INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    lesson TEXT NOT NULL,
    evidence TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS external_observations (
    observation_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    series_id TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    published_at TEXT,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    features TEXT NOT NULL DEFAULT '{}',
    ingested_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_outcomes_decision ON outcomes(decision_id);
CREATE INDEX IF NOT EXISTS idx_signals_market ON signals(market_ticker);
CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at);
CREATE INDEX IF NOT EXISTS idx_signals_market_created ON signals(market_ticker, created_at);
CREATE INDEX IF NOT EXISTS idx_signals_source_created ON signals(source, created_at);
CREATE INDEX IF NOT EXISTS idx_signal_rejections_created ON signal_rejections(rejected_at);
CREATE INDEX IF NOT EXISTS idx_decisions_market ON decisions(market_ticker);
CREATE INDEX IF NOT EXISTS idx_decisions_created ON decisions(created_at);
CREATE INDEX IF NOT EXISTS idx_external_observations_source_time
    ON external_observations(source, observed_at);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_tier_score(value: Any) -> float | None:
    """Match the six-decimal precision frozen in tier feature snapshots."""
    if value is None:
        return None
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("tier score must be finite")
    return round(parsed, 6)


def _rows_match_with_canonical_score(
    stored: Iterable[Any], candidate: Iterable[Any], *, score_index: int,
) -> bool:
    """Compare immutable rows while normalizing historical float tails."""
    left = list(stored)
    right = list(candidate)
    if len(left) != len(right):
        return False
    try:
        left[score_index] = _canonical_tier_score(left[score_index])
        right[score_index] = _canonical_tier_score(right[score_index])
    except (IndexError, TypeError, ValueError):
        return False
    return left == right


def _loads_features(raw: Any) -> dict[str, Any]:
    """Parse a persisted features JSON blob; never raise on a bad row."""
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _external_observation_id(
    source: str, series_id: str, observed_at: str, published_at: str | None,
    value: float, unit: str,
) -> str:
    canonical = json.dumps(
        [source, series_id, observed_at, published_at or "", format(value, ".17g"), unit],
        separators=(",", ":"), ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def ledger_health_probe(
    db_path: Path | str = Path("runtime/autonomy/ledger.db"),
) -> dict[str, Any]:
    """Read-only ledger health snapshot for heartbeat/alerting surfaces.

    Opens the database strictly ``mode=ro`` (never creates or mutates it) and
    reports file size, bloat flag, and header pragmas. Any failure to probe is
    itself a health finding (``probe_error``), never an exception — a daemon
    heartbeat must not die on a sick database.
    """
    path = Path(db_path)
    info: dict[str, Any] = {
        "db_path": str(path),
        "exists": path.exists(),
        "size_bytes": 0,
        "size_gib": 0.0,
        "bloat_warn": False,
        "bloat_warn_bytes": int(LEDGER_BLOAT_WARN_BYTES),
        "probe_error": None,
    }
    if not path.exists():
        return info
    try:
        size = path.stat().st_size
        info["size_bytes"] = int(size)
        info["size_gib"] = round(size / 1024 ** 3, 3)
        info["bloat_warn"] = size >= LEDGER_BLOAT_WARN_BYTES
    except OSError as exc:
        info["probe_error"] = f"stat:{exc}"
        return info
    try:
        connection = sqlite3.connect(
            f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=5.0,
        )
        try:
            for pragma in ("freelist_count", "page_size", "journal_mode"):
                info[pragma] = connection.execute(f"PRAGMA {pragma}").fetchone()[0]
            page_size = int(info.get("page_size") or 0)
            freelist = int(info.get("freelist_count") or 0)
            info["freelist_bytes"] = freelist * page_size
        finally:
            connection.close()
    except sqlite3.Error as exc:
        info["probe_error"] = f"{type(exc).__name__}:{exc}"
    return info


class AutonomyLedger:
    def __init__(self, db_path: Path | str = Path("runtime/autonomy/ledger.db")):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        resolved = self.db_path.resolve()
        mode = "rw" if resolved.exists() else "rwc"
        # Count of write operations that had to be retried after SQLITE_BUSY.
        # A nonzero, growing value is the leading indicator of lock contention.
        self._lock_retries = 0
        self._conn = sqlite3.connect(
            f"file:{resolved.as_posix()}?mode={mode}",
            uri=True,
            timeout=LEDGER_BUSY_TIMEOUT_S,
        )
        # Wait for a held lock instead of raising immediately. Belt (connect
        # timeout) and suspenders (explicit PRAGMA) — some builds honor one but
        # not the other.
        self._conn.execute(f"PRAGMA busy_timeout={int(LEDGER_BUSY_TIMEOUT_S * 1000)}")
        # Wave-83: WAL so readers and writers never block each other (see the
        # module-level concurrency note). The mode persists in the database
        # header, so this is a one-time flip that every later connection
        # inherits; best-effort because an old-mode lock holder can defer it.
        if os.environ.get("DUMMY_LEDGER_WAL", "1") == "1":
            try:
                self._conn.execute("PRAGMA journal_mode=WAL")
            except sqlite3.OperationalError:
                pass
        self._apply_perf_pragmas()
        self._conn.executescript(_SCHEMA)
        self._migrate()
        self._retry_on_locked(self._conn.commit)
        install_signal_history(self._conn)
        self._tier_policy_epochs_seen = {
            str(row[0]) for row in self._conn.execute(
                "SELECT policy_version FROM tier_policy_epochs"
            )
        }

    def _apply_perf_pragmas(self) -> None:
        """Tune the connection for a multi-GB ledger (env-overridable).

        The default 2 MB page cache means every per-cycle index update and every
        backtest scan reads cold pages from disk; ``synchronous=FULL`` fsyncs
        each of the ~15k per-cycle commits. A large cache keeps hot pages
        resident and NORMAL is crash-safe under WAL (it can only lose the last
        transaction on OS/power loss, which is acceptable for a paper shadow
        ledger; retention's two-phase protocol never depends on it). Best-effort:
        never block ledger construction.
        """
        import os

        cache_mb = int(os.environ.get("DUMMY_LEDGER_CACHE_MB", "512"))
        sync = os.environ.get("DUMMY_LEDGER_SYNCHRONOUS", "NORMAL").upper()
        mmap_mb = int(os.environ.get("DUMMY_LEDGER_MMAP_MB", "0"))
        try:
            if cache_mb > 0:
                self._conn.execute(f"PRAGMA cache_size=-{cache_mb * 1024}")  # negative => KiB
            if sync in ("OFF", "NORMAL", "FULL", "EXTRA"):
                self._conn.execute(f"PRAGMA synchronous={sync}")
            self._conn.execute("PRAGMA temp_store=MEMORY")
            if mmap_mb > 0:
                self._conn.execute(f"PRAGMA mmap_size={mmap_mb * 1024 * 1024}")
        except sqlite3.OperationalError:
            pass

    def _retry_on_locked(self, operation: Callable[[], Any]) -> Any:
        """Run a write, retrying with backoff on SQLITE_BUSY within a bound.

        busy_timeout already absorbs most contention; this catches the residual
        race where the lock is grabbed between statements. Non-lock
        OperationalErrors propagate immediately; so does the last lock error —
        bounded retry, fail-closed, never an infinite spin.
        """
        delay = LEDGER_LOCK_BACKOFF_S
        for attempt in range(LEDGER_LOCK_RETRIES):
            try:
                return operation()
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() or attempt == LEDGER_LOCK_RETRIES - 1:
                    raise
                self._lock_retries += 1
                time.sleep(delay)
                delay *= 2

    def set_statement_deadline(self, deadline_monotonic: float | None) -> None:
        """Abort any SQL statement still running past a monotonic deadline.

        The 2026-07-24 lockout was a single synchronous multi-hour query: the
        daemon's cooperative deadline only fires at await boundaries, so a
        blocking sqlite3 call could overrun it forever. A progress handler runs
        inside the VM every N opcodes and aborts the statement (SQLite raises
        OperationalError "interrupted") once the deadline passes — making the
        cycle deadline enforceable against sync SQL. ``None`` clears it.
        """
        if deadline_monotonic is None:
            self._conn.set_progress_handler(None, 0)
            return
        deadline = float(deadline_monotonic)

        def _past_deadline() -> int:
            return 1 if time.monotonic() > deadline else 0

        # ~500k VM opcodes between checks: sub-millisecond granularity on a
        # scan-heavy query, unmeasurable overhead on short statements.
        self._conn.set_progress_handler(_past_deadline, 500_000)

    def health(self) -> dict[str, Any]:
        """Cheap operational health snapshot (file size + header pragmas).

        Never runs integrity_check — that is a full scan and would be ruinous
        on a multi-gigabyte ledger every cycle; see ``integrity_check`` for the
        scheduled/operator-invoked probe.
        """
        try:
            size = self.db_path.stat().st_size if self.db_path.exists() else 0
        except OSError:
            size = 0
        info: dict[str, Any] = {
            "db_path": str(self.db_path),
            "size_bytes": int(size),
            "size_gib": round(size / 1024 ** 3, 3),
            "lock_retries": int(self._lock_retries),
            "bloat_warn": size >= LEDGER_BLOAT_WARN_BYTES,
        }
        for pragma in ("freelist_count", "page_size", "journal_mode", "busy_timeout"):
            try:
                info[pragma] = self._conn.execute(f"PRAGMA {pragma}").fetchone()[0]
            except Exception:
                info[pragma] = None
        return info

    def integrity_check(self, quick: bool = True) -> dict[str, Any]:
        """PRAGMA (quick_)integrity_check — the scheduled deep probe.

        ``quick=True`` skips the expensive index cross-checks; ``quick=False``
        is the operator-invoked full scan.
        """
        sql = "PRAGMA quick_check" if quick else "PRAGMA integrity_check"
        rows = [str(r[0]) for r in self._conn.execute(sql).fetchall()]
        return {"ok": rows == ["ok"], "quick": bool(quick), "result": rows[:20]}

    def _migrate(self) -> None:
        """Additive migrations for ledgers created before a column existed."""
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(signals)")}
        if "mode" not in columns:
            self._conn.execute("ALTER TABLE signals ADD COLUMN mode TEXT NOT NULL DEFAULT 'live'")
        if "features" not in columns:
            self._conn.execute("ALTER TABLE signals ADD COLUMN features TEXT NOT NULL DEFAULT '{}'")
        if "ingested_at" not in columns:
            self._conn.execute("ALTER TABLE signals ADD COLUMN ingested_at TEXT NOT NULL DEFAULT ''")
            self._conn.execute(
                "UPDATE signals SET ingested_at=created_at WHERE ingested_at=''"
            )
        if "ingest_version" not in columns:
            # Historical rows predate receipt-time and feature provenance.
            self._conn.execute(
                "ALTER TABLE signals ADD COLUMN ingest_version INTEGER NOT NULL DEFAULT 1"
            )
        decision_columns = {row[1] for row in self._conn.execute("PRAGMA table_info(decisions)")}
        if "forecast_uncertainty" not in decision_columns:
            self._conn.execute(
                "ALTER TABLE decisions ADD COLUMN forecast_uncertainty REAL NOT NULL DEFAULT 0.5"
            )
        if "tier_label" not in decision_columns:
            self._conn.execute("ALTER TABLE decisions ADD COLUMN tier_label TEXT")
        if "tier_policy_version" not in decision_columns:
            self._conn.execute("ALTER TABLE decisions ADD COLUMN tier_policy_version TEXT")
        if "tier_score" not in decision_columns:
            self._conn.execute("ALTER TABLE decisions ADD COLUMN tier_score REAL")
        if "tier_reason" not in decision_columns:
            self._conn.execute(
                "ALTER TABLE decisions ADD COLUMN tier_reason TEXT NOT NULL DEFAULT ''"
            )
        attribution_columns = {
            row[1] for row in self._conn.execute(
                "PRAGMA table_info(decision_tier_attribution)"
            )
        }
        if attribution_columns and "recorded_at" not in attribution_columns:
            # Existing rows predate durable receipt time.  Leave them NULL so
            # forward performance excludes them instead of inventing receipt.
            self._conn.execute(
                "ALTER TABLE decision_tier_attribution ADD COLUMN recorded_at TEXT"
            )
        external_columns = {
            row[1] for row in self._conn.execute("PRAGMA table_info(external_observations)")
        }
        if external_columns and "observation_id" not in external_columns:
            # The first raw-statistics schema deduplicated by series/time and
            # would suppress later revisions. Rebuild losslessly with a
            # content-addressed key so revised values become new vintages.
            legacy_rows = self._conn.execute(
                "SELECT source,series_id,observed_at,published_at,value,unit,features,ingested_at"
                " FROM external_observations"
            ).fetchall()
            self._conn.execute(
                "ALTER TABLE external_observations RENAME TO external_observations_legacy"
            )
            self._conn.execute("DROP INDEX IF EXISTS idx_external_observations_source_time")
            self._conn.execute(
                """
                CREATE TABLE external_observations (
                    observation_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    series_id TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    published_at TEXT,
                    value REAL NOT NULL,
                    unit TEXT NOT NULL,
                    features TEXT NOT NULL DEFAULT '{}',
                    ingested_at TEXT NOT NULL
                )
                """
            )
            for row in legacy_rows:
                source, series_id, observed_at, published_at, value, unit, features, ingested = row
                observation_id = _external_observation_id(
                    str(source), str(series_id), str(observed_at), published_at,
                    float(value), str(unit),
                )
                self._conn.execute(
                    "INSERT INTO external_observations VALUES (?,?,?,?,?,?,?,?,?)",
                    (observation_id, source, series_id, observed_at, published_at,
                     value, unit, features, ingested),
                )
            self._conn.execute("DROP TABLE external_observations_legacy")
            self._conn.execute(
                "CREATE INDEX idx_external_observations_source_time"
                " ON external_observations(source, observed_at)"
            )

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------

    @staticmethod
    def _signal_validation_error(signal: Signal, mode: str, now: datetime) -> str | None:
        """Return a stable rejection reason for malformed statistical evidence."""
        if mode not in {"live", "retro"}:
            return "invalid_mode"
        if not isinstance(signal.source, str) or not signal.source.strip():
            return "missing_source"
        if not isinstance(signal.market_ticker, str) or not signal.market_ticker.strip():
            return "missing_market_ticker"
        try:
            probability = float(signal.probability_yes)
            uncertainty = float(signal.uncertainty)
        except (TypeError, ValueError):
            return "non_numeric_probability_or_uncertainty"
        if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
            return "probability_out_of_range"
        if not math.isfinite(uncertainty) or not 0.0 <= uncertainty <= 0.5:
            return "uncertainty_out_of_range"
        try:
            created = datetime.fromisoformat(str(signal.created_at).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return "invalid_created_at"
        if created.tzinfo is None:
            return "created_at_missing_timezone"
        if created.astimezone(timezone.utc) > now + timedelta(minutes=5):
            return "future_created_at"
        if not isinstance(signal.rationale, str):
            return "invalid_rationale"
        if not isinstance(signal.features, dict):
            return "features_not_object"
        try:
            json.dumps(signal.features, sort_keys=True, allow_nan=False)
        except (TypeError, ValueError):
            return "features_not_finite_json"
        return None

    def _reject_signal(self, signal: Signal, mode: str, reason: str, rejected_at: str) -> None:
        def finite_or_none(value: Any) -> float | None:
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                return None
            return parsed if math.isfinite(parsed) else None

        self._conn.execute(
            "INSERT INTO signal_rejections(source, market_ticker, probability_yes, uncertainty,"
            " signal_created_at, mode, reason, rejected_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                str(getattr(signal, "source", ""))[:100],
                str(getattr(signal, "market_ticker", ""))[:200],
                finite_or_none(getattr(signal, "probability_yes", None)),
                finite_or_none(getattr(signal, "uncertainty", None)),
                str(getattr(signal, "created_at", ""))[:100],
                str(mode)[:20],
                reason[:100],
                rejected_at,
            ),
        )

    def record_signals(
        self, signals: list[Signal], mode: str = "live", *, all_or_none: bool = False,
    ) -> list[bool]:
        """Validate and persist signal evidence, retaining features and receipt time.

        Invalid rows are quarantined in ``signal_rejections`` instead of
        crashing an autonomous cycle. ``all_or_none`` is used by historical
        replay so a baseline/model pair cannot be only half-written.
        """
        if not signals:
            return []
        now = datetime.now(timezone.utc)
        ingested_at = now.isoformat()
        errors = [self._signal_validation_error(signal, mode, now) for signal in signals]
        duplicate = []
        for signal, error in zip(signals, errors):
            exists = False
            if error is None:
                exists = self._conn.execute(
                    "SELECT 1 FROM signal_history WHERE source=? AND market_ticker=?"
                    " AND created_at=? AND mode=? LIMIT 1",
                    (signal.source, signal.market_ticker, signal.created_at, mode),
                ).fetchone() is not None
            duplicate.append(exists)
        if all_or_none and (any(errors) or any(duplicate)):
            for signal, error, is_duplicate in zip(signals, errors, duplicate):
                reason = error or ("duplicate_signal" if is_duplicate else "batch_rejected")
                self._reject_signal(signal, mode, reason, ingested_at)
            self._retry_on_locked(self._conn.commit)
            return [False] * len(signals)

        accepted: list[bool] = []
        fingerprints, registered_sources = self._forward_candidate_fingerprints()
        # Chunked commits release the whole-DB write lock at each boundary so
        # concurrent writers interleave (see LEDGER_SIGNAL_WRITE_CHUNK). Disabled
        # for all_or_none (replay atomicity) and when the chunk size is <= 0.
        chunk = 0 if all_or_none else LEDGER_SIGNAL_WRITE_CHUNK
        since_commit = 0
        for signal, error, is_duplicate in zip(signals, errors, duplicate):
            if chunk > 0 and since_commit >= chunk:
                self._retry_on_locked(self._conn.commit)
                since_commit = 0
            since_commit += 1
            if error is not None or is_duplicate:
                self._reject_signal(
                    signal, mode, error or "duplicate_signal", ingested_at,
                )
                accepted.append(False)
                continue
            if registered_sources and signal.source in registered_sources:
                self._stamp_forward_fingerprint(signal, fingerprints)
            features = json.dumps(
                signal.features, sort_keys=True, separators=(",", ":"), allow_nan=False,
            )
            cursor = self._conn.execute(
                "INSERT INTO signals(source, market_ticker, probability_yes, uncertainty,"
                " rationale, features, created_at, mode, ingested_at, ingest_version)"
                " VALUES (?,?,?,?,?,?,?,?,?,2)",
                (
                    signal.source.strip(), signal.market_ticker.strip(),
                    float(signal.probability_yes), float(signal.uncertainty),
                    signal.rationale[:500], features, signal.created_at, mode, ingested_at,
                ),
            )
            policy_version = signal.features.get("tier_policy_version")
            if (
                signal.source.strip() == "fused_forecast"
                and isinstance(policy_version, str)
                and policy_version
                and policy_version not in self._tier_policy_epochs_seen
            ):
                self._conn.execute(
                    "INSERT OR IGNORE INTO tier_policy_epochs("
                    "policy_version,first_signal_id,started_at) VALUES (?,?,?)",
                    (policy_version, int(cursor.lastrowid), ingested_at),
                )
                self._tier_policy_epochs_seen.add(policy_version)
            accepted.append(True)
        self._retry_on_locked(self._conn.commit)
        return accepted

    _FORWARD_REGISTRATIONS_PATH = (
        Path(__file__).resolve().parents[1]
        / "runtime" / "autonomy" / "promotion_forward_registrations.json"
    )

    def _forward_candidate_fingerprints(self) -> tuple[dict[str, str], frozenset[str]]:
        """Registered scope -> fingerprint, refreshed when the file changes.

        Stamping is provenance annotation only: auto-promotion refuses forward
        credit unless the signal's fingerprint matches an immutable
        registration made strictly BEFORE the signal existed, so a stamp can
        start an evidence clock but can never promote anything by itself. A
        missing or malformed registrations file means no stamping.
        """
        path = self._FORWARD_REGISTRATIONS_PATH
        try:
            mtime = path.stat().st_mtime_ns
        except OSError:
            return {}, frozenset()
        cached = getattr(self, "_forward_fp_cache", None)
        if cached is not None and cached[0] == mtime:
            return cached[1], cached[2]
        fingerprints: dict[str, str] = {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}, frozenset()
        entries = raw.get("registrations") if isinstance(raw, dict) else None
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            scope = str(entry.get("scope") or "")
            fingerprint = str(entry.get("candidate_fingerprint") or "").lower()
            if len(scope.split("|")) == 4 and len(fingerprint) == 64:
                fingerprints[scope] = fingerprint
        sources = frozenset(scope.split("|", 1)[0] for scope in fingerprints)
        self._forward_fp_cache = (mtime, fingerprints, sources)
        return fingerprints, sources

    def _stamp_forward_fingerprint(
        self, signal: Signal, fingerprints: dict[str, str],
    ) -> None:
        from autonomy.taxonomy import grading_scope

        if not isinstance(signal.features, dict):
            return
        if "promotion_candidate_fingerprint" in signal.features:
            return
        scope = grading_scope(signal.source, signal.market_ticker, signal.features)
        fingerprint = fingerprints.get(scope)
        if fingerprint:
            signal.features["promotion_candidate_fingerprint"] = fingerprint

    def record_signal(self, signal: Signal, mode: str = "live") -> bool:
        return self.record_signals([signal], mode=mode)[0]

    def record_decision(self, decision: Decision) -> None:
        canonical_tier_score = decision.tier_score
        current_tier_policy = False
        if str(decision.forecast.market_ticker) != str(decision.market_ticker):
            raise ValueError(
                "decision and forecast market identity must match for "
                f"{decision.decision_id}"
            )
        if decision.tier_policy_version:
            from autonomy.tier_policy import (
                TIER_POLICY_VERSION,
                tier_snapshot_is_valid,
            )

            if decision.tier_policy_version == TIER_POLICY_VERSION:
                current_tier_policy = True
                snapshot = decision.tier_snapshot or {}
                snapshot_score = snapshot.get("tier_score")
                score_matches = (
                    snapshot_score is None and decision.tier_score is None
                ) or (
                    snapshot_score is not None
                    and decision.tier_score is not None
                    and math.isclose(
                        float(snapshot_score),
                        float(decision.tier_score),
                        abs_tol=1e-6,
                    )
                )
                if (
                    not tier_snapshot_is_valid(
                        snapshot, ticker=decision.market_ticker
                    )
                    or snapshot.get("tier") != decision.tier_label
                    or not score_matches
                    or str(snapshot.get("tier_reason") or "")
                    != str(decision.tier_reason or "")
                ):
                    raise ValueError(
                        "decision tier attribution is not a valid current-policy "
                        f"snapshot for {decision.decision_id}"
                    )
                snapshot_side = str(snapshot["tier_side"])
                win_probability = (
                    float(decision.forecast.probability_yes)
                    if snapshot_side == "yes"
                    else 1.0 - float(decision.forecast.probability_yes)
                )
                expected_gross = (
                    win_probability
                    - float(snapshot["tier_entry_price_cents"]) / 100.0
                )
                if (
                    not math.isclose(
                        float(snapshot["tier_uncertainty"]),
                        float(decision.forecast.uncertainty),
                        abs_tol=1e-6,
                    )
                    or not math.isclose(
                        float(snapshot["tier_gross_executable_edge"]),
                        expected_gross,
                        abs_tol=1e-6,
                    )
                ):
                    raise ValueError(
                        "decision forecast does not match its frozen tier snapshot for "
                        f"{decision.decision_id}"
                    )
                canonical_tier_score = _canonical_tier_score(snapshot_score)
                if (
                    decision.tier_label in {"A", "B", "C"}
                    and decision.action.value != "ABSTAIN"
                ):
                    expected_action = (
                        "BUY_YES"
                        if snapshot.get("tier_side") == "yes"
                        else "BUY_NO"
                    )
                    if (
                        decision.side != snapshot.get("tier_side")
                        or decision.action.value != expected_action
                    ):
                        raise ValueError(
                            "decision action does not match its tier value side for "
                            f"{decision.decision_id}"
                        )
        recorded_at = _now()
        tier_snapshot = json.dumps(
            decision.tier_snapshot or {},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        tier_digest = hashlib.sha256(tier_snapshot.encode("utf-8")).hexdigest()
        sources_used = json.dumps(decision.forecast.sources_used, sort_keys=True)
        abstain_reason = decision.abstain_reason or ""
        tier_reason = decision.tier_reason or ""
        decision_row = (
            decision.decision_id,
            decision.market_ticker,
            decision.action.value,
            decision.side,
            decision.price_cents,
            decision.count,
            decision.ev_cents_per_contract,
            decision.kelly_fraction,
            decision.notional_cents,
            decision.forecast.probability_yes,
            decision.forecast.uncertainty,
            decision.forecast.market_implied_yes,
            sources_used,
            abstain_reason,
            decision.created_at,
            decision.tier_label,
            decision.tier_policy_version,
            canonical_tier_score,
            tier_reason,
        )
        existing_decision = self._conn.execute(
            "SELECT decision_id,market_ticker,action,side,price_cents,count,"
            "ev_cents,kelly,notional_cents,probability_yes,forecast_uncertainty,"
            "market_implied_yes,sources_used,abstain_reason,created_at,tier_label,"
            "tier_policy_version,tier_score,tier_reason FROM decisions WHERE decision_id=?",
            (decision.decision_id,),
        ).fetchone()
        existing = self._conn.execute(
            "SELECT policy_version,tier_label,tier_score,tier_reason,assigned_at,"
            " snapshot_json,snapshot_sha256 FROM decision_tier_attribution"
            " WHERE decision_id=?",
            (decision.decision_id,),
        ).fetchone()
        if existing is not None and not decision.tier_policy_version:
            raise ValueError(
                "decision tier attribution cannot be removed for "
                f"{decision.decision_id}"
            )
        if (
            existing_decision is not None
            and existing is None
            and decision.tier_policy_version
        ):
            raise ValueError(
                "decision tier attribution cannot be added retroactively for "
                f"{decision.decision_id}"
            )
        if decision.tier_policy_version:
            candidate = (
                decision.tier_policy_version,
                decision.tier_label,
                canonical_tier_score,
                tier_reason,
                decision.created_at,
                tier_snapshot,
                tier_digest,
            )
            attribution_matches = (
                _rows_match_with_canonical_score(
                    existing, candidate, score_index=2
                )
                if existing is not None and current_tier_policy
                else tuple(existing) == candidate
                if existing is not None
                else True
            )
            if not attribution_matches:
                raise ValueError(
                    "decision tier attribution is immutable for "
                    f"{decision.decision_id}"
                )
        if existing_decision is not None:
            decision_matches = (
                _rows_match_with_canonical_score(
                    existing_decision, decision_row, score_index=17
                )
                if current_tier_policy
                else tuple(existing_decision) == decision_row
            )
            if not decision_matches:
                raise ValueError(
                    "decision record is immutable for "
                    f"{decision.decision_id}"
                )
            # Exact replay is idempotent.  Do not use REPLACE here: even an
            # equivalent replacement deletes and reinserts the physical row,
            # which changes its rowid and can break audit/foreign-key identity.
            return
        self._conn.execute(
            "INSERT INTO decisions(decision_id, market_ticker, action, side, price_cents, count,"
            " ev_cents, kelly, notional_cents, probability_yes, forecast_uncertainty, market_implied_yes,"
            " sources_used, abstain_reason, created_at, tier_label, tier_policy_version, tier_score, tier_reason)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            decision_row,
        )
        if decision.tier_policy_version and existing is None:
            self._conn.execute(
                "INSERT INTO decision_tier_attribution("
                "decision_id,policy_version,tier_label,tier_score,tier_reason,assigned_at,"
                "recorded_at,snapshot_json,snapshot_sha256) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    decision.decision_id,
                    decision.tier_policy_version,
                    decision.tier_label,
                    canonical_tier_score,
                    tier_reason,
                    decision.created_at,
                    recorded_at,
                    tier_snapshot,
                    tier_digest,
                ),
            )
        self._retry_on_locked(self._conn.commit)

    def record_outcome(self, outcome: TradeOutcome) -> None:
        decision_market = self._conn.execute(
            "SELECT market_ticker FROM decisions WHERE decision_id=?",
            (outcome.decision_id,),
        ).fetchone()
        if (
            decision_market is not None
            and str(decision_market[0]) != str(outcome.market_ticker)
        ):
            raise ValueError(
                "outcome and decision market identity must match for "
                f"{outcome.decision_id}"
            )
        self._conn.execute(
            "INSERT INTO outcomes(decision_id, market_ticker, kind, order_id, fill_count, fill_price_cents,"
            " pnl_cents, broker_contacted, detail, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                outcome.decision_id, outcome.market_ticker, outcome.kind.value, outcome.order_id,
                outcome.fill_count, outcome.fill_price_cents, outcome.pnl_cents,
                1 if outcome.broker_contacted else 0, json.dumps(outcome.detail, sort_keys=True, default=str),
                outcome.created_at,
            ),
        )
        self._retry_on_locked(self._conn.commit)

    def settlement_result(self, market_ticker: str) -> bool | None:
        row = self._conn.execute(
            "SELECT result_yes FROM settlements WHERE market_ticker=?", (market_ticker,)
        ).fetchone()
        return None if row is None else bool(row[0])

    def record_settlement(
        self,
        market_ticker: str,
        result_yes: bool,
        *,
        settled_at: str | None = None,
        source: str | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        """Record one immutable canonical settlement fact.

        An exact replay is a no-op rather than a physical row replacement.
        Optional provenance omitted on a replay means "use the already frozen
        value"; an explicitly supplied conflicting result, timestamp, source,
        or evidence packet is rejected.  This preserves compatibility with the
        legacy two-argument callers without allowing them to mutate richer
        canonical evidence written by a provenance-aware caller.
        """
        ticker = str(market_ticker)
        result = 1 if result_yes else 0
        if settled_at is not None and not str(settled_at).strip():
            raise ValueError("settled_at must be a non-empty timestamp")
        if source is not None and not isinstance(source, str):
            raise TypeError("settlement source must be a string")
        if evidence is not None and not isinstance(evidence, dict):
            raise TypeError("settlement evidence must be a mapping")
        evidence_json = (
            None
            if evidence is None
            else json.dumps(
                evidence,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        )

        existing = self._conn.execute(
            "SELECT s.result_yes,s.settled_at,COALESCE(p.source,''),"
            " COALESCE(p.evidence,'{}') FROM settlements s"
            " LEFT JOIN settlement_provenance p USING(market_ticker)"
            " WHERE s.market_ticker=?",
            (ticker,),
        ).fetchone()
        if existing is not None:
            candidate = (
                result,
                str(existing[1]) if settled_at is None else str(settled_at),
                str(existing[2]) if source is None else source,
                str(existing[3]) if evidence_json is None else evidence_json,
            )
            if tuple(existing) != candidate:
                raise ValueError(f"settlement record is immutable for {ticker}")
            return

        self._conn.execute(
            "INSERT INTO settlements(market_ticker,result_yes,settled_at)"
            " VALUES (?,?,?)",
            (
                ticker,
                result,
                str(settled_at) if settled_at is not None else _now(),
            ),
        )
        self._conn.execute(
            "INSERT INTO settlement_provenance(market_ticker,source,evidence)"
            " VALUES (?,?,?)",
            (
                ticker,
                source or "",
                evidence_json if evidence_json is not None else "{}",
            ),
        )
        self._retry_on_locked(self._conn.commit)

    def record_bankroll(self, bankroll_cents: int, open_exposure_cents: int, stage: int) -> None:
        self._conn.execute(
            "INSERT INTO bankroll_curve(bankroll_cents, open_exposure_cents, stage, created_at) VALUES (?,?,?,?)",
            (bankroll_cents, open_exposure_cents, stage, _now()),
        )
        self._retry_on_locked(self._conn.commit)

    def record_lesson(self, scope: str, lesson: str, evidence: dict[str, Any] | None = None) -> None:
        self._conn.execute(
            "INSERT INTO lessons(scope, lesson, evidence, created_at) VALUES (?,?,?,?)",
            (scope, lesson[:2000], json.dumps(evidence or {}, sort_keys=True, default=str), _now()),
        )
        self._retry_on_locked(self._conn.commit)

    def record_external_observation(
        self,
        *,
        source: str,
        series_id: str,
        observed_at: str,
        value: float,
        unit: str,
        published_at: str | None = None,
        features: dict[str, Any] | None = None,
    ) -> bool:
        """Store a deduplicated raw statistic without turning it into a forecast."""
        if not source.strip() or not series_id.strip() or not unit.strip():
            raise ValueError("source, series_id, and unit are required")
        parsed_value = float(value)
        if not math.isfinite(parsed_value):
            raise ValueError("external observation value must be finite")
        observed = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
        if observed.tzinfo is None:
            raise ValueError("observed_at must include a timezone")
        if published_at is not None:
            published = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
            if published.tzinfo is None:
                raise ValueError("published_at must include a timezone")
        payload = json.dumps(
            features or {}, sort_keys=True, separators=(",", ":"), allow_nan=False,
        )
        observed_iso = observed.astimezone(timezone.utc).isoformat()
        published_iso = None
        if published_at is not None:
            published_iso = published.astimezone(timezone.utc).isoformat()
        observation_id = _external_observation_id(
            source.strip(), series_id.strip(), observed_iso, published_iso,
            parsed_value, unit.strip(),
        )
        cursor = self._conn.execute(
            "INSERT OR IGNORE INTO external_observations(observation_id, source, series_id,"
            " observed_at, published_at, value, unit, features, ingested_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (
                observation_id, source.strip(), series_id.strip(), observed_iso,
                published_iso, parsed_value, unit.strip(), payload, _now(),
            ),
        )
        self._retry_on_locked(self._conn.commit)
        return cursor.rowcount > 0

    def external_observation_summary(self) -> dict[str, Any]:
        rows = self._conn.execute(
            "SELECT source, COUNT(*), MAX(observed_at), MAX(ingested_at)"
            " FROM external_observations GROUP BY source ORDER BY source"
        ).fetchall()
        return {
            "total_observations": sum(int(row[1]) for row in rows),
            "sources": {
                str(source): {
                    "observations": int(count),
                    "latest_observed_at": latest_observed,
                    "latest_ingested_at": latest_ingested,
                }
                for source, count, latest_observed, latest_ingested in rows
            },
        }

    # ------------------------------------------------------------------
    # Trust weights are updated only from realized outcomes.
    # ------------------------------------------------------------------

    def get_weight(self, source: str, default: float = 1.0) -> float:
        row = self._conn.execute("SELECT weight FROM source_trust WHERE source=?", (source,)).fetchone()
        return float(row[0]) if row else default

    def get_weight_scoped(self, source: str, vertical: str) -> float:
        """Vertical-scoped trust when earned, else the source's global weight.

        Scoped rows use the key convention 'source@VERTICAL'. A source can be
        an authority on crypto and a fish on weather; fusion should know.
        """
        row = self._conn.execute(
            "SELECT weight FROM source_trust WHERE source=?", (f"{source}@{vertical}",)
        ).fetchone()
        if row:
            return float(row[0])
        return self.get_weight(source)

    def get_weight_for_signal(
        self,
        source: str,
        vertical: str,
        ticker: str,
        features: dict[str, Any] | None = None,
    ) -> float:
        """Most-specific earned trust: exact scope -> vertical -> global.

        Exact-scope rows are created only from settled outcomes (online by the
        learner, or explicitly via ``backtest --bootstrap``).  A new/sparse
        scope therefore falls back to the established vertical behavior.
        """
        from autonomy.taxonomy import scope_weight_key

        row = self._conn.execute(
            "SELECT weight FROM source_trust WHERE source=?",
            (scope_weight_key(source, ticker, features or {}),),
        ).fetchone()
        if row:
            return float(row[0])
        return self.get_weight_scoped(source, vertical)

    def all_weights(self) -> dict[str, float]:
        return {r[0]: float(r[1]) for r in self._conn.execute("SELECT source, weight FROM source_trust")}

    def trust_rows(self) -> list[dict[str, Any]]:
        return [
            {"source": str(source), "weight": float(weight), "updated_at": str(updated_at)}
            for source, weight, updated_at in self._conn.execute(
                "SELECT source,weight,updated_at FROM source_trust"
            )
        ]

    def update_weight(self, source: str, weight: float, brier: float | None = None) -> None:
        row = self._conn.execute(
            "SELECT brier_sum, brier_count FROM source_trust WHERE source=?", (source,)
        ).fetchone()
        brier_sum, brier_count = (float(row[0]), int(row[1])) if row else (0.0, 0)
        if brier is not None:
            brier_sum += brier
            brier_count += 1
        self._conn.execute(
            "INSERT OR REPLACE INTO source_trust(source, weight, brier_sum, brier_count, updated_at)"
            " VALUES (?,?,?,?,?)",
            (source, weight, brier_sum, brier_count, _now()),
        )
        self._retry_on_locked(self._conn.commit)

    # ------------------------------------------------------------------
    # Queries for the learner / status surface
    # ------------------------------------------------------------------

    def open_decisions(self, scope: str | None = None) -> list[dict[str, Any]]:
        """Active orders plus filled, unsettled positions.

        ``filled_count`` is the largest transport/simulator-confirmed fill seen
        for the decision. Active orders reserve their submitted size and limit;
        filled positions use the witnessed cumulative fill size and weighted
        price. The original decision terms remain available under explicit
        ``decision_*`` keys for audit, never as execution truth.
        """
        scope_clause = ""
        if scope == "shadow":
            scope_clause = "AND a.is_shadow = 1"
        elif scope == "live":
            scope_clause = "AND a.is_live = 1 AND a.is_shadow = 0"
        rows = self._conn.execute(
            f"""
            WITH latest AS (
                SELECT o.* FROM outcomes o
                WHERE o.id = (SELECT MAX(o2.id) FROM outcomes o2
                              WHERE o2.decision_id = o.decision_id)
            ), initial AS (
                SELECT o.* FROM outcomes o
                WHERE o.id = (SELECT MIN(o2.id) FROM outcomes o2
                              WHERE o2.decision_id=o.decision_id
                                AND o2.kind IN ('SHADOW','ACCEPTED'))
            ), aggregate_state AS (
                SELECT decision_id,
                       MAX(CASE WHEN kind IN ('SHADOW','ACCEPTED','PARTIALLY_FILLED',
                                              'FILLED','CANCELED','EXPIRED')
                                THEN fill_count ELSE 0 END) AS filled_count,
                       MAX(CASE WHEN kind = 'SHADOW' THEN 1 ELSE 0 END) AS is_shadow,
                       MAX(broker_contacted) AS is_live,
                       MAX(CASE WHEN kind IN ('SETTLED_WIN','SETTLED_LOSS') THEN 1 ELSE 0 END)
                           AS is_settled
                FROM outcomes GROUP BY decision_id
            ), witnessed_fill AS (
                SELECT o.* FROM outcomes o
                WHERE o.fill_count > 0 AND o.fill_price_cents IS NOT NULL
                  AND o.id = (
                      SELECT o2.id FROM outcomes o2
                      WHERE o2.decision_id = o.decision_id
                        AND o2.fill_count > 0
                        AND o2.fill_price_cents IS NOT NULL
                      ORDER BY o2.fill_count DESC, o2.id DESC
                      LIMIT 1
                  )
            )
            SELECT d.decision_id, d.market_ticker, d.side,
                   d.price_cents, d.count,
                   l.kind, l.order_id, a.filled_count,
                   CASE WHEN l.kind IN ('ACCEPTED','PARTIALLY_FILLED','SHADOW')
                        THEN 1 ELSE 0 END AS order_active,
                   CASE WHEN l.kind IN ('ACCEPTED','PARTIALLY_FILLED','SHADOW')
                        THEN d.count ELSE a.filled_count END AS reserved_count,
                    d.created_at,
                    CASE WHEN a.is_shadow = 1 THEN 'shadow' ELSE 'live' END AS book_scope,
                    i.fill_price_cents, i.detail,
                    w.fill_price_cents, w.detail
            FROM decisions d
            JOIN latest l ON l.decision_id = d.decision_id
            LEFT JOIN initial i ON i.decision_id = d.decision_id
            LEFT JOIN witnessed_fill w ON w.decision_id = d.decision_id
            JOIN aggregate_state a ON a.decision_id = d.decision_id
            WHERE a.is_settled = 0
              AND (l.kind IN ('ACCEPTED','PARTIALLY_FILLED','SHADOW') OR a.filled_count > 0)
              {scope_clause}
            """
        ).fetchall()
        keys = [
            "decision_id", "market_ticker", "side", "decision_price_cents",
            "decision_count", "kind",
            "order_id", "filled_count", "order_active", "reserved_count", "created_at",
            "book_scope", "initial_outcome_price_cents", "submission_detail",
            "witnessed_fill_price_cents", "witnessed_fill_detail",
        ]
        records = [dict(zip(keys, r)) for r in rows]
        for record in records:
            try:
                record["submission_detail"] = json.loads(record["submission_detail"] or "{}")
            except Exception:
                record["submission_detail"] = {}
            try:
                record["witnessed_fill_detail"] = json.loads(
                    record["witnessed_fill_detail"] or "{}"
                )
            except Exception:
                record["witnessed_fill_detail"] = {}

            submission = record["submission_detail"]
            witnessed = record["witnessed_fill_detail"]
            try:
                submitted_price = int(submission.get("submitted_price_cents"))
            except (TypeError, ValueError):
                submitted_price = int(
                    record["initial_outcome_price_cents"]
                    if record["initial_outcome_price_cents"] is not None
                    else record["decision_price_cents"]
                )
            if not (1 <= submitted_price <= 99):
                submitted_price = int(record["decision_price_cents"])
            try:
                submitted_count = int(submission.get("submitted_count"))
            except (TypeError, ValueError):
                submitted_count = int(record["decision_count"])
            if submitted_count < 1:
                submitted_count = int(record["decision_count"])

            filled_count = int(record["filled_count"] or 0)
            witnessed_price = record["witnessed_fill_price_cents"]
            if filled_count > 0 and witnessed_price is not None:
                effective_price = int(witnessed_price)
                fill_price: int | None = effective_price
            elif filled_count > 0:
                # A positive fill count is the position witness. Older rows may
                # lack an independent broker price, so use the submitted limit
                # rather than the stale forecasting decision.
                effective_price = submitted_price
                fill_price = submitted_price
            else:
                effective_price = submitted_price
                fill_price = None

            role = str(
                witnessed.get("liquidity_role")
                or submission.get("liquidity_role")
                or submission.get("submitted_liquidity_role")
                or ""
            ).lower()
            if role not in {"maker", "taker", "mixed"}:
                note = str(submission.get("note") or "").lower()
                role = "taker" if "taker" in note else "maker"

            try:
                submitted_notional = int(submission.get("submitted_notional_cents"))
            except (TypeError, ValueError):
                submitted_notional = submitted_price * submitted_count
            if submitted_notional < 1:
                submitted_notional = submitted_price * submitted_count

            # Active partially filled orders reserve the witnessed cost of the
            # filled slice plus the submitted LIMIT for every unfilled contract.
            # Multiplying the improved fill price by the full order count would
            # under-reserve the remainder exactly when the book moves.
            remaining_count = max(0, submitted_count - filled_count)
            try:
                witnessed_fill_cost = int(witnessed.get("fill_cost_cents"))
            except (TypeError, ValueError):
                witnessed_fill_cost = effective_price * filled_count
            if witnessed_fill_cost < 0:
                witnessed_fill_cost = effective_price * filled_count
            if record["order_active"]:
                reserved_notional = witnessed_fill_cost + submitted_price * remaining_count
            else:
                reserved_notional = witnessed_fill_cost

            record.update({
                "price_cents": effective_price,
                "count": submitted_count,
                "submitted_price_cents": submitted_price,
                "submitted_count": submitted_count,
                "submitted_notional_cents": submitted_notional,
                "fill_price_cents": fill_price,
                "liquidity_role": role,
                "reserved_count": (
                    submitted_count if record["order_active"] else filled_count
                ),
                "reserved_notional_cents": reserved_notional,
                "execution_fee_cents": witnessed.get("execution_fee_cents"),
                "fill_cost_cents": witnessed.get("fill_cost_cents"),
            })
        return records

    def signals_for_market(self, market_ticker: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT source, probability_yes, uncertainty, created_at"
            " FROM signal_history WHERE market_ticker=?",
            (market_ticker,),
        ).fetchall()
        return [
            {"source": r[0], "probability_yes": r[1], "uncertainty": r[2], "created_at": r[3]} for r in rows
        ]

    def calibration_signals_for_market(
        self, market_ticker: str, *, evidence_mode: str = "live",
    ) -> list[dict[str, Any]]:
        """Return point-in-time source opinions from one provenance lane.

        ``evidence_mode='live'`` is the authoritative trust/readiness lane. A
        row is eligible only when *both* its claimed creation time and its
        durable ledger receipt time were no later than Dummy's earliest
        decision (or the settlement time for a phantom-only forecast). This
        receipt-time bound prevents a backdated or late-arriving row from
        acquiring hindsight authority.

        ``evidence_mode='retro'`` is historical-replay evidence. It remains
        separately queryable for research, but callers must never mix it into
        live trust or readiness. Retro rows retain the model-time cutoff while
        intentionally omitting the receipt cutoff because replay is ingested
        after the historical event by construction.
        """
        if evidence_mode not in {"live", "retro"}:
            raise ValueError("evidence_mode must be 'live' or 'retro'")
        decision_time, settled_at = self._conn.execute(
            """
            SELECT
                (SELECT MIN(created_at) FROM decisions WHERE market_ticker=?),
                (SELECT settled_at FROM settlements WHERE market_ticker=?)
            """,
            (market_ticker, market_ticker),
        ).fetchone()
        # An unsettled phantom has no outcome to grade. ``now`` preserves the
        # method's historical inspection utility without granting future rows.
        cutoff = decision_time or settled_at or _now()
        receipt_clause = (
            " AND julianday(ingested_at)<=julianday(?)"
            if evidence_mode == "live" else ""
        )
        params: list[Any] = [market_ticker, evidence_mode, cutoff]
        if evidence_mode == "live":
            params.append(cutoff)
        rows = self._conn.execute(
            """
            SELECT source, probability_yes, uncertainty, created_at, features,
                   mode, ingested_at, id
            FROM signal_history
            WHERE market_ticker=? AND mode=?
              AND julianday(created_at)<=julianday(?)
            """ + receipt_clause + " ORDER BY id",
            params,
        ).fetchall()
        chosen: dict[str, tuple[Any, ...]] = {}
        for row in rows:
            source = str(row[0])
            if decision_time:
                chosen[source] = row  # latest available at/before decision
            else:
                chosen.setdefault(source, row)  # earliest phantom opinion
        return [
            {"source": row[0], "probability_yes": row[1], "uncertainty": row[2],
             "created_at": row[3], "features": _loads_features(row[4]),
             "mode": row[5], "ingested_at": row[6]}
            for row in chosen.values()
        ]

    def calibration_signals_for_settled(
        self, tickers: Iterable[str], *, evidence_mode: str = "live",
    ) -> dict[str, list[dict[str, Any]]]:
        """Return one point-in-time provenance lane for settled markets.

        The implementation delegates to the multi-lane batch so callers that
        need both live and retro evidence can scan ``signal_history`` once.
        """
        return self.calibration_signals_for_settled_by_mode(
            tickers, evidence_modes=(evidence_mode,),
        )[evidence_mode]

    def calibration_signals_for_settled_by_mode(
        self,
        tickers: Iterable[str],
        *,
        evidence_modes: Iterable[str] = ("live", "retro"),
    ) -> dict[str, dict[str, list[dict[str, Any]]]]:
        """Batch point-in-time source opinions for multiple provenance lanes.

        The backtester called the per-market version once per settled market:
        with ~177k settlements that is ~354k round-trips (a decision-time probe
        plus a signal_history scan each) against the 12M-row union view -- the
        6-hourly recalibration's dominant cost. A full report then called the
        one-lane batch twice, scanning the same hot/archive union once for live
        evidence and again for retro evidence. This method returns the identical
        selection for every requested lane in one joined scan.

        Live rows are bounded by both model time and durable receipt time;
        retro rows are model-time bounded and remain research-only. Ordering by
        ``id`` in the per-market SQL is reproduced by keeping the max id
        (traded window) or min id (phantom) per source.
        """
        modes = tuple(dict.fromkeys(str(mode) for mode in evidence_modes))
        if not modes or any(mode not in {"live", "retro"} for mode in modes):
            raise ValueError("evidence_modes must contain 'live' and/or 'retro'")
        want = {str(ticker) for ticker in tickers}
        if not want:
            return {mode: {} for mode in modes}
        # First pass carries keys only. Pulling probability, uncertainty, and
        # especially the JSON features blob for every one of ~10M eligible rows
        # made the Python/SQLite boundary the dominant full-report cost even
        # after the old N+1 was removed. Keep only the chosen physical row id,
        # then fetch full payloads by INTEGER PRIMARY KEY below.
        #
        # mode -> ticker -> source -> (id, physical_store); traded keeps max id
        # in-window, phantom keeps min id -- matching the per-market ORDER BY id
        # semantics without ever merging provenance lanes.
        acc: dict[
            str, dict[str, dict[str, tuple[int, str]]]
        ] = {mode: {} for mode in modes}
        placeholders = ",".join("?" for _mode in modes)
        attached = {
            str(row[1]) for row in self._conn.execute("PRAGMA database_list")
        }
        stores = ["main"]
        if "signal_archive" in attached:
            stores.append("signal_archive")

        branch_sql: list[str] = []
        query_params: list[Any] = []
        for store in stores:
            receipt_clause = (
                " AND (sh.mode!='live' OR julianday(sh.ingested_at)"
                " <=julianday(COALESCE(ed.decision_time,s.settled_at)))"
                if "live" in modes else ""
            )
            branch_sql.append(
                f"""
                SELECT '{store}' AS physical_store,sh.market_ticker,sh.id,
                       sh.source,sh.mode,ed.decision_time
                FROM {store}.signals sh
                JOIN main.settlements s ON s.market_ticker=sh.market_ticker
                LEFT JOIN earliest_decision ed
                  ON ed.market_ticker=sh.market_ticker
                WHERE sh.mode IN ({placeholders})
                  AND julianday(sh.created_at)
                      <=julianday(COALESCE(ed.decision_time,s.settled_at))
                """ + receipt_clause
            )
            query_params.extend(modes)
        query = """
            WITH earliest_decision AS (
                SELECT market_ticker, MIN(created_at) AS decision_time
                FROM decisions GROUP BY market_ticker
            )
            """ + " UNION ALL ".join(branch_sql)
        for store, mt, rid, source, mode, dt in self._conn.execute(
            query, query_params,
        ):
            mt = str(mt)
            if mt not in want:
                continue
            mode = str(mode)
            src = str(source)
            bucket = acc[mode].setdefault(mt, {})
            prev = bucket.get(src)
            if dt is not None:
                # SQL already enforced model/receipt availability at decision.
                if prev is None or rid > prev[0]:
                    bucket[src] = (int(rid), str(store))
            else:
                # earliest phantom opinion (min id)
                if prev is None or rid < prev[0]:
                    bucket[src] = (int(rid), str(store))

        chosen = {
            (store, rid)
            for mode_buckets in acc.values()
            for source_buckets in mode_buckets.values()
            for rid, store in source_buckets.values()
        }
        results: dict[str, dict[str, list[dict[str, Any]]]] = {
            mode: {} for mode in modes
        }
        if not chosen:
            return results

        table = "temp.backtest_chosen_signal_ids"
        self._conn.execute(
            f"CREATE TEMP TABLE IF NOT EXISTS {table}("
            "physical_store TEXT NOT NULL,id INTEGER NOT NULL,"
            "PRIMARY KEY(physical_store,id)) WITHOUT ROWID"
        )
        self._conn.execute(f"DELETE FROM {table}")
        try:
            self._conn.executemany(
                f"INSERT INTO {table}(physical_store,id) VALUES (?,?)",
                sorted(chosen),
            )
            detail_branches = [
                f"""
                SELECT sh.source,sh.market_ticker,sh.probability_yes,
                       sh.uncertainty,sh.created_at,sh.features,sh.mode,
                       sh.ingested_at
                FROM {table} chosen
                CROSS JOIN {store}.signals sh
                WHERE chosen.physical_store=? AND sh.id=chosen.id
                """
                for store in stores
            ]
            for source, mt, prob, unc, created, feat, mode, ingested in self._conn.execute(
                " UNION ALL ".join(detail_branches), stores,
            ):
                results[str(mode)].setdefault(str(mt), []).append({
                    "source": source,
                    "probability_yes": prob,
                    "uncertainty": unc,
                    "created_at": created,
                    "features": _loads_features(feat),
                    "mode": mode,
                    "ingested_at": ingested,
                })
        finally:
            self._conn.execute(f"DELETE FROM {table}")
        return results

    def unsettled_traded_markets(self) -> list[str]:
        rows = self._conn.execute(
            """
            SELECT DISTINCT d.market_ticker FROM decisions d
            WHERE d.action != 'ABSTAIN'
              AND d.market_ticker NOT IN (SELECT market_ticker FROM settlements)
            """
        ).fetchall()
        return [r[0] for r in rows]

    def unsettled_forecast_markets(self, max_age_days: float = 7.0) -> list[str]:
        """Every market we recently opined on that has no settlement yet.

        This is the phantom-grading feed: calibration evidence comes from every
        forecast the machine makes, not just the handful it traded. Bounded by
        signal age so the set can't grow without limit.

        Reads the hot ``signals`` table, NOT the ``signal_history`` union view:
        retention only archives rows of markets settled past the retention
        window, so an unsettled recent market's signals are always hot. The
        view variant scanned the multi-million-row archive for rows that could
        never match — the 2026-07-24 4.5-hour wedged query.
        """
        from datetime import timedelta

        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
        rows = self._conn.execute(
            """
            SELECT DISTINCT s.market_ticker FROM signals s
            WHERE s.created_at >= ?
              AND NOT EXISTS (
                SELECT 1 FROM settlements st WHERE st.market_ticker = s.market_ticker
              )
            """,
            (cutoff,),
        ).fetchall()
        return [r[0] for r in rows]

    def evidence_split(self) -> dict[str, int]:
        """Settled-market counts by evidence provenance (live shadow vs retro).

        One JOIN+GROUP pass over signal_history instead of correlated EXISTS
        subqueries evaluated once per settlement (~180k x 2 lookups over the
        12M-row union view -- part of the recalibration's residual cost).
        """
        row = self._conn.execute(
            """
            SELECT
              COALESCE(SUM(has_live), 0),
              COALESCE(SUM(CASE WHEN has_live = 0 AND has_retro = 1 THEN 1 ELSE 0 END), 0)
            FROM (
              SELECT MAX(CASE WHEN s.mode = 'live' THEN 1 ELSE 0 END) AS has_live,
                     MAX(CASE WHEN s.mode = 'retro' THEN 1 ELSE 0 END) AS has_retro
              FROM settlements st
              JOIN signal_history s ON s.market_ticker = st.market_ticker
              GROUP BY st.market_ticker
            )
            """
        ).fetchone()
        return {"live_settled": int(row[0]), "retro_settled": int(row[1])}

    def signal_quality_summary(self) -> dict[str, Any]:
        """Compact, decision-oriented profile of the statistical intake ledger."""
        totals = self._conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT market_ticker), COUNT(DISTINCT source),"
            " SUM(CASE WHEN ingest_version>=2 THEN 1 ELSE 0 END),"
            " SUM(CASE WHEN ingest_version>=2 AND features!='{}' THEN 1 ELSE 0 END),"
            " SUM(CASE WHEN probability_yes<0 OR probability_yes>1"
            "               OR uncertainty<0 OR uncertainty>0.5 THEN 1 ELSE 0 END),"
            " SUM(CASE WHEN julianday(created_at)>julianday('now','+5 minutes')"
            "          THEN 1 ELSE 0 END),"
            " AVG(CASE WHEN ingest_version>=2 AND mode='live'"
            "          THEN MAX(0,(julianday(ingested_at)-julianday(created_at))*86400.0)"
            "     END),"
            " MAX(CASE WHEN ingest_version>=2 AND mode='live'"
            "          THEN MAX(0,(julianday(ingested_at)-julianday(created_at))*86400.0)"
            "     END),"
            " SUM(CASE WHEN ingest_version>=2 AND mode='live' THEN 1 ELSE 0 END)"
            " FROM signal_history"
        ).fetchone()
        invalid_stored = int(totals[5] or 0)
        duplicate_groups = int(self._conn.execute(
            "SELECT COUNT(*) FROM (SELECT source,market_ticker,created_at,mode,COUNT(*) n"
            " FROM signal_history GROUP BY source,market_ticker,created_at,mode HAVING n>1)"
        ).fetchone()[0])
        future_rows = int(totals[6] or 0)
        post_settlement_rows = int(self._conn.execute(
            "SELECT COUNT(*) FROM signal_history s JOIN settlements st USING(market_ticker)"
            " WHERE julianday(s.created_at)>julianday(st.settled_at)"
        ).fetchone()[0])
        decisions_without_prior_signal = int(self._conn.execute(
            "SELECT COUNT(*) FROM decisions d LEFT JOIN ("
            " SELECT market_ticker,MIN(created_at) AS first_signal_at"
            " FROM signal_history GROUP BY market_ticker"
            ") first_signal ON first_signal.market_ticker=d.market_ticker"
            " WHERE first_signal.first_signal_at IS NULL"
            " OR first_signal.first_signal_at>d.created_at"
        ).fetchone()[0])
        rejection_total = int(self._conn.execute(
            "SELECT COUNT(*) FROM signal_rejections"
        ).fetchone()[0])
        rejection_reasons = {
            str(reason): int(count) for reason, count in self._conn.execute(
                "SELECT reason,COUNT(*) FROM signal_rejections GROUP BY reason ORDER BY COUNT(*) DESC"
            )
        }
        by_mode_counts: dict[str, int] = {}
        by_source_counts: dict[str, int] = {}
        for source, mode, count in self._conn.execute(
            "SELECT source,mode,COUNT(*) FROM signal_history GROUP BY source,mode"
        ):
            source = str(source)
            mode = str(mode)
            count = int(count)
            by_mode_counts[mode] = by_mode_counts.get(mode, 0) + count
            by_source_counts[source] = by_source_counts.get(source, 0) + count
        by_mode = dict(sorted(by_mode_counts.items()))
        by_source = dict(
            sorted(by_source_counts.items(), key=lambda item: (-item[1], item[0]))
        )
        receipt = totals[7:10]

        blocking_issues: list[str] = []
        if invalid_stored:
            blocking_issues.append(f"invalid stored signal rows: {invalid_stored}")
        if duplicate_groups:
            blocking_issues.append(f"duplicate signal grains: {duplicate_groups}")
        if future_rows:
            blocking_issues.append(f"future-dated signal rows: {future_rows}")
        if decisions_without_prior_signal:
            blocking_issues.append(
                f"decisions without point-in-time signals: {decisions_without_prior_signal}"
            )

        warnings: list[str] = []
        current_rows = int(totals[3] or 0)
        feature_rows = int(totals[4] or 0)
        historical_rows = int(totals[0] or 0) - current_rows
        if historical_rows:
            warnings.append(
                f"{historical_rows} historical signals predate receipt-time/feature provenance"
            )
        if current_rows and feature_rows < current_rows:
            warnings.append(
                f"{current_rows - feature_rows} current-version signals have no feature payload"
            )
        if post_settlement_rows:
            warnings.append(
                f"{post_settlement_rows} post-settlement signals are retained but excluded by point-in-time grading"
            )
        if rejection_total:
            warnings.append(f"{rejection_total} malformed or duplicate signals quarantined")

        return {
            "status": "FAIL" if blocking_issues else ("WARN" if warnings else "PASS"),
            "signals_stored": int(totals[0] or 0),
            "markets_covered": int(totals[1] or 0),
            "sources_covered": int(totals[2] or 0),
            "current_provenance_rows": current_rows,
            "historical_provenance_backfill_rows": historical_rows,
            "feature_payload_rows": feature_rows,
            "by_mode": by_mode,
            "by_source": by_source,
            "invalid_stored_rows": invalid_stored,
            "duplicate_grains": duplicate_groups,
            "future_dated_rows": future_rows,
            "post_settlement_rows": post_settlement_rows,
            "decisions_without_prior_signal": decisions_without_prior_signal,
            "quarantined_attempts": rejection_total,
            "quarantine_reasons": rejection_reasons,
            "live_receipt_latency_seconds": {
                "average": round(float(receipt[0]), 3) if receipt[0] is not None else None,
                "maximum": round(float(receipt[1]), 3) if receipt[1] is not None else None,
                "sample_rows": int(receipt[2] or 0),
            },
            "blocking_issues": blocking_issues,
            "warnings": warnings,
        }

    def execution_summary(self, scope: str | None = None) -> dict[str, Any]:
        """Fill-truth KPIs for maker execution and shadow simulation."""
        if scope not in {None, "shadow", "live"}:
            raise ValueError("execution scope must be None, 'shadow', or 'live'")
        scope_clause = ""
        if scope == "shadow":
            scope_clause = "WHERE p.is_shadow=1"
        elif scope == "live":
            scope_clause = "WHERE p.is_live=1 AND p.is_shadow=0"
        row = self._conn.execute(
            f"""
            WITH per_decision AS (
                SELECT decision_id,
                       MAX(CASE WHEN kind IN ('SHADOW','ACCEPTED') THEN 1 ELSE 0 END)
                           AS submitted,
                       MAX(CASE WHEN kind IN ('SHADOW','ACCEPTED','PARTIALLY_FILLED',
                                              'FILLED','CANCELED','EXPIRED')
                                THEN fill_count ELSE 0 END) AS filled_count,
                       MAX(CASE WHEN kind IN ('CANCELED','EXPIRED') THEN 1 ELSE 0 END)
                           AS terminal_unfilled,
                       MAX(CASE WHEN kind='SHADOW' THEN 1 ELSE 0 END) AS is_shadow,
                       MAX(broker_contacted) AS is_live
                FROM outcomes GROUP BY decision_id
            )
            SELECT COALESCE(SUM(submitted),0),
                   COALESCE(SUM(CASE WHEN filled_count > 0 THEN 1 ELSE 0 END),0),
                   COALESCE(SUM(CASE WHEN terminal_unfilled = 1 AND filled_count = 0
                                     THEN 1 ELSE 0 END),0),
                   COALESCE(SUM(CASE WHEN submitted=1 THEN COALESCE(d.count,1) ELSE 0 END),0),
                   COALESCE(SUM(filled_count),0),
                   COALESCE(SUM(CASE WHEN filled_count>0 AND filled_count<COALESCE(d.count,1)
                                     THEN 1 ELSE 0 END),0)
            FROM per_decision p LEFT JOIN decisions d USING(decision_id)
            {scope_clause}
            """
        ).fetchone()
        submitted, filled, expired_unfilled = (int(row[0]), int(row[1]), int(row[2]))
        contracts_submitted, contracts_filled, partial_orders = (
            int(row[3]), int(row[4]), int(row[5])
        )
        active = self.open_decisions(scope)
        pending = sum(1 for decision in active if decision.get("order_active"))
        open_filled = sum(1 for decision in active if int(decision.get("filled_count") or 0) > 0)
        latency_rows = self._conn.execute(
            """
            WITH submitted AS (
                SELECT decision_id, MIN(CASE WHEN kind IN ('SHADOW','ACCEPTED') THEN created_at END)
                           AS submitted_at,
                       MAX(CASE WHEN kind='SHADOW' THEN 1 ELSE 0 END) AS is_shadow,
                       MAX(broker_contacted) AS is_live
                FROM outcomes GROUP BY decision_id
            ), fills AS (
                SELECT o.* FROM outcomes o
                WHERE o.id = (
                    SELECT MIN(o2.id) FROM outcomes o2
                    WHERE o2.decision_id=o.decision_id AND o2.fill_count>0
                      AND o2.kind IN ('SHADOW','PARTIALLY_FILLED','FILLED','CANCELED')
                )
            )
            SELECT s.submitted_at,f.created_at,f.detail,s.is_shadow,s.is_live
            FROM submitted s JOIN fills f USING(decision_id)
            WHERE s.submitted_at IS NOT NULL
            """
        ).fetchall()
        latencies: list[float] = []
        fill_witness_reasons: dict[str, int] = {}
        precise_witness_times = 0
        scoped_filled_rows = 0
        for submitted_at, recorded_at, raw_detail, is_shadow, is_live in latency_rows:
            if not (scope is None or (scope == "shadow" and is_shadow)
                    or (scope == "live" and is_live and not is_shadow)):
                continue
            scoped_filled_rows += 1
            try:
                detail = json.loads(raw_detail or "{}")
            except Exception:
                detail = {}
            reason = str(detail.get("reason") or "broker_or_legacy_fill")
            fill_witness_reasons[reason] = fill_witness_reasons.get(reason, 0) + 1
            witness_at = detail.get("fill_witness_at")
            if witness_at:
                precise_witness_times += 1
            elif detail.get("trade_created_time"):
                witness_at = detail["trade_created_time"]
                precise_witness_times += 1
            elif detail.get("candle_end_ts") is not None:
                try:
                    witness_at = datetime.fromtimestamp(
                        float(detail["candle_end_ts"]), timezone.utc,
                    ).isoformat()
                    precise_witness_times += 1
                except (TypeError, ValueError, OSError):
                    witness_at = None
            try:
                submitted_dt = datetime.fromisoformat(str(submitted_at).replace("Z", "+00:00"))
                witnessed_dt = datetime.fromisoformat(
                    str(witness_at or recorded_at).replace("Z", "+00:00")
                )
                latencies.append(max(0.0, (witnessed_dt - submitted_dt).total_seconds()))
            except (TypeError, ValueError):
                continue

        def percentile(values: list[float], q: float) -> float | None:
            if not values:
                return None
            ordered = sorted(values)
            position = (len(ordered) - 1) * q
            lower = int(position)
            upper = min(len(ordered) - 1, lower + 1)
            fraction = position - lower
            return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction

        def wilson(successes: int, n: int) -> dict[str, Any] | None:
            if n <= 0:
                return None
            z = 1.96
            rate = successes / n
            denominator = 1.0 + z * z / n
            center = (rate + z * z / (2.0 * n)) / denominator
            margin = z * math.sqrt(
                rate * (1.0 - rate) / n + z * z / (4.0 * n * n)
            ) / denominator
            return {
                "rate": round(rate, 6),
                "lower": round(max(0.0, center - margin), 6),
                "upper": round(min(1.0, center + margin), 6),
                "method": "wilson_95",
                "n": n,
            }

        resolved = filled + expired_unfilled

        return {
            "book_scope": scope or "all",
            "orders_submitted": submitted,
            "orders_with_confirmed_fill": filled,
            "observed_fill_rate": round(filled / submitted, 4) if submitted else None,
            "observed_fill_rate_ci95": wilson(filled, submitted),
            "orders_with_known_outcome": resolved,
            "known_outcome_rate": round(resolved / submitted, 4) if submitted else None,
            "resolved_order_fill_rate": round(filled / resolved, 4) if resolved else None,
            "resolved_order_fill_rate_ci95": wilson(filled, resolved),
            "contracts_submitted": contracts_submitted,
            "contracts_confirmed_filled": contracts_filled,
            "contract_fill_rate": (
                round(contracts_filled / contracts_submitted, 4)
                if contracts_submitted else None
            ),
            "contract_fill_rate_ci95": wilson(contracts_filled, contracts_submitted),
            "partially_filled_orders": partial_orders,
            "expired_or_canceled_unfilled": expired_unfilled,
            "pending_orders": pending,
            "open_filled_positions": open_filled,
            "average_seconds_to_first_fill": (
                round(sum(latencies) / len(latencies), 2) if latencies else None
            ),
            "median_seconds_to_first_fill": (
                round(float(percentile(latencies, 0.5)), 2) if latencies else None
            ),
            "p90_seconds_to_first_fill": (
                round(float(percentile(latencies, 0.9)), 2) if latencies else None
            ),
            "fill_witness_quality": {
                "filled_orders": scoped_filled_rows,
                "precise_witness_timestamps": precise_witness_times,
                "precise_witness_rate": (
                    round(precise_witness_times / scoped_filled_rows, 4)
                    if scoped_filled_rows else None
                ),
                "reasons": fill_witness_reasons,
            },
        }

    def performance_summary(self) -> dict[str, Any]:
        # Isolated-challenger lane rows ('chal-') are promotion evidence, not
        # headline performance — excluded so the realized slice stays the
        # ensemble's own record.
        pnl = self._conn.execute(
            """
            SELECT COALESCE(SUM(o.pnl_cents),0), COUNT(*) FROM outcomes o
            WHERE o.pnl_cents IS NOT NULL
              AND o.kind IN ('SETTLED_WIN','SETTLED_LOSS')
              AND o.decision_id NOT LIKE 'chal-%'
              AND EXISTS (
                  SELECT 1 FROM outcomes fill
                  WHERE fill.decision_id = o.decision_id
                    AND fill.id < o.id AND fill.fill_count > 0
              )
            """
        ).fetchone()
        unverified = self._conn.execute(
            """
            SELECT COUNT(*) FROM outcomes o
            WHERE o.pnl_cents IS NOT NULL
              AND o.kind IN ('SETTLED_WIN','SETTLED_LOSS')
              AND NOT EXISTS (
                  SELECT 1 FROM outcomes fill
                  WHERE fill.decision_id = o.decision_id
                    AND fill.id < o.id AND fill.fill_count > 0
              )
            """
        ).fetchone()
        settled = self._conn.execute("SELECT COUNT(*) FROM settlements").fetchone()
        decisions = self._conn.execute(
            "SELECT COUNT(*), SUM(CASE WHEN action='ABSTAIN' THEN 1 ELSE 0 END) FROM decisions"
        ).fetchone()
        lessons = self._conn.execute("SELECT COUNT(*) FROM lessons").fetchone()
        return {
            "realized_pnl_cents": int(pnl[0]),
            "outcomes_with_pnl": int(pnl[1]),
            "unverified_settlement_outcomes": int(unverified[0]),
            "settlements_recorded": int(settled[0]),
            "decisions_total": int(decisions[0] or 0),
            "decisions_abstained": int(decisions[1] or 0),
            "lessons_recorded": int(lessons[0]),
            "source_weights": self.all_weights(),
            "execution_quality": self.execution_summary(),
        }

    def realized_pnl_cents(self, scope: str | None = None) -> int:
        """Verified settled-fill P&L, optionally isolated by shadow/live book."""
        if scope not in {None, "shadow", "live"}:
            raise ValueError("P&L scope must be None, 'shadow', or 'live'")
        rows = self._conn.execute(
            """
            WITH book AS (
                SELECT decision_id,
                       MAX(CASE WHEN kind='SHADOW' THEN 1 ELSE 0 END) AS is_shadow,
                       MAX(broker_contacted) AS is_live
                FROM outcomes GROUP BY decision_id
            )
            SELECT o.pnl_cents,b.is_shadow,b.is_live
            FROM outcomes o JOIN book b USING(decision_id)
            WHERE o.pnl_cents IS NOT NULL
              AND o.kind IN ('SETTLED_WIN','SETTLED_LOSS')
              AND EXISTS (
                  SELECT 1 FROM outcomes fill
                  WHERE fill.decision_id=o.decision_id
                    AND fill.id<o.id AND fill.fill_count>0
              )
            """
        ).fetchall()
        return sum(
            int(pnl) for pnl, is_shadow, is_live in rows
            if scope is None or (scope == "shadow" and int(is_shadow) == 1)
            or (scope == "live" and int(is_live) == 1 and int(is_shadow) == 0)
        )
