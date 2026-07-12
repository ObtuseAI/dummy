# scripts/verify_mlb_matchup_intelligence_live.py
"""One-shot live check of the MLB matchup-intelligence layer (Tasks 1-5)
against a real slate: handedness splits, per-team bullpen quality, and
divisional/rivalry awareness.

For the first upcoming game with a probable pitcher, fetches that pitcher's
real handedness splits and prints overall / vs-LHB / vs-RHB rates (proving
the split fetch works end to end), fetches one team's bullpen aggregate and
prints the parsed rate, and prints is_divisional / is_rivalry for the
matchup's two teams. Read-only, keyless. Not part of the hermetic test suite
-- if StatsAPI or the network is unreachable this prints the failure
honestly rather than fabricating data.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.sports.mlb_matchups import is_divisional, is_rivalry
from autonomy.sports.statsapi import (
    PitcherRates,
    StatsApiClient,
    default_fetch_pitcher_splits,
    default_fetch_team_bullpen,
    parse_pitcher_splits,
    parse_team_bullpen,
)


def _print_pitcher_rates(label: str, rates: PitcherRates | None) -> None:
    if rates is None:
        print(f"    {label}: not available")
        return
    print(
        f"    {label}: k_pct={rates.k_pct} bb_pct={rates.bb_pct} "
        f"hr9={rates.hr9} era={rates.era}"
    )


def _team_id_for_game(schedule_payload: dict, game_pk: int, side: str) -> int | None:
    """Pull a team's numeric id straight from the raw schedule payload.

    MlbGameContext only retains the team abbreviation, not the numeric id
    default_fetch_team_bullpen needs, so this reads the same 'dates ->
    games -> teams' structure parse_schedule walks.
    """
    for date_block in schedule_payload.get("dates", []) or []:
        for game in date_block.get("games", []) or []:
            if game.get("gamePk") == game_pk:
                team = ((game.get("teams", {}) or {}).get(side, {}) or {}).get("team", {}) or {}
                return team.get("id")
    return None


def main() -> int:
    date_iso = sys.argv[1] if len(sys.argv) > 1 else datetime.now(timezone.utc).date().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    client = StatsApiClient()

    try:
        schedule_payload = client.fetch_schedule(date_iso)
    except Exception as exc:
        print(f"StatsAPI schedule fetch failed for {date_iso}: {exc!r}")
        return 1

    try:
        contexts = client.projected_contexts(date_iso, captured_at=now)
    except Exception as exc:
        print(f"projected_contexts parse/hydrate failed for {date_iso}: {exc!r}")
        return 1

    if not contexts:
        print(f"No MLB games found for {date_iso}")
        return 0

    # Pick the first game with a probable pitcher posted on either side.
    target = None
    for ctx in contexts:
        if ctx.home_probable_pitcher_id is not None or ctx.away_probable_pitcher_id is not None:
            target = ctx
            break
    if target is None:
        print(f"{date_iso}: {len(contexts)} games, none have a probable pitcher posted yet")
        return 0

    print(f"{date_iso}: {len(contexts)} games; using {target.away}@{target.home} (gamePk={target.game_pk})")

    if target.home_probable_pitcher_id is not None:
        side, pitcher_id = "home", target.home_probable_pitcher_id
    else:
        side, pitcher_id = "away", target.away_probable_pitcher_id
    print(f"Probable pitcher ({side}): player_id={pitcher_id}")

    # 1. Handedness splits, end-to-end through the live fetch + parser.
    print("Pitcher rates:")
    overall = target.home_pitcher if side == "home" else target.away_pitcher
    _print_pitcher_rates("overall (season)", overall)
    try:
        splits_payload = default_fetch_pitcher_splits(pitcher_id)
        vs_lhb, vs_rhb = parse_pitcher_splits(splits_payload)
        _print_pitcher_rates("vs LHB", vs_lhb)
        _print_pitcher_rates("vs RHB", vs_rhb)
    except Exception as exc:
        print(f"    pitcher splits fetch/parse failed: {exc!r}")

    # 2. Team bullpen quality, end-to-end through the live fetch + parser.
    team_id = _team_id_for_game(schedule_payload, target.game_pk, side)
    team_abbr = target.home if side == "home" else target.away
    if team_id is not None:
        print(f"Team bullpen ({team_abbr}, team_id={team_id}):")
        try:
            bullpen_payload = default_fetch_team_bullpen(int(team_id))
            bullpen = parse_team_bullpen(bullpen_payload)
            _print_pitcher_rates("bullpen aggregate", bullpen)
        except Exception as exc:
            print(f"    team bullpen fetch/parse failed: {exc!r}")
    else:
        print(f"Team id for {team_abbr} not resolvable from the schedule payload - bullpen probe skipped")

    # 3. Divisional / rivalry awareness -- pure, offline, no network call.
    print(f"is_divisional({target.home}, {target.away}) = {is_divisional(target.home, target.away)}")
    print(f"is_rivalry({target.home}, {target.away}) = {is_rivalry(target.home, target.away)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
