"""Walk-forward, point-in-time evaluation of the lake's rating analytics.

Grades five rating models over every league's completed games in the history
lake (no look-ahead) and prints Brier / hit-rate / edge-over-coin-flip per
league -- the honest read-out the recursive tuner acts on. Read-only; touches
nothing live. Run after a history backfill.

Usage:
  python scripts/run_dummy_sports_walk_forward.py
  python scripts/run_dummy_sports_walk_forward.py --league nfl

2026-07-24 (Wave-85): this used to build every model for every league and only
then write the artifact, outside the try/finally. Task Scheduler kills the task
at its execution-time limit, and a killed process writes NOTHING -- so
DummyWF_ncaamb had been returning SCHED_S_TASK_TERMINATED (267014) and
discarding every model it had already computed, on every single run. ncaamb is
the largest league in the lake (104,819 games), so it never once persisted a
full result set, and no watchdog task covered it.

Two changes, mirroring the readiness report's writer rail:
  * results persist after EACH model, so a kill costs at most the in-flight
    model instead of the whole run;
  * a wall-clock budget stops the run cleanly BEFORE the scheduler kills it,
    and every model not reached is recorded as skipped with a reason rather
    than silently missing.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.sports.history_store import SportsHistoryStore  # noqa: E402
from autonomy.sports.walk_forward import walk_forward_glicko  # noqa: E402

LEAGUES = ("mlb", "wnba", "nba", "nfl", "nhl", "ncaaf", "ncaamb")
MODEL_NAMES = ("glicko", "pythagenpat", "mov_elo", "four_factors", "epa")
ARTIFACT = Path("runtime/autonomy/sports_walk_forward.json")

# Distinct exit code for "ran, persisted what it finished, but did not finish".
# The scheduled task shows red, which is the truth: the evaluation is partial.
EXIT_INCOMPLETE = 4

# Default budget sits under the tightest scheduled execution-time limit
# (DummyWF_<league> is PT20M) so the run ends on its own terms and writes its
# record, instead of being killed with nothing to show.
DEFAULT_BUDGET_S = 900.0


def _budget_s() -> float:
    try:
        return float(os.environ.get("DUMMY_WF_BUDGET_S", DEFAULT_BUDGET_S))
    except (TypeError, ValueError):
        return DEFAULT_BUDGET_S


def _persist(leagues: dict, skipped: list[dict], status: str) -> None:
    """Merge into the artifact the dashboard reads (keep leagues not re-run)."""
    prior: dict = {}
    try:
        prior = json.loads(ARTIFACT.read_text(encoding="utf-8")).get("leagues", {})
    except Exception:  # noqa: BLE001
        prior = {}
    for league, models in leagues.items():
        merged = dict(prior.get(league) or {})
        merged.update(models)          # never drop a model this run didn't reach
        prior[league] = merged
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    tmp = ARTIFACT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "models": list(MODEL_NAMES),
        "status": status,
        "skipped": skipped,
        "leagues": prior,
    }), encoding="utf-8")
    tmp.replace(ARTIFACT)


def main() -> int:
    ap = argparse.ArgumentParser(description="Walk-forward evaluate lake rating analytics.")
    ap.add_argument("--league", choices=LEAGUES, default=None)
    ap.add_argument(
        "--budget-s", type=float, default=None,
        help="wall-clock budget; 0 disables (default DUMMY_WF_BUDGET_S or 900)",
    )
    args = ap.parse_args()

    from autonomy.signals.sports_glicko import _HOME_ADVANTAGE
    from autonomy.signals.sports_pythagorean import _HOME_ADVANTAGE_PROB
    from autonomy.sports.walk_forward import (
        walk_forward_epa, walk_forward_four_factors, walk_forward_mov_elo,
        walk_forward_pythagorean,
    )

    budget = _budget_s() if args.budget_s is None else float(args.budget_s)
    deadline = (time.monotonic() + budget) if budget > 0 else None

    store = SportsHistoryStore()
    leagues = [args.league] if args.league else list(LEAGUES)
    results: dict[str, dict] = {}
    skipped: list[dict] = []
    try:
        for league in leagues:
            hadv = _HOME_ADVANTAGE.get(league, 35.0)
            hadv_p = _HOME_ADVANTAGE_PROB.get(league, 0.05)
            builders = {
                "glicko": lambda lg=league, h=hadv: walk_forward_glicko(
                    store, league=lg, home_advantage=h),
                "pythagenpat": lambda lg=league, p=hadv_p: walk_forward_pythagorean(
                    store, league=lg, home_advantage_prob=p),
                "mov_elo": lambda lg=league, h=hadv: walk_forward_mov_elo(
                    store, league=lg, home_advantage=h),
                "four_factors": lambda lg=league, p=hadv_p: walk_forward_four_factors(
                    store, league=lg, home_advantage_prob=p),
                "epa": lambda lg=league: walk_forward_epa(store, league=lg),
            }
            for name, build in builders.items():
                if deadline is not None and time.monotonic() > deadline:
                    skipped.append({
                        "league": league, "model": name, "reason": "budget_exhausted",
                    })
                    continue
                started = time.monotonic()
                try:
                    result = build()
                except Exception as exc:  # noqa: BLE001 -- one model never costs the rest
                    skipped.append({
                        "league": league, "model": name,
                        "reason": f"{type(exc).__name__}: {exc}"[:200],
                    })
                    continue
                results.setdefault(league, {})[name] = result
                # Persist per MODEL: a kill now costs the in-flight model only.
                _persist(results, skipped, "RUNNING")
                if result["n"]:
                    print(
                        f"[{league}] {name}: n={result['n']} hit={result['hit_rate']}"
                        f" edge={result['edge_vs_baseline']}"
                        f" ({time.monotonic() - started:.1f}s)"
                    )
            if (results.get(league, {}).get("glicko") or {}).get("n") == 0:
                print(f"[{league}] no completed games in the lake yet")
    finally:
        store.close()

    status = "PARTIAL" if skipped else "OK"
    _persist(results, skipped, status)
    print(f"wrote {ARTIFACT} status={status} skipped={len(skipped)}")
    for entry in skipped:
        print(f"  SKIPPED {entry['league']}/{entry['model']}: {entry['reason']}")
    return EXIT_INCOMPLETE if skipped else 0


if __name__ == "__main__":
    raise SystemExit(main())
