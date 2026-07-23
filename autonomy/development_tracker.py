"""Development tracker: is the player-development machine actually running?

The Dodgers' separating trait is not buying talent -- several teams do that --
it is that acquired talent keeps IMPROVING after arrival (the pitching lab),
and the machine that does the improving never silently stops. Dummy's
development machine is the daily tuner (walk-forward-tuned home advantages,
scoring sigmas, EPA params, rest coefficients) plus the daily lake ingestion
that feeds it. This tracker watches the machine itself:

  * tuned-params artifact freshness (DummyTune output);
  * history-lake forward growth (most recent game ingested per active league);

and flags DEVELOPMENT_STALE when either rots. Found in the wild: on
2026-07-23 this exact check exposed a deleted per-league scheduler suite --
tuned params 3 days old, the lake frozen 4 days. Report-only; wired into
readiness so a dead development lab is a daily headline, not a surprise.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPORT_PATH = Path("runtime/autonomy/development_tracker.json")
TUNED_PATH = Path("runtime/autonomy/sports_tuned_params.json")
TUNED_STALE_HOURS = 48.0
LAKE_STALE_DAYS = 2.5   # an in-season league should land new finals ~daily


def _parse(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else None


def build_development_tracker(
    store: Any,
    *,
    active_leagues: tuple[str, ...] = ("mlb", "wnba"),
    now: datetime | None = None,
    tuned_path: Path | str = TUNED_PATH,
) -> dict[str, Any]:
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    warnings: list[str] = []

    tuned_generated = None
    try:
        tuned = json.loads(Path(tuned_path).read_text(encoding="utf-8"))
        tuned_generated = _parse(tuned.get("generated_at"))
    except (OSError, ValueError):
        pass
    tuned_age_hours = (
        (now_utc - tuned_generated).total_seconds() / 3600.0
        if tuned_generated else None
    )
    if tuned_age_hours is None or tuned_age_hours > TUNED_STALE_HOURS:
        warnings.append("tuner_output_stale_or_missing")

    lake: dict[str, Any] = {}
    for league in active_leagues:
        latest = None
        try:
            row = store.conn.execute(
                "SELECT MAX(start_time) FROM games WHERE league = ? AND status"
                " IN ('final','post')",
                (league,),
            ).fetchone()
            latest = _parse(row[0]) if row and row[0] else None
        except Exception:  # noqa: BLE001
            latest = None
        age_days = (
            (now_utc - latest).total_seconds() / 86400.0 if latest else None
        )
        stale = age_days is None or age_days > LAKE_STALE_DAYS
        lake[league] = {
            "latest_final": latest.isoformat() if latest else None,
            "age_days": round(age_days, 2) if age_days is not None else None,
            "stale": stale,
        }
        if stale:
            warnings.append(f"lake_ingestion_stale_{league}")

    return {
        "report_version": "development_tracker_v1",
        "generated_at": now_utc.isoformat(),
        "tuner": {
            "generated_at": tuned_generated.isoformat() if tuned_generated else None,
            "age_hours": round(tuned_age_hours, 1) if tuned_age_hours is not None else None,
            "stale_threshold_hours": TUNED_STALE_HOURS,
        },
        "lake_forward_growth": lake,
        "warnings": warnings,
        "development_machine_healthy": not warnings,
        "purpose": (
            "the Dodgers trait is that development never silently stops; this "
            "watches the tuner and lake-ingestion machinery itself, report-only"
        ),
    }


def write_development_tracker(
    store: Any, *, path: Path | str = REPORT_PATH, **kwargs: Any,
) -> dict[str, Any]:
    report = build_development_tracker(store, **kwargs)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(target)
    return report
