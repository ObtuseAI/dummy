"""NFL key-number margin kernel + spread parsing/pricing across leagues."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.sports_intelligence import (
    TeamSportsIntelligenceSignal,
    parse_sports_contract,
)
from autonomy.sports.espn import EspnClient, Game
from autonomy.sports.live_team_models import NFL_LIVE_MODEL_VERSION
from autonomy.sports.nfl_margin import (
    NflMarginModel,
    margin_distribution,
    spread_cover_probability,
    win_probability,
)
from autonomy.sports.team_scores import LEAGUE_SCORE_CONFIGS, TeamScoreModel

NOW = datetime(2026, 9, 13, 16, 0, tzinfo=timezone.utc)


def _market(ticker: str, title: str, **raw) -> MarketView:
    payload = {"event_ticker": ticker.rsplit("-", 1)[0], **raw}
    return MarketView(
        ticker=ticker, title=title, vertical=Vertical.SPORTS, status="open",
        close_time=(NOW + timedelta(hours=6)).isoformat(),
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56,
        volume=500, liquidity=1_000, raw=payload,
    )


# -- kernel math ---------------------------------------------------------------

def test_kernel_is_a_distribution_with_key_number_mass():
    dist = margin_distribution(0.0)
    assert sum(dist.values()) == pytest.approx(1.0, abs=1e-12)
    # Zero-tilt symmetric: mean 0, win prob one half.
    assert sum(m * p for m, p in dist.items()) == pytest.approx(0.0, abs=1e-9)
    assert win_probability(dist) == pytest.approx(0.5, abs=1e-9)
    # Key numbers carry more mass than their neighbors -- the entire reason
    # this kernel exists instead of a normal.
    assert dist[3] > dist[2] and dist[3] > dist[4]
    assert dist[7] > dist[6] and dist[7] > dist[8]
    assert dist[10] > dist[9] and dist[10] > dist[11]


def test_tilt_matches_target_mean_and_preserves_spikes():
    for mu in (-6.5, -2.5, 1.0, 3.0, 7.5):
        dist = margin_distribution(mu)
        assert sum(m * p for m, p in dist.items()) == pytest.approx(mu, abs=1e-6)
        # Spikes stay ON the key numbers (tilting reweights, never shifts).
        assert dist[3] > dist[2] and dist[3] > dist[4]
        assert dist[7] > dist[6] and dist[7] > dist[8]
    # Extreme expectations clamp instead of extrapolating nonsense.
    clamped = margin_distribution(60.0)
    assert sum(clamped.values()) == pytest.approx(1.0, abs=1e-12)


def test_winner_and_spread_ladder_are_coherent_and_monotone():
    dist = margin_distribution(3.0)
    # Winner == cover(0.5) plus half the tie mass: the same distribution
    # prices both cells of the lattice.
    assert win_probability(dist) == pytest.approx(
        spread_cover_probability(dist, 0.5) + 0.5 * dist[0], abs=1e-12)
    # The ladder is strictly monotone in the line.
    ladder = [spread_cover_probability(dist, line) for line in (0.5, 2.5, 3.5, 6.5, 7.5, 10.5)]
    assert all(a > b for a, b in zip(ladder, ladder[1:]))
    # Key-number gap: crossing 3 costs far more probability than crossing 4.
    drop_across_3 = spread_cover_probability(dist, 2.5) - spread_cover_probability(dist, 3.5)
    drop_across_4 = spread_cover_probability(dist, 3.5) - spread_cover_probability(dist, 4.5)
    assert drop_across_3 > 2.0 * drop_across_4


def test_model_sides_are_complementary():
    model = NflMarginModel(24.5, 21.0)  # home favored by 3.5
    assert model.expected_margin == pytest.approx(3.5)
    assert model.home_win_probability() > 0.5
    # Home covering +k.5 and away covering -(k+1)+0.5 partition the space:
    # P(m > 3.5) + P(m < -(-3.5)) ... complementary pair at the same line.
    home_cover = model.home_cover_probability(3.5)
    away_cover = model.away_cover_probability(-3.5)  # away +3.5 underdog line
    assert home_cover + away_cover == pytest.approx(1.0, abs=1e-9)
    assert model.total_over_probability(40.5) > 0.5  # expected total 45.5


# -- parsing -------------------------------------------------------------------

def test_spread_series_parse_for_all_five_leagues():
    cases = {
        "KXNFLSPREAD-26SEP132025KCBUF-KC3": ("nfl", "KC"),
        "KXNBASPREAD-26OCT20LALBOS-BOS7": ("nba", "BOS"),
        "KXNHLSPREAD-26OCT09NYRBOS-NYR1": ("nhl", "NYR"),
        "KXNCAAFSPREAD-26SEP05TEXOU-TEX10": ("ncaaf", "TEX"),
        "KXNCAAMBSPREAD-26NOV20DUKEUNC-DUKE4": ("ncaamb", "DUKE"),
    }
    for ticker, (sport, subject) in cases.items():
        parsed = parse_sports_contract(_market(
            ticker, "Alpha Team vs Beta Team Spread", floor_strike=2.5))
        assert parsed is not None, ticker
        assert parsed.sport == sport and parsed.market_type == "spread"
        assert parsed.subject == subject
        assert parsed.threshold == 2.5
        assert parsed.competitors == ("Alpha Team", "Beta Team")
    # Fail-closed: no floor_strike, malformed suffix, or missing title split.
    assert parse_sports_contract(_market(
        "KXNFLSPREAD-26SEP132025KCBUF-KC3", "Chiefs vs Bills Spread")) is None
    assert parse_sports_contract(_market(
        "KXNFLSPREAD-26SEP132025KCBUF-3KC", "A vs B Spread", floor_strike=2.5)) is None
    assert parse_sports_contract(_market(
        "KXNFLSPREAD-26SEP132025KCBUF-KC3", "No Versus Here Spread", floor_strike=2.5)) is None


# -- signal integration ----------------------------------------------------------

def _signal_with_game(league: str, home: str, away: str,
                      home_name: str, away_name: str, tmp_path):
    client = EspnClient(fetch_scoreboard=lambda _league, _dates: {"events": []})
    game = Game("g1", league, home, away, "pre", None, "2026-09-13T20:25Z",
                home_name=home_name, away_name=away_name)
    client._cache[(league, "20260913")] = [game]
    models = {key: TeamScoreModel(key) for key in LEAGUE_SCORE_CONFIGS}

    class _AlwaysActive:
        def active(self, _league):
            return True

    return TeamSportsIntelligenceSignal(
        espn=client, models=models, model_dir=tmp_path, seasons=_AlwaysActive(),
    ), models


def test_nfl_spread_and_winner_price_from_the_kernel(tmp_path):
    signal, models = _signal_with_game(
        "nfl", "KC", "BUF", "Kansas City Chiefs", "Buffalo Bills", tmp_path)
    spread = signal.generate(_market(
        "KXNFLSPREAD-26SEP132025KCBUF-KC3",
        "Kansas City Chiefs vs Buffalo Bills Spread", floor_strike=2.5))
    assert spread is not None
    assert spread.source == "nfl_spread"
    assert spread.features["challenger_only"] is True
    assert spread.features["margin_model_version"] == "nfl_key_number_kernel_v1"
    # Cold models -> home edge only (2.0 pts). Kernel value ~0.514 on the
    # 2.5 line; the kernel-specific behavior is pinned by the ladder/
    # coherence tests plus the margin_model_version assertion above.
    assert 0.45 < spread.probability_yes < 0.55

    winner = signal.generate(_market(
        "KXNFLGAME-26SEP132025KCBUF-KC", "Chiefs vs Bills Winner?"))
    assert winner is not None
    assert winner.features.get("margin_model_version") == "nfl_key_number_kernel_v1"
    # Kernel coherence at the signal level: winner prob must sit between
    # adjacent spread rungs of the same distribution.
    cover_05 = signal.generate(_market(
        "KXNFLSPREAD-26SEP132025KCBUF-KC1",
        "Kansas City Chiefs vs Buffalo Bills Spread", floor_strike=0.5))
    assert cover_05 is not None
    assert winner.probability_yes >= cover_05.probability_yes  # tie mass split


def test_nfl_live_signal_prices_winner_spread_total_from_one_state_model(tmp_path):
    client = EspnClient(fetch_scoreboard=lambda _league, _dates: {"events": []})
    game = Game(
        "g1", "nfl", "KC", "BUF", "in", None, "2026-09-13T20:25Z",
        home_name="Kansas City Chiefs", away_name="Buffalo Bills",
        home_score=20, away_score=17, current_period=4, current_clock="2:00",
    )
    client._cache[("nfl", "20260913")] = [game]
    models = {key: TeamScoreModel(key) for key in LEAGUE_SCORE_CONFIGS}

    class _AlwaysActive:
        def active(self, _league):
            return True

    signal = TeamSportsIntelligenceSignal(
        espn=client, models=models, model_dir=tmp_path, seasons=_AlwaysActive(),
    )
    winner = signal.generate(_market(
        "KXNFLGAME-26SEP132025KCBUF-KC", "Chiefs vs Bills Winner?"))
    spread = signal.generate(_market(
        "KXNFLSPREAD-26SEP132025KCBUF-KC1",
        "Kansas City Chiefs vs Buffalo Bills Spread", floor_strike=0.5))
    total = signal.generate(_market(
        "KXNFLTOTAL-26SEP132025KCBUF", "Chiefs vs Bills Total Points",
        floor_strike=40.5))

    assert winner is not None and spread is not None and total is not None
    assert winner.source == "nfl_live_winner"
    assert spread.source == "nfl_live_spread"
    assert total.source == "nfl_live_total"
    for result in (winner, spread, total):
        assert result.features["live"] is True
        assert result.features["live_model_version"] == NFL_LIVE_MODEL_VERSION
        assert result.features["minutes_remaining"] == pytest.approx(2.0)
        assert result.features["expected_scores_post_shift"] is True
    assert winner.probability_yes >= spread.probability_yes


def test_nfl_live_signal_abstains_on_overtime_without_possession_state(tmp_path):
    client = EspnClient(fetch_scoreboard=lambda _league, _dates: {"events": []})
    client._cache[("nfl", "20260913")] = [Game(
        "g1", "nfl", "KC", "BUF", "in", None, "2026-09-13T20:25Z",
        home_name="Kansas City Chiefs", away_name="Buffalo Bills",
        home_score=24, away_score=24, current_period=5, current_clock="8:00",
    )]
    signal = TeamSportsIntelligenceSignal(espn=client, model_dir=tmp_path)
    assert signal.generate(_market(
        "KXNFLGAME-26SEP132025KCBUF-KC", "Chiefs vs Bills Winner?")) is None


def test_generic_league_spread_uses_normal_margin(tmp_path):
    signal, _models = _signal_with_game(
        "nba", "LAL", "BOS", "Los Angeles Lakers", "Boston Celtics", tmp_path)
    spread = signal.generate(_market(
        "KXNBASPREAD-26SEP13LALBOS-LAL7",
        "Los Angeles Lakers vs Boston Celtics Spread", floor_strike=6.5))
    assert spread is not None
    assert spread.source == "nba_spread"
    assert "margin_model_version" not in spread.features
    # Cold models: home edge 3.0, sigma 12 -> P(margin > 6.5) < 0.5.
    assert 0.2 < spread.probability_yes < 0.5
    # Away-subject side prices the mirrored margin.
    away = signal.generate(_market(
        "KXNBASPREAD-26SEP13LALBOS-BOS7",
        "Los Angeles Lakers vs Boston Celtics Spread", floor_strike=6.5))
    assert away is not None and away.probability_yes < spread.probability_yes
