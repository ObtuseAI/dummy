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

from autonomy.loss_engine import (  # noqa: E402
    build_fill_loss_attribution,
    build_loss_attribution,
    filled_market_tickers,
    narrate_losses,
    write_report,
)
from autonomy.strategy_miner import load_settled_rows  # noqa: E402

DEFAULT_DB = Path("runtime/autonomy/ledger.db")
DEFAULT_OUT = Path("runtime/autonomy/loss_attribution.json")
# WS-A1: fill-conditioned loss deconstruction (where the FILLED trades lose).
DEFAULT_FILL_OUT = Path("runtime/autonomy/loss_attribution_fills.json")


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
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--fills", action="store_true",
        help="restrict attribution to the witnessed / would-have-filled subset"
        " (WS-A1 adverse-selection localization) and write loss_attribution_fills.json",
    )
    parser.add_argument(
        "--no-narration", action="store_true",
        help="skip the LLM commentary pass; write the deterministic artifact only",
    )
    args = parser.parse_args()
    out_path = args.out or (DEFAULT_FILL_OUT if args.fills else DEFAULT_OUT)
    if not args.db.exists():
        print(json.dumps({"status": "NO_DB", "db": str(args.db)}))
        return 1

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    try:
        rows = load_settled_rows(conn)
        fill_tickers = filled_market_tickers(conn) if args.fills else set()
    finally:
        conn.close()

    now_iso = datetime.now(timezone.utc).isoformat()
    if args.fills:
        attribution = build_fill_loss_attribution(rows, fill_tickers, now_iso=now_iso)
    else:
        attribution = build_loss_attribution(rows, now_iso=now_iso)
    if not args.no_narration:
        try:
            attribution["narration"] = narrate_losses(attribution, _get_router())
        except Exception:
            # Belt-and-suspenders fail-closed: narrate_losses() itself
            # degrades to {} on router/import trouble, but this guard
            # guarantees the deterministic artifact below is STILL written
            # even if something in the narration path raises anyway (e.g. a
            # future change to narrate_losses, or a router construction bug
            # in _get_router() surfacing here instead of returning None).
            attribution["narration"] = {}
    write_report(attribution, out_path)

    bleeding = sum(1 for scope in attribution["scopes"] if scope.get("verdict") == "bleeding")
    status = {
        "status": "OK",
        "mode": "fills" if args.fills else "full",
        "settled_rows": attribution["settled_rows"],
        "scopes_evaluated": attribution["family_size"]["scopes_evaluated"],
        "buckets_evaluated": attribution["family_size"]["buckets_evaluated"],
        "bleeding_scopes": bleeding,
        "narrated": bool(attribution.get("narration")),
        "out": str(out_path),
    }
    if args.fills:
        status.update({
            "filled_markets": attribution.get("filled_markets"),
            "fill_settled_rows": attribution.get("fill_settled_rows"),
            "pooled_cluster_edge": attribution.get("pooled_cluster_edge"),
            "pooled_cluster_edge_ci95": attribution.get("pooled_cluster_edge_ci95"),
        })
    print(json.dumps(status))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
