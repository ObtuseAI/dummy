from __future__ import annotations

from dataclasses import replace as _replace

from autonomy.sports.statsapi import (
    MlbGameContext, LineupSlot, apply_confirmed_lineups, parse_boxscore_lineups,
    parse_schedule,
)


def test_context_provenance_marks_present_and_missing_fields():
    ctx = MlbGameContext(
        game_pk=717465,
        snapshot="projected",
        captured_at="2026-07-11T22:05:00+00:00",
        home="LAD",
        away="SF",
        venue="Dodger Stadium",
        home_probable_pitcher_id=477132,
        away_probable_pitcher_id=None,
        wind_speed_mph=8.0,
        wind_direction="Out To CF",
        temperature_f=74.0,
    )
    prov = ctx.field_provenance()
    assert prov["home_probable_pitcher_id"] is True
    assert prov["away_probable_pitcher_id"] is False
    assert prov["wind_direction"] is True
    # A field never set is reported absent, never invented.
    assert prov["home_lineup"] is False
    assert ctx.home_lineup == ()


def test_context_provenance_treats_zero_reading_as_present():
    ctx = MlbGameContext(
        game_pk=1, snapshot="projected", captured_at="2026-07-11T22:05:00+00:00",
        home="SF", away="LAD", wind_speed_mph=0.0, temperature_f=0.0,
    )
    prov = ctx.field_provenance()
    assert prov["wind_speed_mph"] is True   # calm wind is a real reading, not missing
    assert prov["temperature_f"] is True


_SCHEDULE_FIXTURE = {
    "dates": [
        {
            "date": "2026-07-11",
            "games": [
                {
                    "gamePk": 717465,
                    "teams": {
                        "home": {"team": {"abbreviation": "LAD"},
                                  "probablePitcher": {"id": 477132, "fullName": "C. Kershaw"}},
                        "away": {"team": {"abbreviation": "SF"},
                                  "probablePitcher": {"id": 592789, "fullName": "L. Webb"}},
                    },
                    "venue": {"name": "Dodger Stadium"},
                    "weather": {"condition": "Clear", "temp": "74", "wind": "8 mph, Out To CF"},
                },
                {
                    "gamePk": 717466,
                    "teams": {
                        "home": {"team": {"abbreviation": "NYY"}},
                        "away": {"team": {"abbreviation": "BOS"}},
                    },
                },
            ],
        }
    ]
}


def test_parse_schedule_extracts_probables_venue_weather():
    games = parse_schedule(_SCHEDULE_FIXTURE, captured_at="2026-07-11T18:00:00+00:00")
    assert len(games) == 2
    lad = next(g for g in games if g.game_pk == 717465)
    assert (lad.home, lad.away) == ("LAD", "SF")
    assert lad.snapshot == "projected"
    assert lad.home_probable_pitcher_id == 477132
    assert lad.away_probable_pitcher_id == 592789
    assert lad.venue == "Dodger Stadium"
    assert lad.temperature_f == 74.0
    assert lad.wind_speed_mph == 8.0
    assert lad.wind_direction == "Out To CF"


def test_parse_schedule_tolerates_missing_blocks():
    games = parse_schedule(_SCHEDULE_FIXTURE, captured_at="2026-07-11T18:00:00+00:00")
    nyy = next(g for g in games if g.game_pk == 717466)
    assert nyy.home_probable_pitcher_id is None
    assert nyy.venue is None
    assert nyy.temperature_f is None
    assert nyy.field_provenance()["temperature_f"] is False


_BOX_FIXTURE = {
    "teams": {
        "home": {
            "battingOrder": [605141, 518692],
            "players": {
                "ID605141": {"person": {"fullName": "M. Betts", "batSide": {"code": "R"}}},
                "ID518692": {"person": {"fullName": "F. Freeman", "batSide": {"code": "L"}}},
            },
        },
        "away": {
            "battingOrder": [592885],
            "players": {
                "ID592885": {"person": {"fullName": "T. Estrada", "batSide": {"code": "R"}}},
            },
        },
    }
}


def test_parse_boxscore_lineups_orders_and_reads_handedness():
    home, away = parse_boxscore_lineups(_BOX_FIXTURE)
    assert [s.player_id for s in home] == [605141, 518692]
    assert home[0].batting_order == 1 and home[0].bats == "R"
    assert home[1].name == "F. Freeman" and home[1].bats == "L"
    assert [s.player_id for s in away] == [592885]


def test_apply_confirmed_lineups_promotes_snapshot():
    base = MlbGameContext(
        game_pk=1, snapshot="projected", captured_at="2026-07-11T18:00:00+00:00",
        home="LAD", away="SF",
    )
    home, away = parse_boxscore_lineups(_BOX_FIXTURE)
    confirmed = apply_confirmed_lineups(
        base, home, away, captured_at="2026-07-11T22:40:00+00:00",
    )
    assert confirmed.snapshot == "confirmed"
    assert confirmed.captured_at == "2026-07-11T22:40:00+00:00"
    assert len(confirmed.home_lineup) == 2
    assert base.home_lineup == ()  # original untouched (frozen dataclass)


def test_parse_boxscore_lineups_missing_batting_order_is_empty():
    home, away = parse_boxscore_lineups({"teams": {"home": {}, "away": {}}})
    assert home == () and away == ()


def test_parse_boxscore_lineups_missing_players_keeps_ids_without_enrichment():
    box = {"teams": {"home": {"battingOrder": [605141]}, "away": {}}}
    home, away = parse_boxscore_lineups(box)
    assert len(home) == 1
    assert home[0].player_id == 605141
    assert home[0].name is None and home[0].bats is None
    assert away == ()


def test_parse_boxscore_lineups_empty_dict_does_not_raise():
    home, away = parse_boxscore_lineups({})
    assert home == () and away == ()


from autonomy.sports.statsapi import parse_pitcher_rates

_PEOPLE_FIXTURE = {
    "people": [
        {
            "id": 592789,
            "fullName": "L. Webb",
            "pitchHand": {"code": "R"},
            "stats": [
                {"splits": [{"stat": {
                    "era": "3.25",
                    "strikeOuts": 150,
                    "baseOnBalls": 40,
                    "battersFaced": 750,
                    "homeRunsPer9": "0.85",
                }}]}
            ],
        }
    ]
}


def test_parse_pitcher_rates_computes_k_and_bb_pct():
    rates = parse_pitcher_rates(_PEOPLE_FIXTURE)
    assert rates.player_id == 592789
    assert rates.throws == "R"
    assert rates.era == 3.25
    assert rates.k_pct == round(150 / 750, 4)
    assert rates.bb_pct == round(40 / 750, 4)
    assert rates.hr9 == 0.85


def test_parse_pitcher_rates_returns_none_on_empty():
    assert parse_pitcher_rates({"people": []}) is None


def test_parse_pitcher_rates_zero_denominator_yields_none():
    payload = {"people": [{"id": 5, "stats": [{"splits": [{"stat": {
        "era": "2.00", "strikeOuts": 10, "baseOnBalls": 3, "battersFaced": 0,
    }}]}]}]}
    rates = parse_pitcher_rates(payload)
    assert rates.era == 2.0
    assert rates.k_pct is None and rates.bb_pct is None  # no divide-by-zero


def test_parse_pitcher_rates_missing_stats_yields_none_rates():
    rates = parse_pitcher_rates({"people": [{"id": 7, "fullName": "X"}]})
    assert rates.player_id == 7
    assert rates.era is None and rates.k_pct is None and rates.hr9 is None


def test_parse_pitcher_rates_absent_id_returns_none():
    assert parse_pitcher_rates({"people": [{"fullName": "No Id"}]}) is None


from autonomy.sports.statsapi import bullpen_fatigue, park_factors


def test_park_factors_known_and_neutral():
    run, hr = park_factors("Coors Field")
    assert run > 1.0 and hr > 1.0  # hitter park
    assert park_factors("Unknown Yard") == (1.0, 1.0)
    assert park_factors(None) == (None, None)


def test_bullpen_fatigue_rises_with_recent_use():
    recent = {
        101: ["2026-07-10", "2026-07-09", "2026-07-08"],  # 3 straight days
        102: ["2026-07-08"],                                # 3 days ago -> light residual (0.2)
        103: [],
    }
    fatigue = bullpen_fatigue(recent, as_of="2026-07-11")
    assert fatigue[101] > fatigue[102] > 0.0
    assert fatigue[103] == 0.0
    assert 0.0 <= fatigue[101] <= 1.0


def test_bullpen_fatigue_skips_malformed_dates():
    fatigue = bullpen_fatigue({9: ["not-a-date", "2026-07-10"]}, as_of="2026-07-11")
    assert fatigue[9] == 0.5  # only the valid yesterday counts; bad string skipped, no raise


def test_bullpen_fatigue_saturates_at_one():
    # More weight than 1.0 of appearances still caps at 1.0.
    heavy = {4: ["2026-07-10", "2026-07-09", "2026-07-08", "2026-07-07"]}
    assert bullpen_fatigue(heavy, as_of="2026-07-11")[4] == 1.0


from autonomy.sports.statsapi import StatsApiClient


def test_client_assembles_projected_context_with_pitcher_rates():
    def fake_schedule(date_iso):
        assert date_iso == "2026-07-11"
        return _SCHEDULE_FIXTURE

    def fake_people(player_id):
        assert player_id in {477132, 592789}
        return _PEOPLE_FIXTURE

    client = StatsApiClient(
        fetch_schedule=fake_schedule, fetch_people=fake_people,
        fetch_pitcher_splits=lambda pid: {"people": []},  # keep hermetic; no network
    )
    contexts = client.projected_contexts(
        "2026-07-11", captured_at="2026-07-11T18:00:00+00:00",
    )
    lad = next(c for c in contexts if c.game_pk == 717465)
    assert lad.snapshot == "projected"
    assert lad.away_pitcher is not None
    assert lad.home_pitcher is not None
    assert lad.away_pitcher.k_pct == round(150 / 750, 4)
    assert lad.park_run_factor == 0.98  # Dodger Stadium from the table


def test_client_confirms_lineups_via_boxscore():
    client = StatsApiClient(fetch_boxscore=lambda pk: _BOX_FIXTURE)
    base = MlbGameContext(
        game_pk=717465, snapshot="projected",
        captured_at="2026-07-11T18:00:00+00:00", home="LAD", away="SF",
    )
    confirmed = client.confirm_lineups(base, captured_at="2026-07-11T22:40:00+00:00")
    assert confirmed.snapshot == "confirmed"
    assert len(confirmed.home_lineup) == 2


def test_client_swallows_pitcher_fetch_failure_to_none():
    def boom_people(player_id):
        raise RuntimeError("statsapi down")

    client = StatsApiClient(
        fetch_schedule=lambda d: _SCHEDULE_FIXTURE, fetch_people=boom_people,
    )
    contexts = client.projected_contexts(
        "2026-07-11", captured_at="2026-07-11T18:00:00+00:00",
    )
    lad = next(c for c in contexts if c.game_pk == 717465)
    assert lad.home_pitcher is None and lad.away_pitcher is None  # failure swallowed
    assert lad.park_run_factor == 0.98  # rest of hydration still succeeded


def test_bullpen_fatigue_weights_by_recency():
    fatigue = bullpen_fatigue(
        {1: ["2026-07-10"], 2: ["2026-07-09"], 3: ["2026-07-08"]},
        as_of="2026-07-11",
    )
    assert fatigue[1] == 0.5 and fatigue[2] == 0.3 and fatigue[3] == 0.2


def test_bullpen_fatigue_accepts_full_datetime_as_of():
    fatigue = bullpen_fatigue({3: ["2026-07-10"]}, as_of="2026-07-11T22:05:00+00:00")
    assert fatigue[3] == 0.5  # datetime as_of parsed down to its date


def test_client_clear_cache_forces_pitcher_refetch():
    calls = []
    def counting_people(pid):
        calls.append(pid)
        return _PEOPLE_FIXTURE
    client = StatsApiClient(
        fetch_schedule=lambda d: _SCHEDULE_FIXTURE, fetch_people=counting_people,
        fetch_pitcher_splits=lambda pid: {"people": []},  # keep hermetic; no network
    )
    client.projected_contexts("2026-07-11", captured_at="2026-07-11T18:00:00+00:00")
    first = len(calls)
    client.clear_cache()
    client.projected_contexts("2026-07-11", captured_at="2026-07-11T18:00:00+00:00")
    assert len(calls) > first  # cache cleared -> refetched


from autonomy.sports.statsapi import BatterRates


def test_batter_rates_attaches_to_context_and_reports_provenance():
    from autonomy.sports.statsapi import MlbGameContext
    rates = BatterRates(
        player_id=605141, name="M. Betts", bats="R",
        plate_appearances=600, k_pct=0.16, bb_pct=0.10,
        obp=0.36, slg=0.52, iso=0.24,
    )
    ctx = MlbGameContext(
        game_pk=1, snapshot="confirmed", captured_at="2026-07-11T22:40:00+00:00",
        home="LAD", away="SF", batter_rates={605141: rates},
    )
    assert ctx.batter_rates[605141].obp == 0.36
    assert ctx.field_provenance()["batter_rates"] is True
    # Absent by default (empty map) -> reported absent.
    empty = MlbGameContext(
        game_pk=2, snapshot="projected", captured_at="2026-07-11T18:00:00+00:00",
        home="NYY", away="BOS",
    )
    assert empty.field_provenance()["batter_rates"] is False


from autonomy.sports.statsapi import parse_batter_rates

_BATTER_FIXTURE = {
    "people": [
        {
            "id": 605141,
            "fullName": "M. Betts",
            "batSide": {"code": "R"},
            "stats": [
                {"splits": [{"stat": {
                    "plateAppearances": 600,
                    "strikeOuts": 90,
                    "baseOnBalls": 60,
                    "obp": "0.360",
                    "slg": "0.520",
                    "avg": "0.280",
                }}]}
            ],
        }
    ]
}


def test_parse_batter_rates_computes_rates_and_iso():
    rates = parse_batter_rates(_BATTER_FIXTURE)
    assert rates.player_id == 605141
    assert rates.bats == "R"
    assert rates.plate_appearances == 600
    assert rates.k_pct == round(90 / 600, 4)
    assert rates.bb_pct == round(60 / 600, 4)
    assert rates.obp == 0.360
    assert rates.slg == 0.520
    assert rates.iso == round(0.520 - 0.280, 4)  # slg - avg


def test_parse_batter_rates_none_on_empty_and_missing_denominator():
    assert parse_batter_rates({"people": []}) is None
    zero = {"people": [{"id": 7, "stats": [{"splits": [{"stat": {
        "plateAppearances": 0, "strikeOuts": 3, "baseOnBalls": 1, "slg": "0.400",
    }}]}]}]}
    rates = parse_batter_rates(zero)
    assert rates.player_id == 7
    assert rates.k_pct is None and rates.bb_pct is None  # no divide-by-zero
    assert rates.iso is None  # no avg -> ISO unknown


def test_client_hydrate_batter_rates_fills_lineup_and_swallows_failures():
    from autonomy.sports.statsapi import StatsApiClient, MlbGameContext, LineupSlot

    def fake_batter(player_id):
        if player_id == 999:
            raise RuntimeError("statsapi down")
        return {"people": [{"id": player_id, "fullName": f"P{player_id}",
                            "batSide": {"code": "L"}, "stats": [{"splits": [{"stat": {
                                "plateAppearances": 500, "strikeOuts": 100,
                                "baseOnBalls": 50, "obp": "0.340", "slg": "0.450",
                                "avg": "0.270"}}]}]}]}

    client = StatsApiClient(
        fetch_batter_people=fake_batter,
        fetch_batter_splits=lambda pid: {"people": []},  # keep hermetic; no network
    )
    ctx = MlbGameContext(
        game_pk=1, snapshot="confirmed", captured_at="2026-07-11T22:40:00+00:00",
        home="LAD", away="SF",
        home_lineup=(LineupSlot(1, 605141), LineupSlot(2, 999)),
        away_lineup=(LineupSlot(1, 592885),),
    )
    hydrated = client.hydrate_batter_rates(ctx)
    assert set(hydrated.batter_rates) == {605141, 592885}  # 999 failed -> absent
    assert hydrated.batter_rates[605141].k_pct == round(100 / 500, 4)
    assert ctx.batter_rates == {}  # original untouched (frozen)


def test_client_clear_cache_forces_batter_refetch():
    calls = []
    def counting_batter(pid):
        calls.append(pid)
        return {"people": [{"id": pid, "fullName": "B", "batSide": {"code": "R"},
                            "stats": [{"splits": [{"stat": {
                                "plateAppearances": 500, "strikeOuts": 100,
                                "baseOnBalls": 50, "obp": "0.340", "slg": "0.450",
                                "avg": "0.270"}}]}]}]}
    from autonomy.sports.statsapi import StatsApiClient, MlbGameContext, LineupSlot
    client = StatsApiClient(
        fetch_batter_people=counting_batter,
        fetch_batter_splits=lambda pid: {"people": []},  # keep hermetic; no network
    )
    ctx = MlbGameContext(
        game_pk=1, snapshot="confirmed", captured_at="2026-07-11T22:40:00+00:00",
        home="LAD", away="SF", home_lineup=(LineupSlot(1, 605141),),
    )
    client.hydrate_batter_rates(ctx)
    first = len(calls)
    client.clear_cache()
    client.hydrate_batter_rates(ctx)
    assert len(calls) > first  # cache cleared -> refetched


from autonomy.sports.statsapi import batter_rates_vs, pitcher_rates_vs


def test_batter_rates_vs_selects_split_by_pitcher_hand():
    from autonomy.sports.statsapi import BatterRates
    vs_l = BatterRates(player_id=1, k_pct=0.15, bb_pct=0.12, obp=0.380, slg=0.520, iso=0.24)
    vs_r = BatterRates(player_id=1, k_pct=0.24, bb_pct=0.07, obp=0.300, slg=0.400, iso=0.14)
    batter = BatterRates(player_id=1, k_pct=0.20, bb_pct=0.09, obp=0.340, slg=0.450,
                         iso=0.18, vs_lhp=vs_l, vs_rhp=vs_r)
    assert batter_rates_vs(batter, "L").obp == 0.380   # facing a lefty -> vs-LHP split
    assert batter_rates_vs(batter, "R").obp == 0.300   # facing a righty -> vs-RHP split
    # No split populated -> fall back to the overall line.
    plain = BatterRates(player_id=2, k_pct=0.20, bb_pct=0.09, obp=0.340, slg=0.450, iso=0.18)
    assert batter_rates_vs(plain, "L").obp == 0.340
    assert batter_rates_vs(None, "L") is None


def test_pitcher_rates_vs_selects_split_by_batter_hand():
    from autonomy.sports.statsapi import PitcherRates
    vs_l = PitcherRates(player_id=3, k_pct=0.30, bb_pct=0.06, hr9=0.9)
    vs_r = PitcherRates(player_id=3, k_pct=0.20, bb_pct=0.09, hr9=1.4)
    pitcher = PitcherRates(player_id=3, k_pct=0.25, bb_pct=0.08, hr9=1.1,
                           vs_lhb=vs_l, vs_rhb=vs_r)
    assert pitcher_rates_vs(pitcher, "L").hr9 == 0.9
    assert pitcher_rates_vs(pitcher, "R").hr9 == 1.4
    assert pitcher_rates_vs(pitcher, "S").hr9 == 1.1   # switch hitter -> overall


def test_rates_vs_ignores_empty_small_sample_split():
    from autonomy.sports.statsapi import BatterRates, PitcherRates, batter_rates_vs, pitcher_rates_vs
    empty_b = BatterRates(player_id=1)  # all rates None (0 PA vs that hand)
    batter = BatterRates(player_id=1, k_pct=0.20, obp=0.340, slg=0.450, iso=0.15, vs_lhp=empty_b)
    assert batter_rates_vs(batter, "L") is batter   # empty split ignored -> overall
    empty_p = PitcherRates(player_id=2)
    pitcher = PitcherRates(player_id=2, k_pct=0.22, bb_pct=0.08, hr9=1.2, vs_lhb=empty_p)
    assert pitcher_rates_vs(pitcher, "L") is pitcher


# --- Task 2: parse + hydrate StatsAPI handedness splits ---------------------

from autonomy.sports.statsapi import parse_batter_splits, parse_pitcher_splits

_BATTER_SPLITS_FIXTURE = {
    "people": [
        {
            "id": 605141,
            "fullName": "M. Betts",
            "batSide": {"code": "R"},
            "stats": [
                {"splits": [
                    {"split": {"code": "vl", "description": "vs Left"}, "stat": {
                        "plateAppearances": 150, "strikeOuts": 40, "baseOnBalls": 15,
                        "obp": "0.330", "slg": "0.410", "avg": "0.250",
                    }},
                    {"split": {"code": "vr", "description": "vs Right"}, "stat": {
                        "plateAppearances": 420, "strikeOuts": 90, "baseOnBalls": 50,
                        "obp": "0.360", "slg": "0.500", "avg": "0.280",
                    }},
                ]}
            ],
        }
    ]
}


def test_parse_batter_splits_returns_vs_lhp_and_vs_rhp():
    vs_lhp, vs_rhp = parse_batter_splits(_BATTER_SPLITS_FIXTURE)
    assert vs_lhp.player_id == 605141
    assert vs_lhp.k_pct == round(40 / 150, 4)
    assert vs_lhp.bb_pct == round(15 / 150, 4)
    assert vs_lhp.obp == 0.330
    assert vs_lhp.slg == 0.410
    assert vs_lhp.iso == round(0.410 - 0.250, 4)
    assert vs_rhp.player_id == 605141
    assert vs_rhp.k_pct == round(90 / 420, 4)
    assert vs_rhp.bb_pct == round(50 / 420, 4)
    assert vs_rhp.obp == 0.360
    assert vs_rhp.slg == 0.500


def test_parse_batter_splits_returns_none_none_on_missing_payload():
    assert parse_batter_splits({"people": []}) == (None, None)
    assert parse_batter_splits({}) == (None, None)
    assert parse_batter_splits({"people": [{"id": 1}]}) == (None, None)  # no stats


_PITCHER_SPLITS_FIXTURE = {
    "people": [
        {
            "id": 592789,
            "fullName": "L. Webb",
            "pitchHand": {"code": "R"},
            "stats": [
                {"splits": [
                    {"split": {"code": "vl", "description": "vs Left"}, "stat": {
                        "era": "3.10", "strikeOuts": 60, "baseOnBalls": 20,
                        "battersFaced": 300, "homeRunsPer9": "0.70",
                    }},
                    {"split": {"code": "vr", "description": "vs Right"}, "stat": {
                        "era": "3.40", "strikeOuts": 90, "baseOnBalls": 20,
                        "battersFaced": 450, "homeRunsPer9": "0.95",
                    }},
                ]}
            ],
        }
    ]
}


def test_parse_pitcher_splits_returns_vs_lhb_and_vs_rhb():
    vs_lhb, vs_rhb = parse_pitcher_splits(_PITCHER_SPLITS_FIXTURE)
    assert vs_lhb.player_id == 592789
    assert vs_lhb.era == 3.10
    assert vs_lhb.k_pct == round(60 / 300, 4)
    assert vs_lhb.bb_pct == round(20 / 300, 4)
    assert vs_lhb.hr9 == 0.70
    assert vs_rhb.player_id == 592789
    assert vs_rhb.era == 3.40
    assert vs_rhb.k_pct == round(90 / 450, 4)
    assert vs_rhb.hr9 == 0.95


def test_parse_pitcher_splits_returns_none_none_on_missing_payload():
    assert parse_pitcher_splits({"people": []}) == (None, None)
    assert parse_pitcher_splits({}) == (None, None)
    assert parse_pitcher_splits({"people": [{"id": 1}]}) == (None, None)  # no stats


def test_client_hydrates_batter_splits_onto_vs_lhp_vs_rhp():
    client = StatsApiClient(
        fetch_batter_people=lambda pid: _BATTER_FIXTURE,
        fetch_batter_splits=lambda pid: _BATTER_SPLITS_FIXTURE,
    )
    rates = client._batter(605141)
    assert rates.plate_appearances == 600  # overall rates intact
    assert rates.vs_lhp is not None and rates.vs_lhp.obp == 0.330
    assert rates.vs_rhp is not None and rates.vs_rhp.obp == 0.360


def test_client_hydrates_pitcher_splits_onto_vs_lhb_vs_rhb():
    client = StatsApiClient(
        fetch_people=lambda pid: _PEOPLE_FIXTURE,
        fetch_pitcher_splits=lambda pid: _PITCHER_SPLITS_FIXTURE,
    )
    rates = client._pitcher(592789)
    assert rates.era == 3.25  # overall rates intact
    assert rates.vs_lhb is not None and rates.vs_lhb.era == 3.10
    assert rates.vs_rhb is not None and rates.vs_rhb.era == 3.40


def test_client_swallows_batter_splits_fetch_failure_leaves_vs_none():
    def boom_splits(pid):
        raise RuntimeError("statsapi down")

    client = StatsApiClient(
        fetch_batter_people=lambda pid: _BATTER_FIXTURE,
        fetch_batter_splits=boom_splits,
    )
    rates = client._batter(605141)
    assert rates is not None
    assert rates.plate_appearances == 600  # overall rates intact -> split failure didn't crash hydration
    assert rates.vs_lhp is None and rates.vs_rhp is None  # splits failure swallowed


def test_client_swallows_pitcher_splits_fetch_failure_leaves_vs_none():
    def boom_splits(pid):
        raise RuntimeError("statsapi down")

    client = StatsApiClient(
        fetch_people=lambda pid: _PEOPLE_FIXTURE,
        fetch_pitcher_splits=boom_splits,
    )
    rates = client._pitcher(592789)
    assert rates is not None
    assert rates.era == 3.25  # overall rates intact -> split failure didn't crash hydration
    assert rates.vs_lhb is None and rates.vs_rhb is None  # splits failure swallowed


# --- Task 4: per-team bullpen quality ---------------------------------------

from autonomy.sports.statsapi import parse_team_bullpen


def test_context_gains_bullpen_rates_fields_defaulting_to_none():
    ctx = MlbGameContext(
        game_pk=1, snapshot="projected", captured_at="2026-07-11T18:00:00+00:00",
        home="LAD", away="SF",
    )
    assert ctx.home_bullpen_rates is None
    assert ctx.away_bullpen_rates is None
    prov = ctx.field_provenance()
    assert prov["home_bullpen_rates"] is False
    assert prov["away_bullpen_rates"] is False


def test_context_bullpen_rates_present_reports_true_in_provenance():
    from autonomy.sports.statsapi import PitcherRates
    pen = PitcherRates(player_id=-1, era=3.60, k_pct=0.26, bb_pct=0.09, hr9=1.05)
    ctx = MlbGameContext(
        game_pk=1, snapshot="projected", captured_at="2026-07-11T18:00:00+00:00",
        home="LAD", away="SF", home_bullpen_rates=pen,
    )
    assert ctx.field_provenance()["home_bullpen_rates"] is True
    assert ctx.field_provenance()["away_bullpen_rates"] is False


_TEAM_BULLPEN_FIXTURE = {
    "stats": [
        {"splits": [{"stat": {
            "era": "3.60",
            "strikeOuts": 520,
            "baseOnBalls": 180,
            "battersFaced": 2000,
            "homeRunsPer9": "1.05",
        }}]}
    ]
}


def test_parse_team_bullpen_computes_rates_from_relief_split():
    rates = parse_team_bullpen(_TEAM_BULLPEN_FIXTURE)
    assert rates.player_id == -1  # team aggregate, not a person
    assert rates.era == 3.60
    assert rates.k_pct == round(520 / 2000, 4)
    assert rates.bb_pct == round(180 / 2000, 4)
    assert rates.hr9 == 1.05


def test_parse_team_bullpen_none_on_missing_or_empty_payload():
    assert parse_team_bullpen({}) is None
    assert parse_team_bullpen({"stats": []}) is None
    assert parse_team_bullpen({"stats": [{"splits": []}]}) is None
    assert parse_team_bullpen({"stats": [{}]}) is None


def test_parse_team_bullpen_never_raises_on_malformed_payload():
    assert parse_team_bullpen({"stats": "not-a-list"}) is None
    assert parse_team_bullpen({"stats": [None]}) is None
    assert parse_team_bullpen({"stats": [{"splits": [None]}]}) is not None
    assert parse_team_bullpen(None) is None  # never raises, even on a non-dict payload


def test_parse_team_bullpen_zero_denominator_yields_none_rates_not_crash():
    payload = {"stats": [{"splits": [{"stat": {
        "era": "4.10", "strikeOuts": 5, "baseOnBalls": 2, "battersFaced": 0,
    }}]}]}
    rates = parse_team_bullpen(payload)
    assert rates.era == 4.10
    assert rates.k_pct is None and rates.bb_pct is None  # no divide-by-zero
    assert rates.hr9 is None  # homeRunsPer9 absent -> None, not invented
