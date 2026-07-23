"""Wave-79: MLB player-prop model (distribution math + challenger signal)."""
from __future__ import annotations

import datetime

from autonomy.ontology import MarketView, Vertical
from autonomy.sports.mlb_props import (
    _over_threshold,
    batter_prop_over_probability,
    pitcher_prop_over_probability,
)
from autonomy.sports.statsapi import BatterRates, LineupSlot, MlbGameContext, PitcherRates
from autonomy.signals.mlb_props import (
    MlbPlayerPropSignal,
    _name_matches,
    _player_token_identity,
)


# --------------------------------------------------------------------------
# Distribution math
# --------------------------------------------------------------------------

def test_over_threshold_half_and_whole_lines():
    assert _over_threshold(0.5) == 1
    assert _over_threshold(1.5) == 2
    assert _over_threshold(2.0) == 3  # "over 2" needs 3


def test_home_run_probability_rises_with_power():
    weak = BatterRates(player_id=1, bats="R", obp=0.300, slg=0.360, iso=0.100, k_pct=0.24)
    strong = BatterRates(player_id=2, bats="R", obp=0.380, slg=0.580, iso=0.270, k_pct=0.22)
    p_weak = batter_prop_over_probability("home_runs", 0.5, weak, None, projected_pa=4.3)
    p_strong = batter_prop_over_probability("home_runs", 0.5, strong, None, projected_pa=4.3)
    assert 0.0 < p_weak < p_strong < 1.0


def test_strikeout_probability_rises_with_pitcher_k_rate():
    soft = PitcherRates(player_id=1, throws="R", k_pct=0.16, bb_pct=0.09, hr9=1.4)
    ace = PitcherRates(player_id=2, throws="R", k_pct=0.31, bb_pct=0.06, hr9=0.9)
    p_soft = pitcher_prop_over_probability("strikeouts", 5.5, soft, None, projected_bf=23)
    p_ace = pitcher_prop_over_probability("strikeouts", 5.5, ace, None, projected_bf=23)
    assert 0.0 < p_soft < p_ace < 1.0


def test_more_plate_appearances_raises_batter_over():
    b = BatterRates(player_id=1, bats="R", obp=0.350, slg=0.470, iso=0.190, k_pct=0.22)
    few = batter_prop_over_probability("hits", 1.5, b, None, projected_pa=3.9)
    many = batter_prop_over_probability("hits", 1.5, b, None, projected_pa=4.65)
    assert many > few


def test_unsupported_stats_abstain():
    b = BatterRates(player_id=1, bats="R", obp=0.35, slg=0.47, iso=0.19, k_pct=0.22)
    p = PitcherRates(player_id=2, throws="R", k_pct=0.25, bb_pct=0.07, hr9=1.1)
    assert batter_prop_over_probability("rbis", 0.5, b, None) is None
    assert batter_prop_over_probability("stolen_bases", 0.5, b, None) is None
    assert pitcher_prop_over_probability("outs", 15.5, p) is None


# --------------------------------------------------------------------------
# Token / name parsing
# --------------------------------------------------------------------------

def test_player_token_identity():
    assert _player_token_identity(
        "KXMLBHR-26JUL242010COLMIL-MILCYELICH44-2") == ("MIL", "C", "YELICH")
    assert _player_token_identity(
        "KXMLBKS-26JUL242010COLMIL-COLTSUGANO54-4") == ("COL", "T", "SUGANO")


def test_name_matches_including_multiword_surname():
    assert _name_matches("Christian Yelich", "C", "YELICH")
    assert _name_matches("Elly De La Cruz", "E", "DELACRUZ")
    assert not _name_matches("Christian Yelich", "M", "YELICH")
    assert not _name_matches("Christian Yelich", "C", "TROUT")


# --------------------------------------------------------------------------
# Signal: fail-closed + pitcher pricing against a stubbed StatsAPI
# --------------------------------------------------------------------------

def _mv(ticker: str, raw: dict) -> MarketView:
    return MarketView(
        ticker=ticker, title="prop", vertical=Vertical.SPORTS, status="active",
        close_time=None, yes_bid=40, yes_ask=45, no_bid=55, no_ask=60, volume=10,
        liquidity=10, tick_size=1, raw=raw,
        fetched_at=datetime.datetime.now(datetime.timezone.utc),
    )


class _StubStatsApi:
    """Returns a fixed hydrated context (probable pitchers, no lineup)."""

    def __init__(self, ctx):
        self._ctx = ctx

    def clear_schedule_cache(self):
        pass

    def projected_context_for_matchup(self, date_iso, *, home, away, captured_at):
        # Honor the real home/away resolution (MIL home, COL away here).
        return self._ctx if (home, away) == ("MIL", "COL") else None

    def confirm_lineups(self, ctx, *, captured_at):
        return ctx

    def hydrate_batter_rates(self, ctx):
        return ctx


def _ctx_pitchers_only():
    return MlbGameContext(
        game_pk=1, snapshot="projected", captured_at="2026-07-24T00:00:00Z",
        home="MIL", away="COL",
        home_pitcher=PitcherRates(player_id=10, name="Shane Drohan", throws="L",
                                  k_pct=0.26, bb_pct=0.08, hr9=1.1),
        away_pitcher=PitcherRates(player_id=11, name="Tomoyuki Sugano", throws="R",
                                  k_pct=0.16, bb_pct=0.05, hr9=1.3),
        home_lineup=(), away_lineup=(), batter_rates={}, park_hr_factor=1.0,
    )


def test_pitcher_strikeout_prices_from_probable_starter():
    sig = MlbPlayerPropSignal(statsapi=_StubStatsApi(_ctx_pitchers_only()))
    s = sig.generate(_mv("KXMLBKS-26JUL242010COLMIL-MILSDROHAN54-4", {"floor_strike": 4.5}))
    assert s is not None
    assert s.source == "mlb_player_prop"
    assert s.features["challenger_only"] is True
    assert s.features["stat"] == "strikeouts"
    assert 0.03 <= s.probability_yes <= 0.97


def test_batter_prop_abstains_without_confirmed_lineup():
    sig = MlbPlayerPropSignal(statsapi=_StubStatsApi(_ctx_pitchers_only()))
    # Lineup is empty (not posted) -> the batter cannot be matched -> abstain.
    s = sig.generate(_mv("KXMLBHR-26JUL242010COLMIL-MILCYELICH44-0", {"floor_strike": 0.5}))
    assert s is None


def test_batter_prop_prices_with_confirmed_lineup():
    ctx = _ctx_pitchers_only()
    yelich = LineupSlot(batting_order=3, player_id=99, name="Christian Yelich", bats="L")
    ctx = MlbGameContext(
        game_pk=1, snapshot="confirmed", captured_at="2026-07-24T00:00:00Z",
        home="MIL", away="COL", home_pitcher=ctx.home_pitcher,
        away_pitcher=ctx.away_pitcher, home_lineup=(yelich,), away_lineup=(),
        batter_rates={99: BatterRates(player_id=99, bats="L", obp=0.360, slg=0.520,
                                      iso=0.230, k_pct=0.22)},
        park_hr_factor=1.0,
    )
    sig = MlbPlayerPropSignal(statsapi=_StubStatsApi(ctx))
    s = sig.generate(_mv("KXMLBHR-26JUL242010COLMIL-MILCYELICH44-0", {"floor_strike": 0.5}))
    assert s is not None
    assert s.features["stat"] == "home_runs"
    assert 0.03 <= s.probability_yes <= 0.97


def test_unsupported_prop_not_applicable():
    sig = MlbPlayerPropSignal(statsapi=_StubStatsApi(_ctx_pitchers_only()))
    # Outs / RBIs / SB are deliberately unmodeled -> not applicable, never priced.
    assert sig.applicable(_mv("KXMLBOUTS-26JUL242010COLMIL-MILSDROHAN54-15",
                              {"floor_strike": 15.5})) is False
    assert sig.applicable(_mv("KXMLBKS-26JUL242010COLMIL-MILSDROHAN54-4",
                              {"floor_strike": 4.5})) is True
