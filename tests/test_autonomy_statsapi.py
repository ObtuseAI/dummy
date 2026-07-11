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
