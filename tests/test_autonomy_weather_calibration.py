"""Tests for weather historical-forecast backfill calibration."""

from __future__ import annotations

import json

from autonomy.signals.weather_openmeteo import OpenMeteoWeatherSignal
from autonomy.weather_calibration import (
    calibrate_city,
    load_bias_corrections,
    load_sigma_overrides,
    run_backfill,
)


def _forecast_series(dates, values):
    # Three identical model columns -> ensemble mean equals the series.
    return {
        "time": dates,
        "temperature_2m_max_gfs_seamless": values,
        "temperature_2m_max_ecmwf_ifs025": values,
        "temperature_2m_max_icon_seamless": values,
    }


def _actual_series(dates, values):
    return {"time": dates, "temperature_2m_max": values}


def test_calibrate_city_computes_bias_and_sigma():
    dates = [f"2026-06-{d:02d}" for d in range(1, 21)]
    forecasts = [80.0 + i * 0.1 for i in range(20)]
    # Actuals run 2F cooler than forecast, with alternating +/-1 noise.
    actuals = [f - 2.0 + (1.0 if i % 2 else -1.0) for i, f in enumerate(forecasts)]

    result = calibrate_city(
        "NY", kind="HIGH", lookback_days=60, today_iso="2026-07-01T00:00:00+00:00",
        fetch_forecast=lambda *a: _forecast_series(dates, forecasts),
        fetch_actuals=lambda *a: _actual_series(dates, actuals),
    )
    assert result["usable"] is True
    assert result["samples"] == 20
    assert abs(result["bias_f"] - 2.0) < 0.2  # forecast runs ~2F hot
    assert result["sigma_f"] >= 0.8


def test_calibrate_city_insufficient_samples():
    dates = ["2026-06-01", "2026-06-02"]
    result = calibrate_city(
        "NY", today_iso="2026-07-01T00:00:00+00:00",
        fetch_forecast=lambda *a: _forecast_series(dates, [80.0, 81.0]),
        fetch_actuals=lambda *a: _actual_series(dates, [79.0, 80.0]),
    )
    assert result["usable"] is False


def test_calibrate_city_handles_fetch_error():
    def boom(*a):
        raise RuntimeError("network")

    result = calibrate_city("NY", today_iso="2026-07-01T00:00:00+00:00",
                            fetch_forecast=boom, fetch_actuals=boom)
    assert result["usable"] is False
    assert "error" in result


def test_run_backfill_writes_loadable_artifact(tmp_path):
    dates = [f"2026-06-{d:02d}" for d in range(1, 21)]
    forecasts = [85.0] * 20
    actuals = [82.0] * 20  # constant 3F hot bias, zero variance -> sigma floored

    out = tmp_path / "weather_calibration.json"
    report = run_backfill(
        city_codes=["NY", "CHI"], kind="HIGH", lookback_days=60, out_path=out,
        today_iso="2026-07-01T00:00:00+00:00",
        fetch_forecast=lambda *a: _forecast_series(dates, forecasts),
        fetch_actuals=lambda *a: _actual_series(dates, actuals),
    )
    assert report["usable_count"] == 2
    assert out.exists()

    sigmas = load_sigma_overrides(out)
    biases = load_bias_corrections(out)
    assert set(sigmas) == {"NY", "CHI"}
    assert abs(biases["NY"] - 3.0) < 0.01
    assert sigmas["NY"] >= 0.8


def test_calibration_flows_into_signal_probability(tmp_path):
    dates = [f"2026-06-{d:02d}" for d in range(1, 21)]
    out = tmp_path / "cal.json"
    run_backfill(
        city_codes=["NY"], kind="HIGH", lookback_days=60, out_path=out,
        today_iso="2026-07-01T00:00:00+00:00",
        fetch_forecast=lambda *a: _forecast_series(dates, [85.0] * 20),
        fetch_actuals=lambda *a: _actual_series(dates, [80.0] * 20),  # 5F hot bias
    )
    from autonomy.ontology import MarketView, Vertical

    market = MarketView(
        ticker="KXHIGHNY-26JUL10-T84", title="", vertical=Vertical.WEATHER,
        status="active", close_time="2026-07-10T00:00:00Z",
        yes_bid=40, yes_ask=50, no_bid=50, no_ask=60, volume=100, liquidity=100,
        raw={"strike_type": "greater", "floor_strike": 84.0},
    )
    # Raw forecast 86 would say ">=84.5" very likely YES; the 5F hot bias
    # correction pulls the effective mean to ~81, flipping it toward NO.
    biased = OpenMeteoWeatherSignal(
        fetch_daily_temps=lambda *a: [86.0, 86.0, 86.0],
        sigma_overrides=load_sigma_overrides(out),
        bias_corrections=load_bias_corrections(out),
    )
    uncorrected = OpenMeteoWeatherSignal(fetch_daily_temps=lambda *a: [86.0, 86.0, 86.0])
    assert biased.generate(market).probability_yes < uncorrected.generate(market).probability_yes
