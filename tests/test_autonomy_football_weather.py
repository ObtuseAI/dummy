"""WS-10: NFL/NCAAF outdoor-weather adjustment to game TOTALS only."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.sports_intelligence import TeamSportsIntelligenceSignal
from autonomy.sports.espn import EspnClient, Game
from autonomy.sports.football_weather import (
    HEAVY_PRECIP_CODES,
    STACK_CAP,
    FootballWeatherReading,
    football_weather_adjustment,
    parse_football_weather,
    stadium_for,
    total_points_adjustment,
)
from autonomy.sports.team_scores import LEAGUE_SCORE_CONFIGS, TeamScoreModel

FIXTURE = Path(__file__).parent / "fixtures" / "open_meteo_football_weather_kc_probe.json"


# =========================================================================
# Unit-level: total_points_adjustment / stadium_for
# =========================================================================


def test_dome_bypass_zero_regardless_of_synthetic_weather():
    hostile = FootballWeatherReading(temperature_f=5.0, wind_speed_mph=45.0, weather_code=99.0)
    adjustment, features = total_points_adjustment(hostile, is_dome=True)
    assert adjustment == 0.0
    assert features == {}


def test_dome_stadiums_are_flagged_in_the_nfl_table():
    for team in ("ARI", "ATL", "DAL", "DET", "HOU", "IND", "LV", "MIN", "NO", "LAR", "LAC"):
        stadium = stadium_for("nfl", team)
        assert stadium is not None and stadium.is_dome is True, team
    for team in ("KC", "GB", "BUF", "CHI"):
        stadium = stadium_for("nfl", team)
        assert stadium is not None and stadium.is_dome is False, team


def test_wind_tiers_and_boundaries():
    assert total_points_adjustment(FootballWeatherReading(70.0, 25.0, 0.0))[0] == -2.5
    assert total_points_adjustment(FootballWeatherReading(70.0, 20.0, 0.0))[0] == -2.5  # >= boundary
    assert total_points_adjustment(FootballWeatherReading(70.0, 19.9, 0.0))[0] == -1.5
    assert total_points_adjustment(FootballWeatherReading(70.0, 17.0, 0.0))[0] == -1.5
    assert total_points_adjustment(FootballWeatherReading(70.0, 15.0, 0.0))[0] == -1.5  # >= boundary
    assert total_points_adjustment(FootballWeatherReading(70.0, 14.9, 0.0))[0] == 0.0
    assert total_points_adjustment(FootballWeatherReading(70.0, 10.0, 0.0))[0] == 0.0


def test_temp_and_precip_adjustments():
    assert total_points_adjustment(FootballWeatherReading(10.0, 0.0, 0.0))[0] == -1.5
    assert total_points_adjustment(FootballWeatherReading(15.0, 0.0, 0.0))[0] == -1.5  # <= boundary
    assert total_points_adjustment(FootballWeatherReading(15.1, 0.0, 0.0))[0] == 0.0
    for code in HEAVY_PRECIP_CODES:
        assert total_points_adjustment(FootballWeatherReading(70.0, 0.0, code))[0] == -1.0
    # Light/moderate codes (drizzle, light rain) are NOT "heavy" -> no adjustment.
    for code in (0.0, 1.0, 51.0, 61.0, 63.0, 71.0, 80.0):
        assert total_points_adjustment(FootballWeatherReading(70.0, 0.0, code))[0] == 0.0


def test_stack_cap_bounds_total_at_negative_4():
    # wind>=20 (-2.5) + temp<=15 (-1.5) + heavy precip (-1.0) = -5.0 raw, capped at -4.0.
    adjustment, features = total_points_adjustment(FootballWeatherReading(10.0, 25.0, 65.0))
    assert adjustment == STACK_CAP == -4.0
    assert features["weather_total_adjustment"] == -4.0


def test_feature_logging_has_raw_reading_and_applied_adjustment():
    adjustment, features = total_points_adjustment(FootballWeatherReading(12.0, 22.0, 65.0))
    assert features["weather_wind_mph"] == 22.0
    assert features["weather_temp_f"] == 12.0
    assert features["weather_code"] == 65.0
    assert features["weather_total_adjustment"] == adjustment


def test_missing_reading_and_unmapped_stadium_are_zero_and_empty():
    assert total_points_adjustment(None) == (0.0, {})
    assert stadium_for("nfl", "ZZZ") is None
    assert stadium_for("ncaaf", "ZZZ") is None
    assert stadium_for("mlb", "KC") is None  # not an nfl/ncaaf league -> no table at all


def test_parse_football_weather_defensive_on_malformed_payloads():
    assert parse_football_weather({}, 0) is None
    assert parse_football_weather({"hourly": "not-a-dict"}, 0) is None
    assert parse_football_weather({"hourly": {"temperature_2m": [70.0]}}, 0) is None  # missing series
    assert parse_football_weather(
        {"hourly": {"temperature_2m": [70.0], "wind_speed_10m": [5.0], "weathercode": [0]}}, 5,
    ) is None  # out-of-range index
    assert parse_football_weather(
        {"hourly": {"temperature_2m": ["bad"], "wind_speed_10m": [5.0], "weathercode": [0]}}, 0,
    ) is None  # non-numeric


# =========================================================================
# football_weather_adjustment: end-to-end fail-closed orchestration
# =========================================================================


def test_fetch_failure_zero_adjustment_byte_identical_to_disabled():
    """Brief's own key test: fetch failure -> zero adjustment, byte-identical
    to the feature disabled outright."""
    disabled = football_weather_adjustment("nfl", "ZZZ", "2026-09-13T18:00Z")  # unmapped team

    def boom(*_a, **_k):
        raise RuntimeError("open-meteo down")

    failed_fetch = football_weather_adjustment("nfl", "KC", "2026-09-13T18:00Z", fetch_fn=boom)

    assert disabled == (0.0, {})
    assert failed_fetch == disabled


def test_fetch_returns_empty_or_malformed_payload_is_also_zero():
    assert football_weather_adjustment(
        "nfl", "KC", "2026-09-13T18:00Z", fetch_fn=lambda *a, **k: {}) == (0.0, {})
    assert football_weather_adjustment(
        "nfl", "KC", "2026-09-13T18:00Z",
        fetch_fn=lambda *a, **k: {"hourly": {"temperature_2m": [1]}},
    ) == (0.0, {})


def test_unparseable_kickoff_timestamp_is_zero():
    assert football_weather_adjustment("nfl", "KC", None) == (0.0, {})
    assert football_weather_adjustment("nfl", "KC", "not-a-date") == (0.0, {})
    assert football_weather_adjustment("nfl", "KC", "2026-13-40T99:99Z") == (0.0, {})


def test_dome_team_never_even_attempts_a_fetch():
    calls = []

    def spy(*args):
        calls.append(args)
        return {"hourly": {"temperature_2m": [70.0] * 24, "wind_speed_10m": [30.0] * 24,
                            "weathercode": [95] * 24}}

    adjustment, features = football_weather_adjustment("nfl", "ARI", "2026-09-13T18:00Z", fetch_fn=spy)
    assert adjustment == 0.0 and features == {}
    assert calls == []  # dome short-circuits before any fetch is attempted


def test_college_top_40_hit_and_uncovered_school_both_fail_closed():
    working_fetch = lambda *a, **k: {  # noqa: E731
        "hourly": {"temperature_2m": [70.0] * 24, "wind_speed_10m": [3.0] * 24,
                    "weathercode": [0] * 24},
    }
    covered = football_weather_adjustment("ncaaf", "TEX", "2026-09-13T18:00Z", fetch_fn=working_fetch)
    assert covered == (0.0, {"weather_wind_mph": 3.0, "weather_temp_f": 70.0,
                              "weather_code": 0.0, "weather_total_adjustment": 0.0})
    # Uncovered school (not in the top-40 table) -> honest zero, no fetch attempted.
    calls = []

    def spy(*a, **k):
        calls.append(a)
        return working_fetch(*a, **k)

    uncovered = football_weather_adjustment("ncaaf", "ZZZZ", "2026-09-13T18:00Z", fetch_fn=spy)
    assert uncovered == (0.0, {})
    assert calls == []


# =========================================================================
# Build-time probe fixture: a real (trimmed) Open-Meteo response parses.
# =========================================================================


def test_build_time_probe_fixture_parses_into_a_reading():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert "weathercode" in payload["hourly"]
    assert "precipitation" in payload["hourly"]
    reading = parse_football_weather(payload, 2)  # trimmed slice's 3rd entry (orig. hour 12)
    assert reading is not None
    assert reading.temperature_f == pytest.approx(70.0)
    assert reading.wind_speed_mph == pytest.approx(3.2)
    assert reading.weather_code == 0.0


# =========================================================================
# Hook-level: TeamSportsIntelligenceSignal wiring (NFL + NCAAF)
# =========================================================================

NOW = datetime(2026, 9, 13, 16, 0, tzinfo=timezone.utc)


def _market(ticker: str, title: str, **raw) -> MarketView:
    payload = {"event_ticker": ticker.rsplit("-", 1)[0], **raw}
    return MarketView(
        ticker=ticker, title=title, vertical=Vertical.SPORTS, status="open",
        close_time=(NOW + timedelta(hours=6)).isoformat(),
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56,
        volume=500, liquidity=1_000, raw=payload,
    )


class _AlwaysActive:
    def active(self, _league):
        return True


def _severe_weather_fetch(*_a, **_k):
    # wind 25 (-2.5) + temp 10F (-1.5) + heavy precip 65 (-1.0) = -5.0 raw,
    # capped at STACK_CAP (-4.0) -- deliberately extreme so the total moves
    # unmistakably while winner/spread must stay untouched.
    return {"hourly": {
        "temperature_2m": [10.0] * 24,
        "wind_speed_10m": [25.0] * 24,
        "weathercode": [65] * 24,
    }}


def _nfl_signal(tmp_path, fetch_football_weather=None) -> TeamSportsIntelligenceSignal:
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    game = Game("g1", "nfl", "KC", "BUF", "pre", None, "2026-09-13T18:00Z",
                home_name="Kansas City Chiefs", away_name="Buffalo Bills")
    client._cache[("nfl", "20260913")] = [game]
    models = {key: TeamScoreModel(key) for key in LEAGUE_SCORE_CONFIGS}
    return TeamSportsIntelligenceSignal(
        espn=client, models=models, model_dir=tmp_path, seasons=_AlwaysActive(),
        fetch_football_weather=fetch_football_weather or (lambda *a, **k: {}),
    )


def _ncaaf_signal(tmp_path, fetch_football_weather=None) -> TeamSportsIntelligenceSignal:
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    game = Game("g2", "ncaaf", "TEX", "OU", "pre", None, "2026-09-13T18:00Z",
                home_name="Texas Longhorns", away_name="Oklahoma Sooners")
    client._cache[("ncaaf", "20260913")] = [game]
    models = {key: TeamScoreModel(key) for key in LEAGUE_SCORE_CONFIGS}
    return TeamSportsIntelligenceSignal(
        espn=client, models=models, model_dir=tmp_path, seasons=_AlwaysActive(),
        fetch_football_weather=fetch_football_weather or (lambda *a, **k: {}),
    )


def test_hook_nfl_total_moves_but_winner_and_spread_stay_byte_identical(tmp_path):
    baseline = _nfl_signal(tmp_path / "a")
    windy = _nfl_signal(tmp_path / "b", fetch_football_weather=_severe_weather_fetch)

    winner_market = _market("KXNFLGAME-26SEP13KCBUF-KC", "Kansas City Chiefs vs Buffalo Bills Winner?")
    spread_market = _market(
        "KXNFLSPREAD-26SEP13KCBUF-KC3",
        "Kansas City Chiefs vs Buffalo Bills Spread", floor_strike=2.5)
    total_market = _market(
        "KXNFLTOTAL-26SEP13KCBUF-44",
        "Kansas City Chiefs vs Buffalo Bills Total Points", floor_strike=44.5)

    baseline_winner = baseline.generate(winner_market)
    windy_winner = windy.generate(winner_market)
    baseline_spread = baseline.generate(spread_market)
    windy_spread = windy.generate(spread_market)
    baseline_total = baseline.generate(total_market)
    windy_total = windy.generate(total_market)

    assert all(s is not None for s in (
        baseline_winner, windy_winner, baseline_spread, windy_spread, baseline_total, windy_total))

    # Winner/spread: BYTE-IDENTICAL despite a maximal weather adjustment.
    assert windy_winner.probability_yes == baseline_winner.probability_yes
    assert windy_winner.uncertainty == baseline_winner.uncertainty
    assert windy_spread.probability_yes == baseline_spread.probability_yes
    assert windy_spread.uncertainty == baseline_spread.uncertainty

    # Total: MUST move, and in the expected direction (colder/windier ->
    # lower expected total -> lower P(over)).
    assert windy_total.probability_yes < baseline_total.probability_yes
    assert windy_total.features["weather_total_adjustment"] == STACK_CAP
    assert windy_total.features["weather_wind_mph"] == 25.0
    assert windy_total.features["weather_temp_f"] == 10.0
    assert windy_total.features["weather_code"] == 65.0

    # Weather features never leak onto winner/spread signals.
    assert "weather_total_adjustment" not in windy_winner.features
    assert "weather_total_adjustment" not in windy_spread.features
    assert windy_winner.features["challenger_only"] is True
    assert windy_total.features["challenger_only"] is True


def test_hook_ncaaf_total_moves_but_winner_and_spread_stay_byte_identical(tmp_path):
    baseline = _ncaaf_signal(tmp_path / "a")
    windy = _ncaaf_signal(tmp_path / "b", fetch_football_weather=_severe_weather_fetch)

    winner_market = _market("KXNCAAFGAME-26SEP13TEXOU-TEX", "Texas Longhorns vs Oklahoma Sooners Winner?")
    spread_market = _market(
        "KXNCAAFSPREAD-26SEP13TEXOU-TEX3",
        "Texas Longhorns vs Oklahoma Sooners Spread", floor_strike=2.5)
    total_market = _market(
        "KXNCAAFTOTAL-26SEP13TEXOU-55",
        "Texas Longhorns vs Oklahoma Sooners Total Points", floor_strike=54.5)

    baseline_winner = baseline.generate(winner_market)
    windy_winner = windy.generate(winner_market)
    baseline_spread = baseline.generate(spread_market)
    windy_spread = windy.generate(spread_market)
    baseline_total = baseline.generate(total_market)
    windy_total = windy.generate(total_market)

    assert all(s is not None for s in (
        baseline_winner, windy_winner, baseline_spread, windy_spread, baseline_total, windy_total))

    assert windy_winner.probability_yes == baseline_winner.probability_yes
    assert windy_spread.probability_yes == baseline_spread.probability_yes
    assert windy_total.probability_yes < baseline_total.probability_yes
    assert windy_total.features["weather_total_adjustment"] == STACK_CAP
    assert "weather_total_adjustment" not in windy_winner.features
    assert "weather_total_adjustment" not in windy_spread.features


def test_hook_dome_home_team_total_is_byte_identical_to_no_weather(tmp_path):
    """ARI (dome) hosting -> total signal identical whether or not the
    fetch would have returned severe weather; the dome short-circuits
    before any fetch, so features never carry a weather key at all."""
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    game = Game("g3", "nfl", "ARI", "SF", "pre", None, "2026-09-13T18:00Z",
                home_name="Arizona Cardinals", away_name="San Francisco 49ers")
    client._cache[("nfl", "20260913")] = [game]
    models = {key: TeamScoreModel(key) for key in LEAGUE_SCORE_CONFIGS}

    baseline = TeamSportsIntelligenceSignal(
        espn=client, models=models, model_dir=tmp_path / "a", seasons=_AlwaysActive(),
        fetch_football_weather=lambda *a, **k: {},
    )
    dome_but_severe = TeamSportsIntelligenceSignal(
        espn=client, models={k: TeamScoreModel(k) for k in LEAGUE_SCORE_CONFIGS},
        model_dir=tmp_path / "b", seasons=_AlwaysActive(),
        fetch_football_weather=_severe_weather_fetch,
    )

    total_market = _market(
        "KXNFLTOTAL-26SEP13ARISF-44",
        "Arizona Cardinals vs San Francisco 49ers Total Points", floor_strike=44.5)

    baseline_total = baseline.generate(total_market)
    dome_total = dome_but_severe.generate(total_market)

    assert baseline_total is not None and dome_total is not None
    assert baseline_total.probability_yes == dome_total.probability_yes
    assert "weather_total_adjustment" not in dome_total.features


def test_hook_feature_logging_present_on_total_market_only(tmp_path):
    windy = _nfl_signal(tmp_path, fetch_football_weather=_severe_weather_fetch)
    total_market = _market(
        "KXNFLTOTAL-26SEP13KCBUF-44",
        "Kansas City Chiefs vs Buffalo Bills Total Points", floor_strike=44.5)
    signal = windy.generate(total_market)
    assert signal is not None
    for key in ("weather_wind_mph", "weather_temp_f", "weather_code", "weather_total_adjustment"):
        assert key in signal.features
    assert signal.features["weather_wind_mph"] == 25.0
    assert signal.features["weather_temp_f"] == 10.0
    assert signal.features["weather_code"] == 65.0
    assert signal.features["weather_total_adjustment"] == STACK_CAP
