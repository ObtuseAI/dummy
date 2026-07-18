"""The self-improvement planner (Wave-20).

Every diagnostic loop in the system produces an artifact: where we bleed
(loss engine), where there is no edge (no-edge map), why promotions were
declined (declines dossiers), what the negative-control battery flagged,
what the tuner proposed and auto-applied, and how accurate the fused picks
are. This module reads them ALL and emits one ranked plan -- the machine's
own answer to "what should improve next" -- annotating each item with
whether a CLOSED loop already actions it autonomously (tuner overrides,
validated calibration maps, the fusion floor, the promotion ladder,
performance quarantines, auto-demotion) or whether it is genuinely
operator-gated (capital, new data sources, live deploys).

Read-only over artifacts; fail-open per input (a missing artifact
contributes nothing rather than an error). The plan is itself an artifact:
``runtime/autonomy/self_improvement_plan.json``, surfaced on the dashboard.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUNTIME_DIR = Path("runtime/autonomy")
PLAN_PATH = RUNTIME_DIR / "self_improvement_plan.json"


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def assemble_plan(runtime_dir: Path | None = None) -> dict[str, Any]:
    rd = runtime_dir or RUNTIME_DIR
    items: list[dict[str, Any]] = []

    # 1) Bleeding scopes: the loss engine's verdicts. Trust, the fusion
    # floor, and quarantines already contain these; a PERSISTENT bleeder is
    # a modeling gap worth a targeted build.
    loss = _load(rd / "loss_attribution.json")
    for entry in (loss.get("scopes") or []):
        if isinstance(entry, dict) and entry.get("verdict") == "bleeding":
            items.append({
                "kind": "bleeding_scope",
                "target": entry.get("scope"),
                "severity": abs(float(entry.get("cluster_edge") or 0.0)),
                "evidence": {"cluster_edge": entry.get("cluster_edge"),
                             "n_clusters": entry.get("n_clusters")},
                "closed_loops": ["trust_downweight", "fusion_floor",
                                 "performance_quarantine", "auto_demotion"],
                "owner": "machine",
                "next": "persistent bleeding after floor+trust = modeling gap;"
                        " candidate for a targeted model wave",
            })

    # 2) Significantly-negative scopes (the fusion floor consumes the same
    # map; listed so the plan shows WHAT is currently suppressed).
    no_edge = _load(rd / "no_edge_map.json")
    for entry in (no_edge.get("significantly_negative") or []):
        if isinstance(entry, dict):
            items.append({
                "kind": "significantly_negative_scope",
                "target": entry.get("scope"),
                "severity": abs(float(entry.get("edge_mean") or 0.0)),
                "evidence": {key: entry.get(key) for key in
                             ("edge_mean", "ci_upper", "clusters")},
                "closed_loops": ["fusion_floor"],
                "owner": "machine",
                "next": "excluded from fusion while negative; exits on evidence",
            })

    # 3) Declined promotions: the scopes worth accelerating, failing criteria
    # named (Wave-19 dossiers).
    declines = _load(rd / "promotion_declines.json")
    for entry in (declines.get("declined") or []):
        if isinstance(entry, dict):
            items.append({
                "kind": "promotion_declined",
                "target": entry.get("scope"),
                "severity": 0.5,
                "evidence": {"reason": entry.get("reason")},
                "closed_loops": ["promotion_ladder"],
                "owner": "machine",
                "next": "ladder re-evaluates nightly; failing criteria named"
                        " in the dossier",
            })

    # 4) Negative-control flags: measurement-integrity alarms (the Wave-5
    # fabricated-benchmark class) outrank everything.
    battery = _load(rd / "negative_control_report.json")
    for flagged in (battery.get("flagged_sources") or []):
        items.append({
            "kind": "negative_control_flag",
            "target": flagged if isinstance(flagged, str) else json.dumps(flagged),
            "severity": 10.0,
            "evidence": {"report": "negative_control_report.json"},
            "closed_loops": [],
            "owner": "operator",
            "next": "measurement-integrity alarm: investigate before trusting"
                    " this source's evidence",
        })

    # 5) Tuning: applied moves prove the loop closed; proven candidates
    # WITHOUT a consumption point are each one small build from self-tuning.
    from autonomy.tuned_params import CONSUMED_PARAMS

    tuned = _load(rd / "tuned_params.json")
    proposals = _load(rd / "tuning_proposals.json")
    consumed_now = set((tuned.get("overrides") or {}).keys())
    for proposal in (proposals.get("proposals") or []):
        if not isinstance(proposal, dict) or proposal.get("verdict") != "candidate":
            continue
        name = str(proposal.get("name"))
        if name in CONSUMED_PARAMS:
            items.append({
                "kind": "tuning_applied" if name in consumed_now else "tuning_pending",
                "target": name,
                "severity": 0.4,
                "evidence": {"test_delta": proposal.get("test_delta"),
                             "best": proposal.get("best")},
                "closed_loops": ["tuner_auto_promote"],
                "owner": "machine",
                "next": "override walks toward best at <=20%/night while the"
                        " walk-forward CI holds",
            })
        else:
            items.append({
                "kind": "tuning_unconsumed",
                "target": name,
                "severity": 0.6,
                "evidence": {"test_delta": proposal.get("test_delta"),
                             "best": proposal.get("best")},
                "closed_loops": [],
                "owner": "operator",
                "next": "walk-forward-proven improvement with NO consumption"
                        " point -- wire this parameter into tuned_params to"
                        " close its loop",
            })

    # 6) Pick-accuracy floor: any (league|market_type) cell measurably under
    # 50% hit rate on adequate volume is a mispriced pick side -- the most
    # direct violation of the operator's floor directive.
    readiness = _load(rd / "readiness_report.json")
    picks = (readiness.get("picks") or {}).get("sources") or []
    for source_block in picks:
        for scope, cell in (source_block.get("by_scope") or {}).items():
            hit = cell.get("hit_rate")
            if hit is not None and cell.get("picks", 0) >= 30 and hit < 0.5:
                items.append({
                    "kind": "pick_accuracy_below_floor",
                    "target": f"{source_block.get('source')}::{scope}",
                    "severity": 5.0 * (0.5 - float(hit)),
                    "evidence": dict(cell),
                    "closed_loops": ["fused_calibration_shadow"],
                    "owner": "machine",
                    "next": "calibration shadow measures the correction; if"
                            " the shadow also fails, this cell is a model gap",
                })

    # 7) USE sidecar (Wave-22): where the simulation partner stands -- how
    # much training tape it has accrued toward its first recursive tune, and
    # whether the predictions artifact is flowing.
    use_predictions = _load(rd / "use_predictions.json")
    try:
        with (rd / "use_outcomes.jsonl").open(encoding="utf-8") as fh:
            tape = sum(1 for _ in fh)
    except OSError:
        tape = 0
    if use_predictions or tape:
        status = use_predictions.get("status")
        items.append({
            "kind": "use_sidecar_status",
            "target": "universal-sports-engine",
            "severity": 1.0 if status == "ENGINE_ABSENT" else 0.3,
            "evidence": {"predictions_status": status,
                         "outcomes_on_tape": tape,
                         "tune_gate": 300},
            "closed_loops": ["use_recursive_tuning"],
            "owner": "operator" if status == "ENGINE_ABSENT" else "machine",
            "next": ("sidecar checkout missing -- restore it or set"
                     " DUMMY_USE_ENGINE_PATH" if status == "ENGINE_ABSENT"
                     else "USE's own recursive tuner fires at >=300 taped"
                          " outcomes; champions promote by its preregistered"
                          " gates"),
        })

    items.sort(key=lambda item: -float(item.get("severity") or 0.0))
    counts: dict[str, int] = {}
    for item in items:
        counts[item["kind"]] = counts.get(item["kind"], 0) + 1
    return {
        "report_name": "SELF_IMPROVEMENT_PLAN",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": counts,
        "items": items[:100],
        "closed_loops_active": [
            "trust_learning (per-scope, contested-only)",
            "validated_calibration_maps (holdout-gated, nightly)",
            "fused_calibration_shadow (::cal, self-activating)",
            "fusion_floor (significantly-negative scopes excluded)",
            "performance_quarantine (contraction-safe cohort repair)",
            "promotion_ladder (auto promote/escalate/demote, dossiers kept)",
            "tuner_auto_promote (step-capped runtime overrides)",
            "strategy_miner (FDR-controlled rule mining, nightly)",
            "live_poller + burst_repricing (event-driven)",
            "use_sidecar (strengths -> simulation -> outcomes; USE's own"
            " champion governance tunes on our settled games)",
        ],
    }


def write_plan(plan: dict[str, Any], path: Path | None = None) -> Path:
    target = path or PLAN_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(plan, indent=2, sort_keys=True),
                         encoding="utf-8")
    temporary.replace(target)
    return target
