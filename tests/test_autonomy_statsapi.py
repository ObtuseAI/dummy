from __future__ import annotations

from autonomy.sports.statsapi import MlbGameContext


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
