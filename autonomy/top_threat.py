"""Top-threat decomposition: take away what beats us, Belichick-defense style.

Elite defensive plans start from one question: what is the single thing the
opponent does that most decides the game -- then remove it. Dummy's risk layer
already enforces static caps and a drawdown ladder; what it never states is
WHICH concentration would actually hurt most right now. This report decomposes
the open shadow book into worst-case scenario losses:

  * per correlated event cluster (one game/expiry flipping entirely);
  * per subject/asset (one team narrative, one crypto asset gapping);

ranked by worst-case cents, with each threat's share of total book worst-case.
The #1 row is "their best player" -- the exposure the next cycle should most
respect. Report-only; caps and the allocator remain the enforcement.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_PATH = Path("runtime/autonomy/top_threat.json")
CONCENTRATION_WARN = 0.35   # one cluster carrying >35% of book worst-case


def _worst_case_cents(position: dict[str, Any]) -> int:
    """Worst-case loss for one open position: full entry cost of witnessed size.

    A YES position loses its cost when the market settles NO (and vice versa),
    so worst case = filled_count * price (+ the active remainder's reserved
    cost for still-open orders, which can fill and then lose).
    """
    price = int(position.get("price_cents") or 0)
    filled = int(position.get("filled_count") or 0)
    reserved = int(position.get("reserved_count") or filled)
    at_risk = max(filled, reserved)
    return max(0, at_risk * price)


def build_top_threat(ledger: Any) -> dict[str, Any]:
    from autonomy.correlation import group_key
    from autonomy.taxonomy import prediction_subject

    clusters: dict[str, dict[str, Any]] = {}
    subjects: dict[str, int] = {}
    total = 0
    positions = 0
    for pending in ledger.open_decisions("shadow"):
        worst = _worst_case_cents(pending)
        if worst <= 0:
            continue
        ticker = str(pending.get("market_ticker") or "")
        cluster = group_key(ticker)
        subject = str(prediction_subject(ticker) or "other")
        entry = clusters.setdefault(cluster, {
            "cluster": cluster, "worst_case_cents": 0, "positions": 0,
            "tickers": [],
        })
        entry["worst_case_cents"] += worst
        entry["positions"] += 1
        if ticker not in entry["tickers"][:8]:
            entry["tickers"].append(ticker)
        subjects[subject] = subjects.get(subject, 0) + worst
        total += worst
        positions += 1

    ranked = sorted(
        clusters.values(), key=lambda c: -c["worst_case_cents"],
    )
    for entry in ranked:
        entry["share_of_book"] = (
            round(entry["worst_case_cents"] / total, 4) if total else 0.0
        )
        entry["tickers"] = entry["tickers"][:8]
    top = ranked[0] if ranked else None
    warnings = []
    if top and top["share_of_book"] > CONCENTRATION_WARN:
        warnings.append("single_cluster_concentration")
    return {
        "report_version": "top_threat_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "open_positions": positions,
        "book_worst_case_cents": total,
        "top_threat": top,
        "threats": ranked[:15],
        "by_subject": dict(sorted(
            subjects.items(), key=lambda item: -item[1],
        )[:10]),
        "warnings": warnings,
        "purpose": (
            "name the single concentration that would hurt most right now "
            "(the opponent's best player) so it is respected before it "
            "connects; report-only, caps stay the enforcement"
        ),
    }


def write_top_threat(
    ledger: Any, *, path: Path | str = REPORT_PATH,
) -> dict[str, Any]:
    report = build_top_threat(ledger)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(target)
    return report
