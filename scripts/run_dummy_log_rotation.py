"""Wave-49: bound the append-only runtime telemetry so the ledger-hardened
autonomy stack is *completely* self-sufficient. The daily prune + weekly VACUUM
bound the ledger; the process stdout logs and two rolling telemetry tapes were
the last unbounded-growth vectors on disk. This is the maintenance task that
bounds them.

Because this is the ONLY scheduled task that rewrites ``runtime/autonomy``
telemetry files, its safety rule is strict: it rotates a file only when that
file is disposable telemetry whose *old* lines have no consumer. It works from
an explicit allowlist -- it never globs ``*.jsonl`` -- so organism state, open
paper positions, the promotion/preregistration audit trail, and the CLV
order-book tape are left completely alone.

Rotated (consumers verified 2026-07-19):
  * ``*.log``             process stdout/stderr; no structured reader.
                          Byte-cap: keep the last DUMMY_LOG_KEEP_MIB, snapped to
                          a line boundary; drop older bytes. Rotates only when
                          the file exceeds DUMMY_LOG_MAX_MIB (hysteresis).
  * ``cycles.jsonl``      tail-only readers (dashboard reads last 30/10,
                          watchdog reads the trailing-error run).
  * ``live_events.jsonl`` tail-only reader (live_tape reads the last 64 KiB).
                          Both tapes: keep the last DUMMY_JSONL_KEEP_LINES
                          lines; rotate only above 1.5x that (hysteresis).

Never touched by default:
  * ``book_tape.jsonl``   the CLV grader joins paper entries against this over
                          *full history*; a blind truncation would silently
                          degrade closing-line-value grading. Age-bounded ONLY
                          when DUMMY_BOOK_TAPE_KEEP_DAYS is set (disarmed
                          default), keeping records whose ``ts`` is within that
                          many days. Records with an unparseable ``ts`` are
                          always kept.
  * every other .jsonl    state/audit -- pending episodes, paper_entries,
                          promotion_ledger, preregistrations, use_outcomes,
                          evolution_history, alerts -- never rotated.

Fail-safe throughout: a file is rewritten only when it is over its cap; each
rewrite is atomic (tmp + os.replace) so a crash never leaves a partial file; a
file another process holds (os.replace raises on Windows) is skipped and picked
up on the next daily run; nothing is deleted, only tail-preserved.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Verified tail-only telemetry tapes -> line-capped. Deliberately a short,
# hand-verified tuple, NOT a glob: adding a name here is a decision that the
# file has no full-history consumer.
TAPES = ("cycles.jsonl", "live_events.jsonl")

# The CLV order-book tape: read over full history by the CLV grader, so it is
# age-bounded (never line/byte-capped) and only when explicitly armed.
BOOK_TAPE = "book_tape.jsonl"
BOOK_TAPE_TS_FIELD = "ts"

# This task's own launcher appends here while the task runs; skip it so we never
# rewrite a log our own parent process holds open.
SELF_LOG = "log_rotation_stdout.log"

_MIB = 1024 * 1024


@dataclass
class Config:
    log_keep_bytes: int
    log_max_bytes: int
    jsonl_keep_lines: int
    jsonl_max_lines: int
    book_tape_keep_days: float | None  # None == disarmed


@dataclass
class Result:
    name: str
    kind: str          # "log" | "tape" | "book_tape"
    action: str        # "rotated" | "ok" | "skipped-locked" | "skipped-missing"
    before: int        # bytes
    after: int         # bytes


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def config_from_env() -> Config:
    keep_mib = _env_float("DUMMY_LOG_KEEP_MIB", 4.0)
    max_mib = _env_float("DUMMY_LOG_MAX_MIB", 20.0)
    # A max below the keep size would rotate to a *larger* tail than the cap;
    # clamp so max is always at least the keep size.
    max_mib = max(max_mib, keep_mib)
    keep_lines = int(_env_float("DUMMY_JSONL_KEEP_LINES", 50_000))
    raw_days = (os.environ.get("DUMMY_BOOK_TAPE_KEEP_DAYS") or "").strip()
    book_days: float | None = None
    if raw_days:
        try:
            book_days = float(raw_days)
        except ValueError:
            book_days = None
    return Config(
        log_keep_bytes=int(keep_mib * _MIB),
        log_max_bytes=int(max_mib * _MIB),
        jsonl_keep_lines=keep_lines,
        jsonl_max_lines=int(keep_lines * 1.5),
        book_tape_keep_days=book_days,
    )


def _atomic_replace(path: Path, data: bytes, *, retries: int = 3, wait: float = 2.0) -> bool:
    """Rewrite ``path`` atomically. Returns False if another process holds it
    (os.replace raises on Windows) -- caller treats that as skip-and-retry-later.
    """
    tmp = path.with_suffix(path.suffix + ".rot.tmp")
    for attempt in range(retries):
        try:
            with tmp.open("wb") as fh:
                fh.write(data)
            os.replace(tmp, path)
            return True
        except OSError:
            try:
                tmp.unlink()
            except OSError:
                pass
            if attempt < retries - 1:
                time.sleep(wait)
    return False


def rotate_log(path: Path, keep_bytes: int, max_bytes: int) -> Result:
    """Byte-cap a plain log to its last ``keep_bytes``, snapped to a line."""
    size = path.stat().st_size
    if size <= max_bytes:
        return Result(path.name, "log", "ok", size, size)
    with path.open("rb") as fh:
        fh.seek(max(0, size - keep_bytes))
        tail = fh.read()
    # Drop a partial first line left by the byte seek.
    nl = tail.find(b"\n")
    if 0 <= nl < len(tail) - 1:
        tail = tail[nl + 1:]
    if _atomic_replace(path, tail):
        return Result(path.name, "log", "rotated", size, len(tail))
    return Result(path.name, "log", "skipped-locked", size, size)


def _count_lines(path: Path) -> int:
    n = 0
    with path.open("rb") as fh:
        while True:
            block = fh.read(1 << 20)
            if not block:
                break
            n += block.count(b"\n")
    return n


def rotate_tape(path: Path, keep_lines: int, max_lines: int) -> Result:
    """Line-cap a verified tail-only tape to its last ``keep_lines`` lines."""
    before = path.stat().st_size
    if _count_lines(path) <= max_lines:
        return Result(path.name, "tape", "ok", before, before)
    with path.open("rb") as fh:
        lines = fh.read().splitlines(keepends=True)
    data = b"".join(lines[-keep_lines:])
    if _atomic_replace(path, data):
        return Result(path.name, "tape", "rotated", before, len(data))
    return Result(path.name, "tape", "skipped-locked", before, before)


def _parse_ts(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def age_bound(path: Path, ts_field: str, keep_days: float, now: datetime) -> Result:
    """Drop records older than ``keep_days`` by their ``ts_field``. A record
    with a missing or unparseable timestamp is always kept (fail-safe)."""
    before = path.stat().st_size
    cutoff = now - timedelta(days=keep_days)
    kept: list[bytes] = []
    dropped = 0
    with path.open("rb") as fh:
        for raw in fh:
            stripped = raw.strip()
            if not stripped:
                continue
            keep = True
            try:
                ts = _parse_ts(json.loads(stripped).get(ts_field))
                if ts is not None and ts < cutoff:
                    keep = False
            except (ValueError, TypeError):
                keep = True  # unparseable -> keep
            if keep:
                kept.append(raw if raw.endswith(b"\n") else raw + b"\n")
            else:
                dropped += 1
    if dropped == 0:
        return Result(path.name, "book_tape", "ok", before, before)
    data = b"".join(kept)
    if _atomic_replace(path, data):
        return Result(path.name, "book_tape", "rotated", before, len(data))
    return Result(path.name, "book_tape", "skipped-locked", before, before)


def _cleanup_tmp(runtime_dir: Path) -> None:
    for tmp in runtime_dir.glob("*.rot.tmp"):
        try:
            tmp.unlink()
        except OSError:
            pass


def run_rotation(runtime_dir: Path, config: Config, now: datetime) -> list[Result]:
    results: list[Result] = []
    if not runtime_dir.is_dir():
        return results
    _cleanup_tmp(runtime_dir)

    # Logs: every *.log except this task's own (held-open) launcher log.
    for path in sorted(runtime_dir.glob("*.log")):
        if path.name == SELF_LOG:
            continue
        try:
            results.append(rotate_log(path, config.log_keep_bytes, config.log_max_bytes))
        except OSError:
            results.append(Result(path.name, "log", "skipped-locked",
                                  path.stat().st_size if path.exists() else 0, 0))

    # Tapes: the explicit, verified tail-only allowlist.
    for name in TAPES:
        path = runtime_dir / name
        if not path.exists():
            results.append(Result(name, "tape", "skipped-missing", 0, 0))
            continue
        try:
            results.append(rotate_tape(path, config.jsonl_keep_lines, config.jsonl_max_lines))
        except OSError:
            results.append(Result(name, "tape", "skipped-locked", path.stat().st_size, 0))

    # book_tape: age-bound only when armed.
    book = runtime_dir / BOOK_TAPE
    if config.book_tape_keep_days is not None and book.exists():
        try:
            results.append(age_bound(book, BOOK_TAPE_TS_FIELD,
                                     config.book_tape_keep_days, now))
        except OSError:
            results.append(Result(BOOK_TAPE, "book_tape", "skipped-locked",
                                  book.stat().st_size, 0))

    return results


def main() -> int:
    runtime_dir = Path(os.environ.get("DUMMY_RUNTIME_DIR") or "runtime/autonomy")
    config = config_from_env()
    now = datetime.now(timezone.utc)
    stamp = now.isoformat(timespec="seconds")
    results = run_rotation(runtime_dir, config, now)

    rotated = [r for r in results if r.action == "rotated"]
    reclaimed = sum(r.before - r.after for r in rotated)
    print(f"[{stamp}] log rotation: dir={runtime_dir} "
          f"rotated={len(rotated)} reclaimed={reclaimed / _MIB:.1f}MiB "
          f"armed_book_tape={config.book_tape_keep_days is not None}")
    for r in results:
        if r.action in ("rotated", "skipped-locked"):
            print(f"  {r.action:15s} {r.kind:10s} {r.name}: "
                  f"{r.before / _MIB:.2f} -> {r.after / _MIB:.2f} MiB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
