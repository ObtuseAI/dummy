#!/usr/bin/env python
"""Nightly readiness pass: per-scope promotion evidence + auto-demotions.

Read-only against the ledger. For every challenger scope (source x market_type
x horizon/phase, WS-15) it computes contested-Brier evidence over event
clusters and reports:
  * eligibility for a HUMAN promotion review (>=300 clusters, edge CI95 lower
    > 0, CLV non-negative where known, not degrading),
  * projected days-to-eligibility (the acceleration lever), and
  * auto-demotions for already-promoted scopes whose recent record turned
    negative -- written to auto_demotions.json, the only machine-authoritative
    governance file.

Proposes; never promotes. promotions.json is edited by a person in a reviewed
PR citing readiness_report.json. This runner has no session, execution, or
capital authority.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.promotion import (  # noqa: E402
    DEFAULT_DEMOTIONS_PATH,
    PromotionRegistry,
    build_readiness,
    utc_now,
)
from autonomy.strategy_miner import _brier_edge, load_settled_rows  # noqa: E402

DEFAULT_DB = Path("runtime/autonomy/ledger.db")
REPORT_PATH = Path("runtime/autonomy/readiness_report.json")


def _epoch(text: str) -> float | None:
    try:
        return datetime.fromisoformat(str(text).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _merge_demotions(path: Path, fresh: dict, now_iso: str) -> dict:
    """Union new demotions with existing ones -- demotions never un-stick.

    A promoted scope that recovers stays demoted until a HUMAN removes it from
    promotions.json (or clears this file); otherwise a transient recovery would
    silently re-promote it, defeating the human-only promotion rule.
    """
    existing: dict[str, dict] = {}
    try:
        prior = json.loads(path.read_text(encoding="utf-8"))
        for entry in (prior.get("demotions") or []):
            if isinstance(entry, dict) and entry.get("scope"):
                existing[str(entry["scope"])] = entry
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    for entry in fresh.get("demotions", []):
        existing.setdefault(entry["scope"], entry)  # keep original detected_at
    return {"demotions": sorted(existing.values(), key=lambda e: e["scope"]),
            "generated_at": now_iso}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    if not args.db.exists():
        print(json.dumps({"status": "NO_DB", "db": str(args.db)}))
        return 1

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    try:
        rows = load_settled_rows(conn)
    finally:
        conn.close()

    scope_rows: dict[str, list[tuple[float, str, float]]] = {}
    # A scope is challenger-gated when its rows carry challenger_only -- only
    # gated scopes can be promotion candidates (promoting an already-fusing
    # champion is a no-op the report must not recommend).
    gated_true: dict[str, int] = {}
    gated_total: dict[str, int] = {}
    for row in rows:
        ts = _epoch(row.created_at)
        if ts is None or not row.scope:
            continue
        scope_rows.setdefault(row.scope, []).append(
            (ts, row.event_cluster, _brier_edge(row)))
        gated_total[row.scope] = gated_total.get(row.scope, 0) + 1
        if bool((row.features or {}).get("challenger_only")):
            gated_true[row.scope] = gated_true.get(row.scope, 0) + 1
    challenger_gated = {
        scope for scope, total in gated_total.items()
        if gated_true.get(scope, 0) * 2 >= total  # majority of rows gated
    }

    registry = PromotionRegistry()
    promoted = set(registry.snapshot()["promoted"])
    now_ts, now_iso = utc_now()
    built = build_readiness(
        scope_rows, promoted, now_ts, now_iso,
        challenger_gated_scopes=challenger_gated)

    _write_json(REPORT_PATH, built["report"])
    merged_demotions = _merge_demotions(DEFAULT_DEMOTIONS_PATH, built["demotions"], now_iso)
    _write_json(DEFAULT_DEMOTIONS_PATH, merged_demotions)

    report = built["report"]
    print(json.dumps({
        "status": "OK",
        "scopes_evaluated": report["scopes_evaluated"],
        "promotion_candidates": report["promotion_candidates"],
        "new_auto_demotions": report["auto_demotions"],
        "total_auto_demotions": len(merged_demotions["demotions"]),
        "report": str(REPORT_PATH),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
