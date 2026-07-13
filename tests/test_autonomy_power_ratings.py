"""Tests for autonomy.sports.power_ratings (Phenon Harness WS-A1).

Zero network: consensus math uses fake in-memory sources with
hand-computed expected values; parse_powerindex is exercised both against
hand-built malformed payloads and against trimmed REAL committed fixtures
(tests/fixtures/espn_fpi_nfl_powerindex_probe.json,
tests/fixtures/espn_bpi_nba_powerindex_probe.json) -- no live fetch ever
happens in a test.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from autonomy.sports.power_ratings import (
    ConsensusMargin,
    EloSource,
    EspnBpiSource,
    EspnFpiSource,
    POINTS_PER_RATING_UNIT,
    consensus_margin,
    default_fetch_powerindex,
    parse_powerindex,
)

FIXTURES = Path(__file__).parent / "fixtures"


class FakeSource:
    """A RatingSource with a fixed home/away rating (or None) per team."""

    def __init__(self, name: str, ratings: dict[str, float | None]) -> None:
        self.name = name
        self._ratings = ratings

    def rating(self, league: str, team: str) -> float | None:
        return self._ratings.get(team)


@pytest.fixture()
def scaled_league(monkeypatch):
    """A dedicated fake league with a clean, easy-to-hand-compute scale."""
    monkeypatch.setitem(POINTS_PER_RATING_UNIT, "testleague", 2.0)
    return "testleague"


# ---------------------------------------------------------------------------
# consensus_margin: core math
# ---------------------------------------------------------------------------


def test_consensus_margin_median_and_dispersion_hand_computed(scaled_league):
    # implied = (home - away) * scale(2.0)
    # A: (110-100)*2 = 20   B: (105-100)*2 = 10   C: (100-90)*2 = 20
    source_a = FakeSource("A", {"HOME": 110, "AWAY": 100})
    source_b = FakeSource("B", {"HOME": 105, "AWAY": 100})
    source_c = FakeSource("C", {"HOME": 100, "AWAY": 90})

    result = consensus_margin("HOME", "AWAY", scaled_league, [source_a, source_b, source_c])

    assert result is not None
    assert result.per_source == {"A": 20.0, "B": 10.0, "C": 20.0}
    assert result.ensemble_margin == 20.0  # median([20, 10, 20])
    assert result.dispersion == 10.0  # max - min
    assert result.n_sources == 3


def test_consensus_margin_drops_source_missing_a_team(scaled_league):
    source_a = FakeSource("A", {"HOME": 110, "AWAY": 100})  # implied 20
    source_b = FakeSource("B", {"HOME": None, "AWAY": 100})  # HOME missing -> dropped
    source_c = FakeSource("C", {"HOME": 100, "AWAY": 90})  # implied 20

    result = consensus_margin("HOME", "AWAY", scaled_league, [source_a, source_b, source_c])

    assert result is not None
    assert result.n_sources == 2
    assert "B" not in result.per_source
    assert result.per_source == {"A": 20.0, "C": 20.0}
    assert result.ensemble_margin == 20.0
    assert result.dispersion == 0.0


def test_consensus_margin_all_sources_none_returns_none(scaled_league):
    source_a = FakeSource("A", {"HOME": None, "AWAY": 100})
    source_b = FakeSource("B", {"HOME": 100, "AWAY": None})

    assert consensus_margin("HOME", "AWAY", scaled_league, [source_a, source_b]) is None


def test_consensus_margin_empty_source_list_returns_none(scaled_league):
    assert consensus_margin("HOME", "AWAY", scaled_league, []) is None


def test_consensus_margin_unknown_league_returns_none():
    source_a = FakeSource("A", {"HOME": 110, "AWAY": 100})
    assert consensus_margin("HOME", "AWAY", "not_a_real_league", [source_a]) is None


def test_consensus_margin_single_source_dispersion_zero(scaled_league):
    source_a = FakeSource("A", {"HOME": 110, "AWAY": 100})

    result = consensus_margin("HOME", "AWAY", scaled_league, [source_a])

    assert result is not None
    assert result.n_sources == 1
    assert result.dispersion == 0.0
    assert result.ensemble_margin == 20.0


def test_consensus_margin_no_side_effects_on_sources(scaled_league):
    # Calling consensus_margin must not mutate the sources' own state.
    source_a = FakeSource("A", {"HOME": 110, "AWAY": 100})
    before = dict(source_a._ratings)
    consensus_margin("HOME", "AWAY", scaled_league, [source_a])
    assert source_a._ratings == before


# ---------------------------------------------------------------------------
# parse_powerindex: fail-closed on malformed input
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"teams": "not-a-list"},
        {"teams": None},
        {"teams": [None]},
        {"teams": ["not-a-dict"]},
        {"teams": [{"team": "not-a-dict", "categories": []}]},
        {"teams": [{"team": {}, "categories": []}]},  # missing abbreviation
        {"teams": [{"team": {"abbreviation": "KC"}, "categories": "not-a-list"}]},
        {"teams": [{"team": {"abbreviation": "KC"}, "categories": [{"name": "not_fpi"}]}]},
        {"teams": [{"team": {"abbreviation": "KC"}, "categories": [{"name": "fpi", "values": []}]}]},
        {"teams": [{"team": {"abbreviation": "KC"}, "categories": [{"name": "fpi", "values": ["nan-string"]}]}]},
        "not-even-a-dict",
        [],
    ],
)
def test_parse_powerindex_malformed_returns_empty_dict(payload):
    assert parse_powerindex(payload, "nfl") == {}


def test_parse_powerindex_skips_bad_entries_but_keeps_good_ones():
    payload = {
        "teams": [
            {"team": {"abbreviation": "KC"}, "categories": [{"name": "fpi", "values": [9.5]}]},
            {"team": {}, "categories": [{"name": "fpi", "values": [1.0]}]},  # no abbr -> skipped
            {"team": {"abbreviation": "SF"}, "categories": [{"name": "fpi", "values": [3.2]}]},
        ]
    }
    assert parse_powerindex(payload, "nfl") == {"KC": 9.5, "SF": 3.2}


# ---------------------------------------------------------------------------
# parse_powerindex: real committed fixtures
# ---------------------------------------------------------------------------


def test_parse_powerindex_real_fpi_fixture_nonempty():
    payload = json.loads((FIXTURES / "espn_fpi_nfl_powerindex_probe.json").read_text(encoding="utf-8"))

    ratings = parse_powerindex(payload, "nfl")

    assert ratings  # non-empty
    assert "LAR" in ratings
    for abbr, value in ratings.items():
        assert isinstance(abbr, str) and abbr
        assert isinstance(value, float)
        assert -50.0 < value < 50.0  # sane FPI range


def test_parse_powerindex_real_bpi_fixture_nonempty():
    payload = json.loads((FIXTURES / "espn_bpi_nba_powerindex_probe.json").read_text(encoding="utf-8"))

    ratings = parse_powerindex(payload, "nba")

    assert ratings  # non-empty
    assert "OKC" in ratings
    for abbr, value in ratings.items():
        assert isinstance(abbr, str) and abbr
        assert isinstance(value, float)
        assert -50.0 < value < 50.0  # sane BPI range


# ---------------------------------------------------------------------------
# EspnFpiSource / EspnBpiSource: caching + fail-closed fetch
# ---------------------------------------------------------------------------


def test_espn_fpi_source_caches_fetch_per_league_not_per_team():
    calls = []

    def fake_fetch(league: str) -> dict:
        calls.append(league)
        return {"teams": [{"team": {"abbreviation": "KC"}, "categories": [{"name": "fpi", "values": [9.5]}]}]}

    source = EspnFpiSource(fetch=fake_fetch)

    assert source.rating("nfl", "KC") == 9.5
    assert source.rating("nfl", "SF") is None  # not in the map, but no refetch
    assert source.rating("nfl", "KC") == 9.5

    assert calls == ["nfl"]  # fetched exactly once for this league


def test_espn_fpi_source_fetch_failure_is_fail_closed():
    def failing_fetch(league: str) -> dict:
        raise RuntimeError("feed down")

    source = EspnFpiSource(fetch=failing_fetch)

    assert source.rating("nfl", "KC") is None
    assert source.rating("nfl", "SF") is None  # every team None this cycle, never raises


def test_espn_bpi_source_basic_lookup():
    def fake_fetch(league: str) -> dict:
        return {"teams": [{"team": {"abbreviation": "OKC"}, "categories": [{"name": "bpi", "values": [11.2]}]}]}

    source = EspnBpiSource(fetch=fake_fetch)

    assert source.rating("nba", "OKC") == 11.2
    assert source.rating("nba", "BOS") is None


# ---------------------------------------------------------------------------
# EloSource: read-only wrapper, never updates
# ---------------------------------------------------------------------------


class SpyEloModel:
    """Stand-in EloModel: records rating() calls, raises if update() is ever called.

    Exposes a public `ratings` dict, mirroring the real `EloModel.ratings`
    field, since `EloSource` checks membership there directly.
    """

    def __init__(self, ratings: dict[str, float]) -> None:
        self.ratings = ratings
        self.rating_calls: list[str] = []

    def rating(self, team: str) -> float:
        self.rating_calls.append(team)
        return self.ratings.get(team, 1500.0)

    def update(self, *args, **kwargs) -> None:
        raise AssertionError("EloSource must never call EloModel.update() -- point-in-time read only")


def test_elo_source_reads_via_rating_and_never_updates():
    elo_model = SpyEloModel({"KC": 1620.0, "DEN": 1480.0})
    source = EloSource(elo_model)

    assert source.name == "elo"
    assert source.rating("nfl", "KC") == 1620.0
    assert source.rating("nfl", "DEN") == 1480.0
    assert elo_model.rating_calls == ["KC", "DEN"]
    # SpyEloModel.update() would raise if called; reaching here means it never was.


def test_elo_source_participates_in_consensus_without_updating(scaled_league):
    elo_model = SpyEloModel({"HOME": 1550.0, "AWAY": 1500.0})
    elo_source = EloSource(elo_model)

    result = consensus_margin("HOME", "AWAY", scaled_league, [elo_source])

    assert result is not None
    assert result.per_source["elo"] == (1550.0 - 1500.0) * 2.0
    assert elo_model.rating_calls == ["HOME", "AWAY"]


# ---------------------------------------------------------------------------
# EloSource: fail-closed on unknown teams (WS-A1 review fix)
# ---------------------------------------------------------------------------


def test_elo_source_returns_none_for_team_absent_from_elo_model():
    # KC is present; KC's opponent this cycle, "XYZ", has never been seen by
    # the Elo model. EloSource must not fabricate BASE_RATING (1500.0) for it.
    elo_model = SpyEloModel({"KC": 1620.0})
    source = EloSource(elo_model)

    assert source.rating("nfl", "XYZ") is None
    # A present team still resolves to its real rating.
    assert source.rating("nfl", "KC") == 1620.0
    # And a team legitimately rated exactly 1500.0 must NOT be treated as
    # missing -- membership in `.ratings`, not equality to BASE_RATING, is
    # the test.
    elo_model_at_base = SpyEloModel({"KC": 1620.0, "KNOWN_AT_1500": 1500.0})
    source_at_base = EloSource(elo_model_at_base)
    assert source_at_base.rating("nfl", "KNOWN_AT_1500") == 1500.0


def test_consensus_margin_elo_only_both_teams_absent_returns_none(scaled_league):
    # Regression for the fail-closed hole: previously EloModel.rating()
    # defaulted BOTH unknown teams to 1500.0, producing a fabricated
    # ConsensusMargin(0.0, ...) instead of dropping the source entirely.
    elo_model = SpyEloModel({})  # neither HOME nor AWAY has ever been rated
    elo_source = EloSource(elo_model)

    result = consensus_margin("HOME", "AWAY", scaled_league, [elo_source])

    assert result is None


def test_consensus_margin_elo_only_one_team_absent_returns_none(scaled_league):
    # HOME is known, AWAY has never been rated -> Elo must drop out rather
    # than reporting a fabricated (rating - 1500.0) implied margin. Elo is
    # the only source here, so the whole consensus is None.
    elo_model = SpyEloModel({"HOME": 1600.0})
    elo_source = EloSource(elo_model)

    result = consensus_margin("HOME", "AWAY", scaled_league, [elo_source])

    assert result is None


# ---------------------------------------------------------------------------
# default_fetch_powerindex: unmapped league fails closed, not KeyError
# ---------------------------------------------------------------------------


def test_default_fetch_powerindex_unmapped_league_returns_empty_dict():
    assert default_fetch_powerindex("not_a_real_league") == {}
