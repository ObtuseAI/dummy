"""Walk-forward, point-in-time evaluation of the lake's rating analytics.

Grades Glicko-2 over every league's completed games in the history lake (no
look-ahead) and prints Brier / hit-rate / edge-over-coin-flip per league --
the honest read-out the recursive tuner acts on. Read-only; touches nothing
live. Run after a history backfill.

Usage:
  python scripts/run_dummy_sports_walk_forward.py
  python scripts/run_dummy_sports_walk_forward.py --league nfl
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.sports.history_store import SportsHistoryStore  # noqa: E402
from autonomy.sports.walk_forward import walk_forward_glicko  # noqa: E402

LEAGUES = ("mlb", "wnba", "nba", "nfl", "nhl", "ncaaf", "ncaamb")
ARTIFACT = Path("runtime/autonomy/sports_walk_forward.json")


def main() -> int:
    ap = argparse.ArgumentParser(description="Walk-forward evaluate lake rating analytics.")
    ap.add_argument("--league", choices=LEAGUES, default=None)
    args = ap.parse_args()

    from autonomy.signals.sports_glicko import _HOME_ADVANTAGE

    store = SportsHistoryStore()
    leagues = [args.league] if args.league else list(LEAGUES)
    results: dict[str, dict] = {}
    try:
        for league in leagues:
            r = walk_forward_glicko(store, league=league,
                                    home_advantage=_HOME_ADVANTAGE.get(league, 35.0))
            results[league] = r
            if r["n"] == 0:
                print(f"[{league}] no completed games in the lake yet")
                continue
            print(f"[{league}] n={r['n']} brier={r['brier']} hit={r['hit_rate']} "
                  f"logloss={r['log_loss']} edge_vs_coin={r['edge_vs_baseline']}")
    finally:
        store.close()

    # Merge into the artifact the dashboard reads (keep leagues not re-run).
    import json
    from datetime import datetime, timezone

    prior = {}
    try:
        prior = json.loads(ARTIFACT.read_text(encoding="utf-8")).get("leagues", {})
    except Exception:  # noqa: BLE001
        prior = {}
    prior.update(results)
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    tmp = ARTIFACT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": "glicko2", "leagues": prior,
    }), encoding="utf-8")
    tmp.replace(ARTIFACT)
    print(f"wrote {ARTIFACT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
