"""Matchup lens: hunt strong-source-vs-soft-market spots, Reid-offense style.

Elite offensive coordinators scheme to isolate their best player on the
defense's weakest coverage. Dummy's board ranks edges by after-fee size, but
an edge's QUALITY depends on the matchup that produced it:

  * source strength -- how much earned trust the contributing scope carries
    (recalibration weights);
  * market softness -- how weak the pricing on the other side is (wide
    spread, thin displayed depth, aging quote).

A big edge against FIRM pricing (tight, deep, fresh) is usually the market
knowing something we don't -- the Brady-era axiom that an easy-looking deep
shot against a good defense is bait. A modest edge from a strong source
against soft pricing is the isolation play. This lens grades the board's top
rows accordingly. Display/report-only.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_PATH = Path("runtime/autonomy/matchup_report.json")
RECAL_PATH = Path("runtime/autonomy/last_recalibration.json")
BOARD_PATH = Path("runtime/autonomy/bet_board.json")
TOP_ROWS = 25

SPREAD_SOFT_CENTS = 6.0     # bid/ask spread at/above this is soft pricing
DEPTH_SOFT = 25.0           # displayed size at/below this is thin
QUOTE_AGE_SOFT_SECONDS = 300.0


def _load(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {}
    except (OSError, ValueError):
        return {}


def source_strength(weights: dict[str, Any], scope_hint: str) -> float:
    """Best earned weight among sources matching the row's league/asset hint.

    Falls back to 1.0 (neutral) when no weight matches; weights below 1 mean
    the learner has DOWNGRADED the family -- a weak isolation target.
    """
    hint = str(scope_hint or "").lower()
    best = None
    for key, value in (weights or {}).items():
        if not isinstance(value, (int, float)):
            continue
        if hint and hint in str(key).lower():
            best = max(best, float(value)) if best is not None else float(value)
    return round(best, 4) if best is not None else 1.0


def market_softness(row: dict[str, Any]) -> dict[str, Any]:
    """0..1 softness from spread width, displayed depth, and quote age."""
    yes_bid, yes_ask = row.get("yes_bid"), row.get("yes_ask")
    spread = (
        float(yes_ask) - float(yes_bid)
        if isinstance(yes_bid, (int, float)) and isinstance(yes_ask, (int, float))
        else None
    )
    depth_values = [
        float(v) for v in (
            row.get("selected_bid_size_fp"), row.get("selected_ask_size_fp"),
        ) if isinstance(v, (int, float))
    ]
    depth = min(depth_values) if depth_values else None
    age = row.get("quote_age_seconds")
    components = {}
    score = 0.0
    weight = 0.0
    if spread is not None:
        components["spread_cents"] = spread
        score += min(1.0, spread / SPREAD_SOFT_CENTS) * 0.4
        weight += 0.4
    if depth is not None:
        components["displayed_depth"] = depth
        score += min(1.0, DEPTH_SOFT / max(depth, 1.0)) * 0.4
        weight += 0.4
    if isinstance(age, (int, float)):
        components["quote_age_seconds"] = age
        score += min(1.0, float(age) / QUOTE_AGE_SOFT_SECONDS) * 0.2
        weight += 0.2
    softness = round(score / weight, 4) if weight else None
    return {"softness": softness, **components}


def grade_matchup(strength: float, softness: float | None) -> str:
    if softness is None:
        return "unassessed"
    if strength >= 1.0 and softness >= 0.5:
        return "prime_isolation"          # strong source vs soft market
    if strength < 1.0 and softness < 0.3:
        return "bait_suspect"             # weak source vs firm market
    if softness < 0.3:
        return "firm_market_edge"         # respect: they might know something
    return "neutral"


def build_matchup_report(
    *, board_path: Path = BOARD_PATH, recal_path: Path = RECAL_PATH,
) -> dict[str, Any]:
    board = _load(board_path)
    recal = _load(recal_path)
    weights = {}
    for key in ("weights", "global_weights", "source_weights"):
        block = recal.get(key)
        if isinstance(block, dict):
            weights.update(block)
    rows = [r for r in (board.get("top") or []) if isinstance(r, dict)][:TOP_ROWS]
    graded = []
    for row in rows:
        if row.get("tier") not in ("A", "B", "C"):
            continue
        hint = str(row.get("league") or row.get("vertical") or "")
        strength = source_strength(weights, hint)
        softness = market_softness(row)
        matchup = grade_matchup(strength, softness.get("softness"))
        graded.append({
            "ticker": row.get("ticker"),
            "label": row.get("label") or row.get("market"),
            "tier": row.get("tier"),
            "after_fee_edge": row.get("after_fee_edge"),
            "source_strength": strength,
            **softness,
            "matchup": matchup,
        })
    order = {"prime_isolation": 0, "neutral": 1, "unassessed": 2,
             "firm_market_edge": 3, "bait_suspect": 4}
    graded.sort(key=lambda g: (order.get(g["matchup"], 9),
                               -(g.get("after_fee_edge") or 0.0)))
    return {
        "report_version": "matchup_lens_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "board_generated_at": board.get("generated_at"),
        "graded": graded,
        "prime_isolations": [g["ticker"] for g in graded
                             if g["matchup"] == "prime_isolation"],
        "bait_suspects": [g["ticker"] for g in graded
                          if g["matchup"] == "bait_suspect"],
        "purpose": (
            "grade each letter-tier edge by the matchup that produced it: "
            "strong source vs soft pricing is the isolation play; a big edge "
            "vs firm pricing is bait until proven otherwise; display-only"
        ),
    }


def write_matchup_report(
    *, path: Path | str = REPORT_PATH,
    board_path: Path = BOARD_PATH, recal_path: Path = RECAL_PATH,
) -> dict[str, Any]:
    report = build_matchup_report(board_path=board_path, recal_path=recal_path)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(target)
    return report
