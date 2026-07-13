"""Tests for the static MLB park run-factor table (WS-11)."""
from __future__ import annotations

from autonomy.sports.mlb_parks import PARK_FACTORS, park_factor_for


def test_park_factors_cover_all_thirty_teams_plus_athletics_alias():
    # 30 franchises; ATH + OAK both present as the same park (team code
    # transitioned mid-history), so 31 keys total.
    assert len(PARK_FACTORS) == 31
    assert PARK_FACTORS["ATH"] == PARK_FACTORS["OAK"]


def test_brief_anchor_values_are_encoded_verbatim():
    # The WS-11 brief calls out these three values explicitly.
    assert PARK_FACTORS["COL"] == 1.28
    assert abs(PARK_FACTORS["SD"] - 0.90) < 1e-9
    assert abs(PARK_FACTORS["SF"] - 0.90) < 1e-9


def test_all_factors_are_bounded_and_plausible():
    # No park should be modeled as swinging run environment more than ~30%
    # in either direction -- guards against a fat-fingered constant.
    for team, factor in PARK_FACTORS.items():
        assert 0.80 <= factor <= 1.30, f"{team} factor {factor} out of bounds"


def test_park_factor_for_known_team_uses_table():
    assert park_factor_for("COL") == 1.28
    assert abs(park_factor_for("SD") - 0.90) < 1e-9


def test_park_factor_for_aliases_canonicalizes_team_code():
    # AZ/CWS are MLB_TEAM_ALIASES for ARI/CHW elsewhere in the codebase;
    # the lookup must canonicalize before hitting the table.
    assert park_factor_for("AZ") == PARK_FACTORS["ARI"]
    assert park_factor_for("CWS") == PARK_FACTORS["CHW"]


def test_park_factor_for_unknown_or_missing_team_is_a_noop():
    assert park_factor_for("ZZZ") == 1.0
    assert park_factor_for(None) == 1.0
    assert park_factor_for("") == 1.0


def test_col_vs_sd_totals_delta_matches_the_table():
    # A COL home game should scale a raw total up by exactly the ratio of
    # the two static factors relative to an SD home game, for the same
    # underlying raw expected total.
    raw_total = 8.0
    col_total = raw_total * park_factor_for("COL")
    sd_total = raw_total * park_factor_for("SD")
    assert abs((col_total / sd_total) - (1.28 / 0.90)) < 1e-9
    assert col_total > raw_total > sd_total
