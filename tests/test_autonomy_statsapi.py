from __future__ import annotations

from autonomy.sports.statsapi import MlbGameContext, parse_schedule


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
