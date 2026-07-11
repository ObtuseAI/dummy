"""Print mlb_pa_sim market probabilities for a neutral and a lopsided matchup.

Pure/offline eyeball check of the plate-appearance engine -- not a pytest test.
Reflects the Task 6 calibration: a neutral matchup (average batters vs average
pitchers) should land close to real MLB's ~8.5 expected total runs, ~0.55 YRFI,
and a near coin-flip home_win; a strong-vs-weak matchup should tilt the winner
market well above 0.5 without breaking the market probabilities' [0, 1] bounds.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.sports.mlb_pa_sim import simulate_game_markets  # noqa: E402
from autonomy.sports.statsapi import (  # noqa: E402
    BatterRates, LineupSlot, MlbGameContext, PitcherRates,
)


def _ctx(home_iso: float, away_iso: float) -> MlbGameContext:
    rates = {}
    home = tuple(LineupSlot(i + 1, 100 + i, bats="R") for i in range(9))
    away = tuple(LineupSlot(i + 1, 200 + i, bats="R") for i in range(9))
    for i in range(9):
        rates[100 + i] = BatterRates(player_id=100 + i, bats="R", k_pct=0.20,
                                     bb_pct=0.09, obp=0.340, slg=0.300 + home_iso, iso=home_iso)
        rates[200 + i] = BatterRates(player_id=200 + i, bats="R", k_pct=0.20,
                                     bb_pct=0.09, obp=0.340, slg=0.300 + away_iso, iso=away_iso)
    return MlbGameContext(
        game_pk=1, snapshot="confirmed", captured_at="2026-07-11T22:40:00+00:00",
        home="HOME", away="AWAY", home_lineup=home, away_lineup=away,
        home_pitcher=PitcherRates(player_id=9, throws="R", k_pct=0.22, bb_pct=0.08, hr9=1.2),
        away_pitcher=PitcherRates(player_id=8, throws="R", k_pct=0.22, bb_pct=0.08, hr9=1.2),
        batter_rates=rates, park_run_factor=1.0, park_hr_factor=1.0,
    )


def main() -> int:
    print("Neutral matchup (equal lineups, real-MLB calibration check):")
    print("  target: expected_total_runs in [8.0, 9.5], yrfi in [0.48, 0.62], home_win in [0.47, 0.58]")
    print(json.dumps(simulate_game_markets(_ctx(0.15, 0.15), seed=1, sims=4000), indent=2))
    print("\nStrong home vs weak away (home_win should sit well above 0.5):")
    print(json.dumps(simulate_game_markets(_ctx(0.28, 0.09), seed=1, sims=4000), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
