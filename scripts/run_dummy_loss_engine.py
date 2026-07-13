#!/usr/bin/env python
"""Loss-deconstruction evolution engine: nightly entrypoint (WS-B).

Read-only against the autonomy ledger. Deconstructs where the system loses
to the market (cluster-level Brier shortfall, per grading scope) and writes
the proposal artifact ``runtime/autonomy/loss_attribution.json`` for the
tuner's priority read, the dashboard/readiness "where we bleed" line, and
human review.

This is a proposer, not an actor: it has no session, execution, or capital
authority, and NEVER writes anything but this one JSON artifact -- no
constant, no promotion, no source file. The optional LLM narration pass is
commentary for a human reviewer only and fails closed (attribution is still
written with an empty ``narration`` if the router is unavailable, raises, or
times out).
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.loss_engine import build_loss_attribution, narrate_losses, write_report  # noqa: E402
from autonomy.strategy_miner import load_settled_rows  # noqa: E402

DEFAULT_DB = Path("runtime/autonomy/ledger.db")
DEFAULT_OUT = Path("runtime/autonomy/loss_attribution.json")


def _get_router():
    """Reuse the EXACT verified-LLM router construction/fail-closed pattern
    already shipped in autonomy/signals/llm_analyst.py -- no new LLM client.
    Any construction trouble (missing module, missing credentials, etc.)
    yields None, which narrate_losses treats as fail-closed."""
    try:
        from autonomy.signals.llm_analyst import LlmAnalystSignal

        return LlmAnalystSignal()._get_router()
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--no-narration", action="store_true",
        help="skip the LLM commentary pass; write the deterministic artifact only",
    )
    args = parser.parse_args()
    if not args.db.exists():
        print(json.dumps({"status": "NO_DB", "db": str(args.db)}))
        return 1

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    try:
        rows = load_settled_rows(conn)
    finally:
        conn.close()

    attribution = build_loss_attribution(rows, now_iso=datetime.now(timezone.utc).isoformat())
    if not args.no_narration:
        attribution["narration"] = narrate_losses(attribution, _get_router())
    write_report(attribution, args.out)

    bleeding = sum(1 for scope in attribution["scopes"] if scope.get("verdict") == "bleeding")
    print(json.dumps({
        "status": "OK",
        "settled_rows": attribution["settled_rows"],
        "scopes_evaluated": attribution["family_size"]["scopes_evaluated"],
        "buckets_evaluated": attribution["family_size"]["buckets_evaluated"],
        "bleeding_scopes": bleeding,
        "narrated": bool(attribution.get("narration")),
        "out": str(args.out),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
