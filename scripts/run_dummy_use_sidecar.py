#!/usr/bin/env python
"""Universal Sports Engine sidecar pass (Wave-22).

One crash-isolated invocation, scheduled every few hours:

  1. OUTCOMES:    yesterday's + today's finals per in-season league -> append
                  to the USE training tape (``use_outcomes.jsonl``) in its
                  HistoricalGame vocabulary.
  2. PREDICTIONS: today's + tomorrow's pre-game slates -> the sidecar's
                  champion ensemble ForecastMoments per matchup ->
                  ``use_predictions.json`` (the UseSimSignal's whole input).
  3. TUNE (gated): once the tape holds >= --min-tune-outcomes finals, invoke
                  USE's own recursive improvement over a chronological split
                  of OUR outcomes; its champion governance decides promotion
                  by its own preregistered gates. Self-activates as history
                  accrues -- the same discipline as every other loop.

Read/observe only on dummy's side; USE's governance owns its champions.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.use_bridge import (  # noqa: E402
    LEAGUE_TO_USE,
    OUTCOMES_PATH,
    append_outcomes,
    engine_src,
    generate_predictions,
)


def _dates(offsets: list[int]) -> list[str]:
    now = datetime.now(timezone.utc)
    return [(now + timedelta(days=off)).strftime("%Y%m%d") for off in offsets]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-tune-outcomes", type=int, default=300)
    parser.add_argument("--skip-tune", action="store_true")
    args = parser.parse_args()

    if engine_src() is None:
        print(json.dumps({"status": "ENGINE_ABSENT",
                          "hint": "clone ObtuseAI/universal-sports-engine or set DUMMY_USE_ENGINE_PATH"}))
        generate_predictions({})   # writes the ENGINE_ABSENT artifact
        return 0

    from autonomy.sports.espn import EspnClient

    espn = EspnClient()
    finals: dict[str, list] = {}
    upcoming: dict[str, list] = {}
    for league in LEAGUE_TO_USE:
        games: list = []
        for dates in _dates([-1, 0, 1]):
            try:
                games.extend(espn.games(league, dates))
            except Exception:
                continue
        finals[league] = [g for g in games if g.status == "post"]
        upcoming[league] = [g for g in games if g.status == "pre"]

    appended = append_outcomes(finals)
    payload = generate_predictions(upcoming)

    summary = {
        "status": payload.get("status"),
        "outcomes_appended": appended,
        "predictions": len(payload.get("rows") or []),
    }

    if not args.skip_tune:
        try:
            tape_lines = sum(
                1 for _ in OUTCOMES_PATH.open(encoding="utf-8"))
        except OSError:
            tape_lines = 0
        summary["outcomes_on_tape"] = tape_lines
        if tape_lines >= args.min_tune_outcomes:
            summary["tune"] = _tune()
        else:
            summary["tune"] = {
                "status": "WAITING_FOR_EVIDENCE",
                "have": tape_lines,
                "need": args.min_tune_outcomes,
            }

    print(json.dumps(summary, sort_keys=True))
    return 0


def _tune() -> dict:
    """Chronological split of our tape -> USE's own recursive improvement."""
    try:
        from universal_sports_engine.autotune import (
            load_tuning_config,
            run_recursive_improvement,
        )
        from universal_sports_engine.accuracy import HistoricalGame

        records = []
        with OUTCOMES_PATH.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    records.append(json.loads(line))
                except (ValueError, TypeError):
                    continue
        records.sort(key=lambda r: str(r.get("decision_time") or ""))
        # Chronological 60/25/15 split per USE's preregistered discipline.
        n = len(records)
        games = []
        for index, record in enumerate(records):
            split = ("train" if index < n * 0.60
                     else "calibration" if index < n * 0.85 else "test")
            from datetime import datetime, timezone

            try:
                decided = datetime.fromisoformat(
                    str(record.get("decision_time")).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                decided = datetime(2026, 1, 1, tzinfo=timezone.utc)
            games.append(HistoricalGame(
                game_id=str(record.get("game_id") or index),
                league=str(record["league"]),
                decision_time=decided,
                features_available_at=decided,
                outcome_time=decided,
                home_score=int(record["home_score"]),
                away_score=int(record["away_score"]),
                home_strength=float(record.get("home_strength") or 1.0),
                away_strength=float(record.get("away_strength") or 1.0),
                split=split,
            ))
        config = load_tuning_config(
            Path(engine_src()).parent / "AUTONOMY_CONFIG.json")
        results = run_recursive_improvement(tuple(games), config)
        return {
            "status": "OK",
            "leagues_tuned": [r.league for r in results],
        }
    except Exception as exc:
        return {"status": f"TUNE_ERROR:{type(exc).__name__}",
                "error": str(exc)[:200]}


if __name__ == "__main__":
    raise SystemExit(main())
