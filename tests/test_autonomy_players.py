"""Tests for WS-6: player availability / rookie / mismatch layer."""
from __future__ import annotations

from autonomy.signals.sports_intelligence import TeamSportsIntelligenceSignal
from autonomy.sports.espn import EspnClient, Game
from autonomy.sports.players import (
    LEAGUE_POINT_SCALE,
    POSITION_IMPACT,
    AvailabilityEffect,
    LeagueInjuryBook,
    RookieBook,
    TeamAvailability,
    apply_margin_shift_to_scores,
    availability_effect,
    bounded_mismatch_score,
    classify_status,
    hard_points_for_player,
    mismatch_margin_shift,
    parse_team_availability,
    parse_team_ids,
    probe_rookie_qb_start,
    shift_probability_by_margin,
)
from autonomy.ontology import MarketView, Vertical
from datetime import datetime, timedelta, timezone


# ------------------------------------------------------------- classification


def test_classify_status_hard_soft_and_untracked():
    assert classify_status("Out") == "hard"
    assert classify_status("doubtful") == "hard"
    assert classify_status("Questionable") == "soft"
    assert classify_status("Day-To-Day") == "soft"
    assert classify_status("Probable") == "soft"
    assert classify_status("Active") is None
    assert classify_status("Injured Reserve") is None
    assert classify_status(None) is None


# ------------------------------------------------------------- position table


def test_position_impact_table_matches_brief_exactly():
    assert POSITION_IMPACT["nfl"]["QB"] == -4.5
    assert POSITION_IMPACT["nfl"]["RB_WR"] == -0.7
    assert POSITION_IMPACT["nfl"]["OL"] == -0.5
    assert POSITION_IMPACT["nba"]["DEFAULT"] == -1.8
    assert POSITION_IMPACT["nhl"]["SKATER"] == -0.3
    # College = half of the pro table.
    assert POSITION_IMPACT["ncaaf"]["QB"] == POSITION_IMPACT["nfl"]["QB"] / 2
    assert POSITION_IMPACT["ncaaf"]["RB_WR"] == POSITION_IMPACT["nfl"]["RB_WR"] / 2
    assert POSITION_IMPACT["ncaaf"]["OL"] == POSITION_IMPACT["nfl"]["OL"] / 2
    assert POSITION_IMPACT["ncaamb"]["DEFAULT"] == POSITION_IMPACT["nba"]["DEFAULT"] / 2


def test_hard_points_for_player_position_mapping():
    assert hard_points_for_player("nfl", "QB") == -4.5
    assert hard_points_for_player("nfl", "WR") == -0.7
    assert hard_points_for_player("nfl", "RB") == -0.7
    assert hard_points_for_player("nfl", "OT") == -0.5
    assert hard_points_for_player("nfl", "CB") == 0.0    # unmapped defensive position
    assert hard_points_for_player("nba", "C") == -1.8    # NBA: flat default regardless of position
    assert hard_points_for_player("nhl", "D") == -0.3
    assert hard_points_for_player("nhl", "G") == 0.0     # goalie: WS-3's own layer
    assert hard_points_for_player("unknown_league", "QB") == 0.0


# ------------------------------------------------------------- injuries parse


def _nfl_payload():
    return {"injuries": [
        {"displayName": "Kansas City Chiefs", "injuries": [
            {"status": "Out", "athlete": {"position": {"abbreviation": "QB"}}},
            {"status": "Questionable", "athlete": {"position": {"abbreviation": "WR"}}},
            {"status": "Active", "athlete": {"position": {"abbreviation": "QB"}}},  # ignored
        ]},
        {"displayName": "Buffalo Bills", "injuries": [
            {"status": "Questionable", "athlete": {"position": {"abbreviation": "CB"}}},
        ]},
    ]}


def test_parse_team_availability_hard_and_soft():
    parsed = parse_team_availability("nfl", _nfl_payload())
    chiefs = parsed["kansascitychiefs"]
    assert chiefs.hard_points == -4.5
    assert chiefs.soft_count == 1
    assert chiefs.hard_labels == ("QB:Out",)
    bills = parsed["buffalobills"]
    assert bills.hard_points == 0.0
    assert bills.soft_count == 1


def test_parse_team_availability_none_and_empty_are_safe():
    assert parse_team_availability("nfl", None) == {}
    assert parse_team_availability("nfl", {}) == {}
    assert parse_team_availability("ncaamb", {"injuries": []}) == {}  # offseason shape, probed live


def test_parse_team_availability_hard_points_are_capped():
    payload = {"injuries": [{"displayName": "Stacked Team", "injuries": [
        {"status": "Out", "athlete": {"position": {"abbreviation": "QB"}}},
        {"status": "Out", "athlete": {"position": {"abbreviation": "QB"}}},
        {"status": "Out", "athlete": {"position": {"abbreviation": "QB"}}},
    ]}]}
    parsed = parse_team_availability("nfl", payload)
    assert parsed["stackedteam"].hard_points == -9.0  # capped at 2x QB weight, not -13.5


# ------------------------------------------------------------- injury book


def test_league_injury_book_is_zero_until_refreshed_no_network():
    calls = []

    def fetch():
        calls.append(1)
        return _nfl_payload()

    book = LeagueInjuryBook("nfl", fetch_fn=fetch)
    assert book.for_team("Kansas City Chiefs") == TeamAvailability()
    assert calls == []
    book.refresh()
    assert calls == [1]
    assert book.for_team("Kansas City Chiefs").hard_points == -4.5


def test_league_injury_book_matches_by_normalized_name_and_unknown_is_zero():
    book = LeagueInjuryBook("nfl", fetch_fn=_nfl_payload)
    book.refresh()
    assert book.for_team("kansas city chiefs").hard_points == -4.5
    assert book.for_team("Unknown Team") == TeamAvailability()
    assert book.for_team(None) == TeamAvailability()


def test_league_injury_book_fail_closed_on_fetch_error():
    def boom():
        raise RuntimeError("espn down")

    book = LeagueInjuryBook("nfl", fetch_fn=boom)
    book.refresh()
    assert book.for_team("Kansas City Chiefs") == TeamAvailability()


# ------------------------------------------------------------- rookie probe


def test_probe_rookie_qb_start_true_and_false():
    rookie_roster = {"athletes": [
        {"position": "offense", "items": [
            {"position": {"abbreviation": "QB"}, "experience": {"years": 0}},
            {"position": {"abbreviation": "WR"}, "experience": {"years": 5}},
        ]},
    ]}
    veteran_roster = {"athletes": [
        {"position": "offense", "items": [
            {"position": {"abbreviation": "QB"}, "experience": {"years": 8}},
        ]},
    ]}
    assert probe_rookie_qb_start(rookie_roster) is True
    assert probe_rookie_qb_start(veteran_roster) is False


def test_probe_rookie_qb_start_fails_closed_on_missing_data():
    assert probe_rookie_qb_start(None) is None
    assert probe_rookie_qb_start({}) is None
    assert probe_rookie_qb_start({"athletes": [{"position": "offense", "items": []}]}) is None
    no_experience = {"athletes": [{"position": "offense", "items": [
        {"position": {"abbreviation": "QB"}},
    ]}]}
    assert probe_rookie_qb_start(no_experience) is None


def test_parse_team_ids():
    payload = {"sports": [{"leagues": [{"teams": [
        {"team": {"id": "12", "abbreviation": "KC", "displayName": "Kansas City Chiefs"}},
        {"team": {"id": "2", "abbreviation": "BUF", "displayName": "Buffalo Bills"}},
    ]}]}]}
    assert parse_team_ids(payload) == {"KC": "12", "BUF": "2"}
    assert parse_team_ids(None) == {}
    assert parse_team_ids({}) == {}


def test_rookie_book_refreshes_within_budget_and_fails_closed():
    rosters = {
        "12": {"athletes": [{"position": "offense", "items": [
            {"position": {"abbreviation": "QB"}, "experience": {"years": 0}},
        ]}]},
        "2": {"athletes": [{"position": "offense", "items": [
            {"position": {"abbreviation": "QB"}, "experience": {"years": 9}},
        ]}]},
    }
    calls = []

    def fetch_teams(_league):
        return {"sports": [{"leagues": [{"teams": [
            {"team": {"id": "12", "abbreviation": "KC"}},
            {"team": {"id": "2", "abbreviation": "BUF"}},
        ]}]}]}

    def fetch_roster(_league, team_id):
        calls.append(team_id)
        return rosters[team_id]

    book = RookieBook("nfl", fetch_teams=fetch_teams, fetch_roster=fetch_roster, fetch_budget=8)
    book.refresh(["KC", "BUF"])
    assert book.rookie_start("KC") is True
    assert book.rookie_start("BUF") is False
    assert book.rookie_start("UNKNOWN") is None
    assert sorted(calls) == ["12", "2"]


def test_rookie_book_respects_fetch_budget():
    def fetch_teams(_league):
        return {"sports": [{"leagues": [{"teams": [
            {"team": {"id": str(i), "abbreviation": f"T{i}"}} for i in range(5)
        ]}]}]}

    def fetch_roster(_league, team_id):
        return {"athletes": [{"position": "offense", "items": [
            {"position": {"abbreviation": "QB"}, "experience": {"years": 0}},
        ]}]}

    book = RookieBook("nfl", fetch_teams=fetch_teams, fetch_roster=fetch_roster, fetch_budget=2)
    book.refresh([f"T{i}" for i in range(5)])
    assert len(book._flags) == 2  # budget respected


def test_rookie_book_fail_closed_on_fetch_error():
    def fetch_teams(_league):
        raise RuntimeError("down")

    def fetch_roster(_league, team_id):
        raise AssertionError("should never be called")

    book = RookieBook("nfl", fetch_teams=fetch_teams, fetch_roster=fetch_roster)
    book.refresh(["KC"])
    assert book.rookie_start("KC") is None


# ------------------------------------------------------------- mismatch score


def test_bounded_mismatch_score_is_bounded():
    assert bounded_mismatch_score(1000.0, -1000.0, 10.0) <= 1.0
    assert bounded_mismatch_score(-1000.0, 1000.0, 10.0) >= -1.0
    assert bounded_mismatch_score(0.0, 0.0, 10.0) == 0.0
    assert bounded_mismatch_score(5.0, 1.0, 10.0) < 1.0  # not yet saturated -> strictly interior


def test_bounded_mismatch_score_is_symmetric_under_home_away_swap():
    score = bounded_mismatch_score(7.5, 2.0, 8.0)
    swapped = bounded_mismatch_score(2.0, 7.5, 8.0)
    assert swapped == -score


def test_bounded_mismatch_score_zero_scale_is_zero():
    assert bounded_mismatch_score(5.0, 1.0, 0.0) == 0.0


def test_mismatch_margin_shift_zero_below_threshold():
    assert mismatch_margin_shift(0.5, 10.0) == 0.0
    assert mismatch_margin_shift(-0.5, 10.0) == 0.0
    assert mismatch_margin_shift(0.2, 10.0) == 0.0


def test_mismatch_margin_shift_bounded_and_signed_above_threshold():
    shift = mismatch_margin_shift(0.8, 10.0)
    assert shift == 0.8 * 0.3 * 10.0
    assert mismatch_margin_shift(-0.8, 10.0) == -shift
    # Even a score of 1.0 (max) never exceeds 0.3 * point_scale.
    assert abs(mismatch_margin_shift(1.0, 10.0)) == 0.3 * 10.0


# ------------------------------------------------------------- probability shift


def test_shift_probability_by_margin_is_exact_noop_at_zero_delta():
    assert shift_probability_by_margin(0.6321, 0.0, 12.0, True) == 0.6321


def test_shift_probability_by_margin_direction_and_bounds():
    base = 0.5
    up = shift_probability_by_margin(base, 3.0, 12.0, True)
    down = shift_probability_by_margin(base, 3.0, 12.0, False)
    assert up > base
    assert down < base
    assert 0.005 <= up <= 0.995
    assert 0.005 <= down <= 0.995


def test_apply_margin_shift_to_scores_preserves_total_and_shifts_margin_exactly():
    home, away = 24.0, 20.0
    new_home, new_away = apply_margin_shift_to_scores(home, away, -4.5)
    assert (new_home - new_away) - (home - away) == -4.5
    assert (new_home + new_away) == (home + away)  # total preserved


# ------------------------------------------------------------- availability effect


def test_availability_effect_hard_only_shifts_margin_qb_out_key_test():
    home = TeamAvailability(hard_points=-4.5, soft_count=0, hard_labels=("QB:Out",))
    away = TeamAvailability()
    effect = availability_effect("nfl", home, away)
    assert effect.hard_margin_delta == -4.5
    assert effect.soft_uncertainty_add == 0.0
    assert effect.rookie_uncertainty_add == 0.0
    assert effect.features["hard_margin_delta"] == -4.5


def test_availability_effect_away_hard_flips_sign():
    home = TeamAvailability()
    away = TeamAvailability(hard_points=-4.5)
    effect = availability_effect("nfl", home, away)
    assert effect.hard_margin_delta == 4.5   # hurting AWAY raises home's relative margin


def test_availability_effect_soft_widens_only_never_mean():
    home = TeamAvailability(soft_count=3)   # 3 * 0.02 = 0.06
    away = TeamAvailability(soft_count=10)  # capped at 0.08
    effect = availability_effect("nfl", home, away)
    assert effect.hard_margin_delta == 0.0
    assert round(effect.soft_uncertainty_add, 4) == round(0.06 + 0.08, 4)


def test_availability_effect_rookie_widens_only_never_mean():
    effect = availability_effect(
        "nfl", TeamAvailability(), TeamAvailability(),
        home_rookie_start=True, away_rookie_start=False,
    )
    assert effect.hard_margin_delta == 0.0
    assert effect.soft_uncertainty_add == 0.0
    assert effect.rookie_uncertainty_add == 0.04
    both = availability_effect(
        "nfl", TeamAvailability(), TeamAvailability(),
        home_rookie_start=True, away_rookie_start=True,
    )
    assert both.rookie_uncertainty_add == 0.08


def test_availability_effect_feed_absent_is_all_zero_effects():
    """The brief's own key test: injuries feed absent -> all zero effects,
    byte-identical to feature disabled."""
    book = LeagueInjuryBook("nfl", fetch_fn=lambda: (_ for _ in ()).throw(RuntimeError("down")))
    book.refresh()
    home = book.for_team("Kansas City Chiefs")
    away = book.for_team("Buffalo Bills")
    effect = availability_effect("nfl", home, away, home_rookie_start=None, away_rookie_start=None)
    assert effect.hard_margin_delta == 0.0
    assert effect.soft_uncertainty_add == 0.0
    assert effect.rookie_uncertainty_add == 0.0


def test_league_point_scale_table_has_every_team_sport():
    for league in ("nba", "ncaamb", "nfl", "ncaaf", "nhl"):
        assert LEAGUE_POINT_SCALE[league] > 0


# =========================================================================
# End-to-end wiring tests through TeamSportsIntelligenceSignal.generate()
# =========================================================================

NOW = datetime(2026, 9, 10, tzinfo=timezone.utc)


def _nfl_market(ticker: str, title: str, **raw) -> MarketView:
    payload = {"event_ticker": ticker.rsplit("-", 1)[0], **raw}
    return MarketView(
        ticker=ticker, title=title, vertical=Vertical.SPORTS, status="open",
        close_time=(NOW + timedelta(days=1)).isoformat(),
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56, volume=500, liquidity=1_000,
        raw=payload,
    )


def _nfl_game() -> Game:
    return Game(
        game_id="nfl1", league="nfl", home="KC", away="BUF", status="pre", home_won=None,
        date="2026-09-10T20:00:00Z", home_name="Kansas City Chiefs", away_name="Buffalo Bills",
    )


def _nfl_signal(tmp_path, fetch_injuries=None, rookie_book=None) -> TeamSportsIntelligenceSignal:
    client = EspnClient(fetch_scoreboard=lambda _league, _dates: {"events": []})
    client._cache[("nfl", "20260910")] = [_nfl_game()]
    injury_books = {"nfl": LeagueInjuryBook("nfl", fetch_fn=fetch_injuries or (lambda: {"injuries": []}))}
    injury_books["nfl"].refresh()
    return TeamSportsIntelligenceSignal(
        espn=client, model_dir=tmp_path, injury_books=injury_books,
        rookie_book=rookie_book or RookieBook("nfl", fetch_teams=lambda _l: {}, fetch_roster=lambda _l, _t: {}),
    )


def _nfl_winner_market() -> MarketView:
    return _nfl_market("KXNFLGAME-26SEP10KCBUF-KC", "Kansas City vs Buffalo Winner?")


def test_engine_qb_out_shifts_nfl_expected_margin_by_exactly_4_5(tmp_path):
    """THE brief's key test: QB-Out shifts the NFL expected margin by
    exactly -4.5 for the affected (home) team, with the feature logged."""
    healthy = _nfl_signal(tmp_path / "a", fetch_injuries=lambda: {"injuries": []})
    hurt_payload = {"injuries": [
        {"displayName": "Kansas City Chiefs", "injuries": [
            {"status": "Out", "athlete": {"position": {"abbreviation": "QB"}}},
        ]},
    ]}
    hurt = _nfl_signal(tmp_path / "b", fetch_injuries=lambda: hurt_payload)

    market = _nfl_winner_market()
    healthy_signal = healthy.generate(market)
    hurt_signal = hurt.generate(market)

    assert healthy_signal is not None and hurt_signal is not None
    assert healthy_signal.features["hard_margin_delta"] == 0.0
    assert hurt_signal.features["hard_margin_delta"] == -4.5
    # KC is home and the subject -> hurting KC's margin must LOWER KC's win
    # probability relative to the healthy baseline.
    assert hurt_signal.probability_yes < healthy_signal.probability_yes
    assert hurt_signal.features["challenger_only"] is True


def test_engine_questionable_widens_uncertainty_only_mean_byte_identical(tmp_path):
    healthy = _nfl_signal(tmp_path / "a", fetch_injuries=lambda: {"injuries": []})
    soft_payload = {"injuries": [
        {"displayName": "Kansas City Chiefs", "injuries": [
            {"status": "Questionable", "athlete": {"position": {"abbreviation": "WR"}}},
        ]},
    ]}
    soft = _nfl_signal(tmp_path / "b", fetch_injuries=lambda: soft_payload)

    market = _nfl_winner_market()
    healthy_signal = healthy.generate(market)
    soft_signal = soft.generate(market)

    assert soft_signal.features["hard_margin_delta"] == 0.0
    assert soft_signal.probability_yes == healthy_signal.probability_yes  # mean byte-identical
    assert soft_signal.uncertainty > healthy_signal.uncertainty           # uncertainty widened
    assert round(soft_signal.uncertainty - healthy_signal.uncertainty, 4) == 0.02


def test_engine_rookie_flag_widens_uncertainty_only_mean_byte_identical(tmp_path):
    no_rookie_book = RookieBook("nfl", fetch_teams=lambda _l: {}, fetch_roster=lambda _l, _t: {})
    baseline = _nfl_signal(tmp_path / "a", rookie_book=no_rookie_book)

    rookie_book = RookieBook("nfl", fetch_teams=lambda _l: {}, fetch_roster=lambda _l, _t: {})
    rookie_book._flags = {"KC": True}  # pre-seed as if refresh() had probed it
    rookie = _nfl_signal(tmp_path / "b", rookie_book=rookie_book)

    market = _nfl_winner_market()
    baseline_signal = baseline.generate(market)
    rookie_signal = rookie.generate(market)

    assert rookie_signal.features["hard_margin_delta"] == 0.0
    assert rookie_signal.probability_yes == baseline_signal.probability_yes  # mean byte-identical
    assert rookie_signal.uncertainty > baseline_signal.uncertainty
    assert round(rookie_signal.uncertainty - baseline_signal.uncertainty, 4) == 0.04
    assert rookie_signal.features["rookie_start_home"] is True


def test_engine_injuries_feed_absent_is_byte_identical_to_disabled(tmp_path):
    """The brief's own key test: injuries feed absent -> all zero effects,
    byte-identical to feature disabled."""
    disabled = _nfl_signal(tmp_path / "a", fetch_injuries=lambda: {"injuries": []})

    def boom():
        raise RuntimeError("espn down")

    absent = _nfl_signal(tmp_path / "b", fetch_injuries=boom)

    market = _nfl_winner_market()
    disabled_signal = disabled.generate(market)
    absent_signal = absent.generate(market)

    assert disabled_signal.probability_yes == absent_signal.probability_yes
    assert disabled_signal.uncertainty == absent_signal.uncertainty
    assert absent_signal.features["hard_margin_delta"] == 0.0
    assert absent_signal.features["soft_uncertainty_add"] == 0.0
