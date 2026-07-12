"""Print mlb_pa_sim market probabilities for a neutral and a lopsided matchup.

Pure/offline eyeball check of the plate-appearance engine -- not a pytest test.
Reflects the Task 3 re-calibration for realistic run COMPOSITION: a neutral matchup
(average batters vs average pitchers) should land close to real MLB's ~8.5 expected
total runs and a modest home edge (~0.54), with a realistic run process -- HR/PA
~0.033 and HR ~0.13-0.15 of hits, not an HR-inflated shortcut. YRFI lands ~0.43
(raised from ~0.40 by the probabilistic _advance baserunning fix), still modestly
below real MLB's ~0.55 -- the residual gap is a subtler artifact of the
independent per-PA run process, not the (now-fixed) station-to-station single
advancement. A strong-vs-weak matchup should still tilt the winner market well
above 0.5 without breaking the [0, 1] bounds.
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
    from autonomy.sports.mlb_pa_sim import plate_appearance_distribution  # noqa: E402

    # Composition eyeball: a neutral average batter should hit HRs at ~real MLB rates.
    b = BatterRates(player_id=1, k_pct=0.20, bb_pct=0.09, obp=0.340, slg=0.450, iso=0.15)
    p = PitcherRates(player_id=2, k_pct=0.22, bb_pct=0.08, hr9=1.2)
    d = plate_appearance_distribution(b, p)
    hits = d["single"] + d["double"] + d["triple"] + d["hr"]
    print("Neutral run composition (target: HR/PA ~0.033, HR share of hits ~0.15):")
    print(f"  HR/PA={d['hr']:.4f}  HR/hits={d['hr'] / hits:.3f}")
    print("\nNeutral matchup (equal lineups, real-MLB calibration check):")
    print("  target: expected_total_runs in [8.0, 9.2], home_win in [0.51, 0.575];")
    print("  yrfi ~0.42 (raised by probabilistic _advance; still < real ~0.55)")
    print(json.dumps(simulate_game_markets(_ctx(0.15, 0.15), seed=1, sims=4000), indent=2))
    print("\nStrong home vs weak away (home_win should sit well above 0.5):")
    print(json.dumps(simulate_game_markets(_ctx(0.28, 0.09), seed=1, sims=4000), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
