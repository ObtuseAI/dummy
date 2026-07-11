from __future__ import annotations

from autonomy.sports.ballpark_weather import (
    BALLPARKS, GameWeather, parse_hourly_weather, weather_factors,
)


def test_ballpark_table_covers_all_30_teams():
    assert len(BALLPARKS) == 30
    coors = BALLPARKS["COL"]
    assert coors.is_dome is False
    assert 39.0 < coors.lat < 40.0 and -105.5 < coors.lon < -104.5
    assert 0.0 <= coors.cf_bearing_deg < 360.0
    # A dome exists and is flagged.
    assert BALLPARKS["TB"].is_dome is True


_HOURLY_FIXTURE = {
    "hourly": {
        "time": ["2026-07-11T22:00", "2026-07-11T23:00"],
        "temperature_2m": [88.0, 90.0],
        "wind_speed_10m": [12.0, 14.0],
        "wind_direction_10m": [180.0, 200.0],
    }
}


def test_parse_hourly_weather_reads_the_right_hour():
    gw = parse_hourly_weather(_HOURLY_FIXTURE, 1)
    assert gw.temperature_f == 90.0
    assert gw.wind_speed_mph == 14.0
    assert gw.wind_direction_deg == 200.0


def test_parse_hourly_weather_tolerates_missing():
    assert parse_hourly_weather({"hourly": {}}, 0) is None
    assert parse_hourly_weather(_HOURLY_FIXTURE, 99) is None  # out of range


def test_neutral_and_dome_weather_are_identity():
    neutral = GameWeather(temperature_f=70.0, wind_speed_mph=0.0, wind_direction_deg=0.0)
    assert weather_factors(neutral, cf_bearing_deg=0.0) == (1.0, 1.0)
    assert weather_factors(None, cf_bearing_deg=90.0) == (1.0, 1.0)
    hot = GameWeather(temperature_f=95.0, wind_speed_mph=20.0, wind_direction_deg=0.0)
    assert weather_factors(hot, cf_bearing_deg=0.0, is_dome=True) == (1.0, 1.0)


def test_hot_weather_raises_both_factors():
    hot = GameWeather(temperature_f=95.0, wind_speed_mph=0.0, wind_direction_deg=0.0)
    hr, run = weather_factors(hot, cf_bearing_deg=0.0)
    assert hr > 1.0 and run > 1.0


def test_wind_out_to_center_raises_hr_more_than_wind_in():
    # cf_bearing 0 (CF is due north). Wind FROM 0deg blows toward 180 (in from CF);
    # wind FROM 180 blows toward 0 (out to CF).
    out = GameWeather(temperature_f=70.0, wind_speed_mph=15.0, wind_direction_deg=180.0)
    into = GameWeather(temperature_f=70.0, wind_speed_mph=15.0, wind_direction_deg=0.0)
    hr_out, _ = weather_factors(out, cf_bearing_deg=0.0)
    hr_in, _ = weather_factors(into, cf_bearing_deg=0.0)
    assert hr_out > 1.0 > hr_in
