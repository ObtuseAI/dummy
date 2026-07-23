"""Recruiting board: one ranked talent pipeline across every candidate source.

Championship programs run recruiting as a single national board: every
prospect rated, staged, and matched to a position of need -- not four separate
lists nobody reconciles. Dummy sources candidate "talent" from four pipelines
that today never meet:

  * mined rules            (strategy miner -> mined_rule_forward_registry)
  * compiled claims        (strategy claim compiler -> strategy_claims)
  * harvested repositories (repo_harvester incorporation registry)
  * challenger scopes      (readiness report -- close to promotion)

This board merges them into one artifact with a stage per prospect
(PROSPECT -> EVALUATED -> COMMITTED -> STARTER, or CUT), a star rating from
evidence strength, and POSITION NEEDS derived from the no-edge map (scopes
with no demonstrated coverage are the roster holes recruiting should fill).

Report-only: the board prioritizes attention; promotion still goes through
every existing gate.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BOARD_PATH = Path("runtime/autonomy/recruiting_board.json")
RUNTIME = Path("runtime/autonomy")


def _load(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {}
    except (OSError, ValueError):
        return {}


def _stars(evidence: float, cap: float) -> int:
    """1-5 stars from a bounded evidence score (cap = the 5-star bar)."""
    if cap <= 0:
        return 1
    ratio = max(0.0, min(1.0, evidence / cap))
    return max(1, min(5, 1 + int(ratio * 4.999)))


def _mined_prospects(runtime: Path) -> list[dict[str, Any]]:
    registry = _load(runtime / "mined_rule_forward_registry.json")
    prospects = []
    for fingerprint, entry in (registry.get("rules") or {}).items():
        forward = entry.get("forward") or {}
        status = str(entry.get("status") or "TRACKING")
        stage = {
            "FORWARD_POSITIVE": "COMMITTED",
            "FORWARD_NEGATIVE": "CUT",
        }.get(status, "EVALUATED")
        clusters = int(forward.get("n_clusters") or 0)
        prospects.append({
            "name": str(entry.get("rule") or fingerprint)[:80],
            "source_type": "mined_rule",
            "stage": stage,
            "stars": _stars(clusters, 40.0),
            "evidence": {
                "forward_clusters": clusters,
                "forward_mean_edge": forward.get("mean_edge"),
                "status": status,
            },
        })
    return prospects


def _claim_prospects(runtime: Path) -> list[dict[str, Any]]:
    registry = _load(runtime / "strategy_claims.json")
    prospects = []
    for claim_id, compiled in (registry.get("claims") or {}).items():
        falsifiable = ((compiled.get("falsifiability") or {}).get("falsifiable")) is True
        repro = str(((compiled.get("reproducibility") or {}).get("status")) or "")
        if not falsifiable:
            continue  # unfalsifiable claims never make the board
        stage = {
            "REPRODUCED": "EVALUATED",
            "FAILED_TO_REPRODUCE": "CUT",
        }.get(repro, "PROSPECT")
        prospects.append({
            "name": str((compiled.get("claim") or {}).get("raw_excerpt") or claim_id)[:80],
            "source_type": "compiled_claim",
            "stage": stage,
            "stars": 2 if stage == "EVALUATED" else 1,
            "evidence": {
                "claim_id": claim_id,
                "interpretations": compiled.get("interpretation_count"),
                "reproducibility": repro or "NOT_YET_BACKTESTED",
            },
        })
    return prospects


def _repo_prospects() -> list[dict[str, Any]]:
    registry = _load(Path("artifacts/repo_harvester/incorporation_registry.json"))
    prospects = []
    for entry in registry.get("pending_tests") or []:
        prospects.append({
            "name": str(entry.get("adapter_name") or entry.get("repo") or "?")[:80],
            "source_type": "harvested_repo",
            "stage": "PROSPECT",
            "stars": 1,
            "evidence": {"integration_status": entry.get("integration_status")},
        })
    for entry in registry.get("incorporated") or []:
        prospects.append({
            "name": str(entry.get("adapter_name") or entry.get("repo") or "?")[:80],
            "source_type": "harvested_repo",
            "stage": "COMMITTED",
            "stars": 3,
            "evidence": {"integration_status": entry.get("integration_status")},
        })
    return prospects


def _challenger_prospects(runtime: Path) -> list[dict[str, Any]]:
    readiness = _load(runtime / "readiness_report.json")
    prospects = []
    for scope in readiness.get("scopes") or []:
        if not isinstance(scope, dict):
            continue
        clusters = int(scope.get("contested_clusters") or scope.get("n_clusters") or 0)
        eligible = bool(scope.get("eligible") or scope.get("promotion_candidate"))
        if clusters <= 0:
            continue
        prospects.append({
            "name": str(scope.get("scope") or "?")[:80],
            "source_type": "challenger_scope",
            "stage": "STARTER" if eligible else "COMMITTED",
            "stars": _stars(clusters, 300.0),
            "evidence": {
                "contested_clusters": clusters,
                "eligible_for_review": eligible,
            },
        })
    return prospects


def _position_needs(runtime: Path) -> list[dict[str, Any]]:
    """Roster holes: scopes with no demonstrated edge (or insufficient data)."""
    no_edge = _load(runtime / "no_edge_map.json")
    needs: list[dict[str, Any]] = []
    scopes = no_edge.get("scopes")
    if isinstance(scopes, dict):
        for scope, verdict in scopes.items():
            label = str(
                verdict.get("verdict") if isinstance(verdict, dict) else verdict
            ).lower()
            if "insufficient" in label:
                needs.append({"scope": scope, "need": "insufficient_evidence"})
            elif "no_edge" in label or "no demonstrated" in label:
                needs.append({"scope": scope, "need": "no_demonstrated_edge"})
    return needs[:50]


def build_recruiting_board(*, runtime: Path = RUNTIME) -> dict[str, Any]:
    prospects = (
        _mined_prospects(runtime)
        + _claim_prospects(runtime)
        + _repo_prospects()
        + _challenger_prospects(runtime)
    )
    stage_rank = {"STARTER": 0, "COMMITTED": 1, "EVALUATED": 2, "PROSPECT": 3, "CUT": 4}
    prospects.sort(key=lambda p: (stage_rank.get(p["stage"], 9), -p["stars"], p["name"]))
    by_stage: dict[str, int] = {}
    for prospect in prospects:
        by_stage[prospect["stage"]] = by_stage.get(prospect["stage"], 0) + 1
    return {
        "board_version": "recruiting_board_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prospects": prospects,
        "class_size": len(prospects),
        "by_stage": by_stage,
        "position_needs": _position_needs(runtime),
        "authority": "attention_prioritization_only_every_gate_still_applies",
    }


def write_recruiting_board(
    *, path: Path | str = BOARD_PATH, runtime: Path = RUNTIME,
) -> dict[str, Any]:
    board = build_recruiting_board(runtime=runtime)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(board, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(target)
    return board
