#!/usr/bin/env python
"""Nightly readiness pass: per-scope promotion evidence + auto-demotions.

Read-only against the ledger. For every challenger scope (source x subject x
market_type x horizon/phase, WS-15) it computes contested-Brier evidence over event
clusters and reports:
  * eligibility for a HUMAN promotion review (>=300 clusters, edge CI95 lower
    > 0, CLV non-negative where known, not degrading),
  * projected days-to-eligibility (the acceleration lever), and
  * auto-demotions for already-promoted scopes whose recent record turned
    negative -- written to auto_demotions.json, the only machine-authoritative
    governance file.

Since the 2026-07-16 owner directive this runner ALSO executes the autonomous
thresholded promotion pass (autonomy/auto_promotion_runner.py) after the
readiness report. Promotion to a capped probation weight requires predictive
gates plus ledger-verified, receipt-bounded witnessed-fill net P&L from the
exact registered candidate over independent forward event clusters.
Midpoint/maker counterfactual ROI is report-only and cannot auto-promote.
Fusion membership only -- this runner still has no session, execution, or
capital authority, and live trading authorization (live_submit.json /
second-proof / session live auth) remains operator-gated.
``--skip-auto-promotion`` restores the report-only behavior. The existing
DummyReadinessReport scheduled task keeps working unchanged (re-running the
install script is optional; nothing about the task definition changed).

2026-07-24 (external audit): the optional report-writer sections (film room,
self-scout, fusion ablation, recruiting board, development tracker, edge
concentration, model-authority evidence, LLM value) used to be wrapped in
silent ``except Exception: pass`` handlers, so a locked ledger produced eight
missing artifacts while the task stayed green. Writers still run
independently (one failure never costs the others), but every failure is now
recorded in ``runtime/autonomy/report_writer_failures.json`` (written even
when empty so staleness is detectable) and any failure makes this process
exit ``EXIT_WRITER_FAILED`` so Task Scheduler shows the run red.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.promotion import (  # noqa: E402
    DEFAULT_DEMOTIONS_PATH,
    PromotionRegistry,
    build_readiness,
    utc_now,
)
from autonomy.reliability import (  # noqa: E402
    DEFAULT_MAPS_PATH,
    build_reliability_artifact,
    fit_maps_from_rows,
)
from autonomy.strategy_miner import _brier_edge, load_settled_rows  # noqa: E402

DEFAULT_DB = Path("runtime/autonomy/ledger.db")
REPORT_PATH = Path("runtime/autonomy/readiness_report.json")
LOSS_ATTRIBUTION_PATH = Path("runtime/autonomy/loss_attribution.json")
FAILURES_PATH = Path("runtime/autonomy/report_writer_failures.json")

# Distinct exit code for "the report ran but at least one report writer
# failed" (1 = missing DB, 2 = stale-backtest refusal). Task Scheduler
# records the code, so a dead writer is a red run instead of a green one.
EXIT_WRITER_FAILED = 3

# Cap on recorded traceback lines per failure (the artifact is a diagnostic,
# not a log dump).
TRACEBACK_TAIL_LINES = 30


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class WriterFailureRail:
    """Crash isolation for report-writer sections that must stay LOUD.

    Each optional section runs through :meth:`run` so one crashing writer
    never stops the others (that part of the old behavior was correct -- only
    the silence was wrong). Every failure is recorded with its traceback tail
    and surfaces in ``report_writer_failures.json`` + a nonzero exit code.
    """

    def __init__(self) -> None:
        self.failures: list[dict] = []
        self.ok_writers: list[str] = []

    def run(self, name: str, fn, default=None):
        try:
            result = fn()
        except Exception as exc:
            self.failures.append({
                "writer": name,
                "error": repr(exc),
                "traceback": traceback.format_exc().splitlines()[-TRACEBACK_TAIL_LINES:],
                "at": _utc_iso(),
            })
            return default
        self.ok_writers.append(name)
        return result

    def error_for(self, name: str) -> str | None:
        for entry in reversed(self.failures):
            if entry["writer"] == name:
                return str(entry["error"])
        return None


def write_failures_artifact(
    rail: WriterFailureRail, path: Path = FAILURES_PATH,
) -> None:
    """Written EVERY run, even with zero failures, so staleness is detectable."""
    _write_json(path, {
        "generated_at": _utc_iso(),
        "failures": rail.failures,
        "ok_writers": rail.ok_writers,
    })


def _where_we_bleed(path: Path = LOSS_ATTRIBUTION_PATH) -> str | None:
    """WS-B: one-line summary of the worst bleeding grading scope, read
    fail-closed from the loss engine's artifact. Missing/malformed artifact
    or no bleeding scope -> None (the caller omits the key entirely, so the
    printed summary has no line at all rather than a fabricated one)."""
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    bleeding = [
        entry for entry in (data.get("scopes") or [])
        if isinstance(entry, dict) and entry.get("verdict") == "bleeding"
    ]
    if not bleeding:
        return None
    try:
        worst = min(bleeding, key=lambda entry: float(entry.get("cluster_edge") or 0.0))
        return (
            f"{worst['scope']} edge {worst['cluster_edge']}"
            f" ({worst['n_clusters']} clusters)"
        )
    except Exception:
        return None


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


def _record_ratchet(fresh: dict, existing: dict, now_iso: str) -> int:
    """Charge every NEW demotion to the scope's promotion ratchet.

    Wave-86: under autonomous operation a demotion must raise the price of the
    next promotion rather than ban the scope forever. Recorded here, at the one
    place demotions are minted, so the ratchet cannot drift out of step with
    the demotion list. Returns how many new demotions were charged.
    """
    from autonomy.promotion_ratchet import load_ratchet, record_demotion, save_ratchet

    new_scopes = [
        entry["scope"] for entry in fresh.get("demotions", [])
        if isinstance(entry, dict) and entry.get("scope")
        and entry["scope"] not in existing
    ]
    if not new_scopes:
        return 0
    state = load_ratchet()
    for scope in new_scopes:
        record_demotion(state, scope, reason="auto_demotion", at=now_iso)
    save_ratchet(state)
    return len(new_scopes)


def _merge_demotions(path: Path, fresh: dict, now_iso: str) -> dict:
    """Union new demotions with existing ones -- demotions never un-stick HERE.

    A promoted scope that recovers stays in this file; it is not silently
    re-promoted by a transient recovery. Wave-86 makes the return path
    autonomous rather than human-only: each demotion charges the scope's
    ratchet (autonomy/promotion_ratchet.py), and a later attempt may clear a
    strictly harder bar. The door is repriced, not closed.
    """
    existing: dict[str, dict] = {}
    try:
        prior = json.loads(path.read_text(encoding="utf-8"))
        for entry in (prior.get("demotions") or []):
            if isinstance(entry, dict) and entry.get("scope"):
                existing[str(entry["scope"])] = entry
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    charged = _record_ratchet(fresh, existing, now_iso)
    for entry in fresh.get("demotions", []):
        existing.setdefault(entry["scope"], entry)  # keep original detected_at
    return {"demotions": sorted(existing.values(), key=lambda e: e["scope"]),
            "generated_at": now_iso,
            "ratchet_charged": charged}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument(
        "--allow-stale-backtest", action="store_true",
        help="Break-glass: evaluate despite a stale backtest summary "
             "(explicit operator decision; never the default)",
    )
    parser.add_argument(
        "--skip-auto-promotion", action="store_true",
        help="report only; skip the autonomous thresholded promotion pass",
    )
    args = parser.parse_args()
    if not args.db.exists():
        print(json.dumps({"status": "NO_DB", "db": str(args.db)}))
        return 1

    # Fail-closed evidence-freshness gate: promotion/demotion evaluation must
    # not run against a silently-aged backtest surface. A missing/unstamped/
    # stale summary blocks evaluation (and alerts) unless the operator breaks
    # the glass explicitly.
    from autonomy.backtest import backtest_summary_freshness  # noqa: E402

    freshness = backtest_summary_freshness()
    if freshness["is_stale"] and not args.allow_stale_backtest:
        try:
            from autonomy.alerts import emit_alert  # noqa: E402

            emit_alert(
                "BACKTEST_STALE",
                "readiness evaluation refused: backtest summary is stale "
                f"(age_hours={freshness.get('age_hours')}, "
                f"reason={freshness.get('reason')})",
                freshness,
            )
        except Exception:
            pass
        print(json.dumps({
            "status": "BLOCKED_STALE_BACKTEST",
            "backtest_freshness": freshness,
            "hint": "refresh with scripts/run_dummy_backtest.py, or pass "
                    "--allow-stale-backtest to break the glass explicitly",
        }, sort_keys=True))
        return 2

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

    # CLV evidence (WS-8 + Wave-2 D1 sports): map the CLV report's
    # specialist|market_type grain onto exact scopes (crypto AND now sports)
    # via the same helper the auto-promotion path uses, then feed each scope's
    # mean CLV to the readiness criteria (clv_nonneg_or_absent). Fail-open: a
    # missing/empty report leaves every scope's CLV absent, unchanged behavior.
    from autonomy.auto_promotion_runner import clv_by_exact_scope  # noqa: E402

    def _load_json_ro(path: Path) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            return {}

    clv_report = _load_json_ro(Path("runtime/autonomy/clv_report.json"))
    clv_exact = clv_by_exact_scope(clv_report, set(scope_rows))
    clv_by_scope = {
        scope: float(entry["mean"])
        for scope, entry in clv_exact.items()
        if entry.get("mean") is not None
    }

    built = build_readiness(
        scope_rows, promoted, now_ts, now_iso,
        clv_by_scope=clv_by_scope,
        challenger_gated_scopes=challenger_gated)

    # Crash-isolation rail (2026-07-24 audit): every optional writer below
    # runs through it -- failures are recorded, never swallowed.
    rail = WriterFailureRail()

    # Wave-14 (picks-first directive 2026-07-17): outcome-grounded pick
    # accuracy + calibration for the FUSED forecast, leading the report.
    # No market benchmark enters this section -- ground truth is settlements.
    # A picks failure must never cost the readiness report, but it lands in
    # the failures artifact and the section is marked UNAVAILABLE instead of
    # shipping a bare error string inside readiness_report.json.
    def _picks_section() -> dict:
        from autonomy.picks import (  # noqa: E402
            FUSED_SOURCE,
            llm_voice_sources,
            pick_accuracy_report,
        )

        picks_conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
        try:
            # Wave-61: grade every LLM voice that has settled observational
            # evidence alongside the fused headline, so "which model is
            # actually accurate" is a report fact instead of a guess.
            voices = llm_voice_sources(picks_conn)
            return pick_accuracy_report(
                picks_conn, sources=(FUSED_SOURCE, *voices),
            )
        finally:
            picks_conn.close()

    picks = rail.run("picks", _picks_section)
    built["report"]["picks"] = picks if picks is not None else {
        "status": "UNAVAILABLE", "reason": rail.error_for("picks"),
    }

    _write_json(REPORT_PATH, built["report"])
    merged_demotions = _merge_demotions(DEFAULT_DEMOTIONS_PATH, built["demotions"], now_iso)
    _write_json(DEFAULT_DEMOTIONS_PATH, merged_demotions)

    # Reliability calibration maps (WS-18): fit per-scope isotonic corrections
    # for the curated sources and write the reviewable artifact the calibrated
    # challenger wrappers consume.
    maps = fit_maps_from_rows(rows)
    _write_json(
        DEFAULT_MAPS_PATH,
        build_reliability_artifact(maps, generated_at=now_iso),
    )

    report = built["report"]
    summary = {
        "status": "OK",
        "scopes_evaluated": report["scopes_evaluated"],
        "promotion_candidates": report["promotion_candidates"],
        "new_auto_demotions": report["auto_demotions"],
        "total_auto_demotions": len(merged_demotions["demotions"]),
        "reliability_maps": len(maps),
        "clv_instrumented_scopes": len(clv_by_scope),
        "report": str(REPORT_PATH),
    }
    # WS-B: "where we bleed" line, fail-closed -- absent artifact/no bleeding
    # scope means the key is omitted entirely, never a fabricated line.
    where_we_bleed = _where_we_bleed()
    if where_we_bleed:
        summary["where_we_bleed"] = where_we_bleed

    # Wave-58: strict point-in-time eligibility per league, so the exact
    # moment enough stamped seasons exist for the sealed temporal holdout is
    # observable instead of discovered by a blocked run. Read-only; never
    # claims or consumes the holdout.
    def _holdout_eligibility() -> dict:
        from autonomy.sports.history_store import SportsHistoryStore
        from autonomy.sports_markets import SPORTS_LEAGUES

        store = SportsHistoryStore()
        eligibility: dict[str, dict] = {}
        for league in SPORTS_LEAGUES:
            row = store.evaluation_eligibility(league=league)
            eligibility[league] = {
                "eligible": row["eligible"],
                "final_candidates": row["final_candidates"],
                "rejection_reasons": row["rejection_reasons"],
            }
        return eligibility

    eligibility = rail.run("holdout_eligibility", _holdout_eligibility)
    if eligibility is not None:
        summary["holdout_eligibility"] = eligibility

    # Wave-74 (age-curve watch, "cut a year early"): promoted scopes whose
    # newer-half contested edge fell materially below their older half go on a
    # proactive watch list BEFORE auto-demotion fires. Disclosure only.
    def _age_curve_watch() -> list[dict]:
        watch: list[dict] = []
        for scope in sorted(promoted):
            entries = sorted(scope_rows.get(scope) or [])
            if len(entries) < 40:
                continue
            half = len(entries) // 2
            older = [edge for _ts, _cl, edge in entries[:half]]
            newer = [edge for _ts, _cl, edge in entries[half:]]
            older_mean = sum(older) / len(older)
            newer_mean = sum(newer) / len(newer)
            if newer_mean < older_mean - 0.01 and newer_mean < 0.005:
                watch.append({
                    "scope": scope,
                    "older_half_edge": round(older_mean, 5),
                    "newer_half_edge": round(newer_mean, 5),
                    "decline": round(older_mean - newer_mean, 5),
                })
        return sorted(watch, key=lambda item: -item["decline"])

    watch = rail.run("age_curve_watch", _age_curve_watch)
    if watch:
        summary["age_curve_watch"] = watch

    # Wave-76 (Dodgers "development never silently stops"): watch the tuner
    # and lake-ingestion machinery itself; a dead development lab becomes a
    # daily headline.
    def _development_tracker() -> dict:
        from autonomy.development_tracker import write_development_tracker
        from autonomy.sports.history_store import SportsHistoryStore as _Lake

        _dev_store = _Lake()
        try:
            return write_development_tracker(_dev_store)
        finally:
            _dev_store.close()

    development = rail.run("development_tracker", _development_tracker)
    if development and development.get("warnings"):
        summary["development_warnings"] = development["warnings"]

    # Wave-74 football-organization reports (self-scout, film room, recruiting
    # board): all report-only, all crash-isolated via the rail.
    def _self_scout() -> dict:
        from autonomy.self_scout import write_self_scout

        return write_self_scout(args.db)

    scout = rail.run("self_scout", _self_scout)
    if scout and scout.get("warnings"):
        summary["self_scout_warnings"] = scout["warnings"]

    def _film_room() -> None:
        from autonomy.film_room import write_film_room

        write_film_room(args.db)

    rail.run("film_room", _film_room)

    def _recruiting_board() -> dict:
        from autonomy.recruiting_board import write_recruiting_board

        return write_recruiting_board()

    board = rail.run("recruiting_board", _recruiting_board)
    if board is not None:
        summary["recruiting_class"] = board.get("by_stage", {})

    # Wave-77 (ablation science): each source's MARGINAL contribution to the
    # fused ensemble via disclosed leave-one-out approximation; redundancy
    # candidates surface for roster review. Report-only.
    def _fusion_ablation() -> dict:
        from autonomy.fusion_ablation import write_fusion_ablation

        return write_fusion_ablation(args.db)

    ablation = rail.run("fusion_ablation", _fusion_ablation)
    if ablation and ablation.get("redundancy_candidates"):
        summary["fusion_redundancy_candidates"] = (
            ablation["redundancy_candidates"]
        )

    # Wave-69: edge-concentration / selection-bias audit (report-only lens on
    # which sources' edge is dangerously narrow).
    def _edge_concentration() -> dict:
        from autonomy.edge_concentration import write_edge_concentration

        return write_edge_concentration(args.db)

    concentration = rail.run("edge_concentration", _edge_concentration)
    if concentration and concentration.get("narrow_edge_sources"):
        summary["narrow_edge_sources"] = concentration["narrow_edge_sources"]

    # Wave-65: build the model-authority evidence artifact + eligibility
    # report (measurement only; never authors the dossier, so no authority
    # can be self-granted).
    def _model_authority_evidence() -> dict:
        from forecasting.model_evidence_builder import build_and_write

        return build_and_write(args.db)

    evidence = rail.run("model_authority_evidence", _model_authority_evidence)
    if evidence is not None:
        summary["model_authority_evidence"] = {
            "scopes_measured": len(evidence["scopes"]),
            "governance_eligible_scopes": evidence["governance_eligible_scopes"],
            "dossier_authored": evidence["dossier_authored"],
        }

    # Wave-61: paired quant-vs-LLM incremental-value evidence (report-only;
    # the model authority registry keeps its own stricter dossier).
    def _llm_value_report() -> dict:
        from autonomy.llm_value_report import write_llm_value_report

        return write_llm_value_report(args.db)

    value = rail.run("llm_value_report", _llm_value_report) or {}
    graded = [v for v in value.get("voices", []) if v.get("status") == "OK"]
    if graded:
        summary["llm_value"] = {
            v["voice"]: {
                "paired_rows": v["paired_rows"],
                "voice_brier": v["voice_brier"],
                "fused_brier": v["fused_brier"],
                "adds_value_over_fused": v["adds_value_over_fused"],
            }
            for v in graded
        }

    # Wave-14: the one-line picks readout (fused accuracy is the headline
    # number under the picks-first directive; absent until rows accrue).
    def _fused_picks_readout() -> dict | None:
        fused = (built["report"].get("picks") or {}).get("sources", [])
        overall = fused[0]["overall"] if fused else {}
        if overall.get("n"):
            return {
                "n": overall["n"],
                "hit_rate": overall.get("hit_rate"),
                "brier": overall.get("brier"),
            }
        return None

    fused_picks = rail.run("fused_picks_summary", _fused_picks_readout)
    if fused_picks:
        summary["fused_picks"] = fused_picks

    # Autonomous thresholded promotion pass (owner directive 2026-07-16):
    # runs INSIDE this existing daily task path -- no new schtasks. Crash-
    # isolated: a failure here must never lose the readiness report above.
    if not args.skip_auto_promotion:
        try:
            from autonomy.auto_promotion_runner import run_auto_promotion

            state = run_auto_promotion(args.db)
            summary["auto_promotion"] = {
                "status": state.get("status"),
                "promoted": state.get("promoted", []),
                "escalated": state.get("escalated", []),
                "demoted": state.get("demoted", []),
                "deferred": state.get("deferred", []),
                "replacement_candidates": state.get("replacement_candidates", []),
                "declined": state.get("declined", []),
                "reasons": state.get("reasons", []),
            }
        except Exception as exc:  # fail-closed: no promotion, report intact
            summary["auto_promotion"] = {
                "status": "ERROR", "error": f"{type(exc).__name__}: {exc}"[:300],
            }

    # The masking fix (2026-07-24 audit): the failure record is written every
    # run -- an empty failures list is evidence the writers all ran, and a
    # stale artifact is itself detectable. Any recorded failure turns the run
    # red via EXIT_WRITER_FAILED, after every surviving artifact is written.
    write_failures_artifact(rail)
    if rail.failures:
        summary["status"] = "WRITER_FAILURES"
        summary["writer_failures"] = sorted({
            entry["writer"] for entry in rail.failures
        })
        summary["writer_failures_report"] = str(FAILURES_PATH)

    print(json.dumps(summary))
    return EXIT_WRITER_FAILED if rail.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
