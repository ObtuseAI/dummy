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
        102: ["2026-07-08"],                                # rested
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
    )
    contexts = client.projected_contexts(
        "2026-07-11", captured_at="2026-07-11T18:00:00+00:00",
    )
    lad = next(c for c in contexts if c.game_pk == 717465)
    assert lad.snapshot == "projected"
    assert lad.away_pitcher is not None
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
