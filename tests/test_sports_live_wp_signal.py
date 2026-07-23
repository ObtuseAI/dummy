"""Live-WP challenger: prices in-progress games from the comeback matrices."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autonomy.ingest.pbp_lake import write_pbp_artifact
from autonomy.ontology import MarketView, Vertical
from autonomy.signals.sports_live_wp import SportsLiveWpSignal


NOW = datetime(2026, 1, 10, tzinfo=timezone.utc)


class _Game:
    def __init__(self, home, away, status, period=None, hs=None, as_=None):
        self.home, self.away, self.status = home, away, status
        self.current_period, self.home_score, self.away_score = period, hs, as_


class _Espn:
    def __init__(self, game):
        self._game = game
    def clear_cache(self):
        pass
    def find_matchup(self, league, subject, opponent, dates=None):
        return self._game


def _artifact(tmp_path):
    # NBA comeback matrix: after period 2, home lead bucket [6,10) -> 0.85 (n=200).
    path = tmp_path / "sports_pbp_params.json"
    write_pbp_artifact({"nba": {
        "games": 5000,
        "per_season": {"2024": {"comeback": {"after_period_2": {
            "[6,10)": {"n": 200, "home_win_rate": 0.85},
        }}}},
    }}, path=path)
    return path


def _market():
    return MarketView(
        ticker="KXNBAGAME-26JAN10BOSLAL-BOS", title="Celtics vs Lakers Winner?",
        vertical=Vertical.SPORTS, status="open",
        close_time=(NOW + timedelta(hours=3)).isoformat(),
        yes_bid=48, yes_ask=52, no_bid=48, no_ask=52, volume=100, liquidity=500,
        raw={},
    )


def _signal(tmp_path, game, monkeypatch):
    monkeypatch.setattr(
        "autonomy.sports.pbp_params.DEFAULT_ARTIFACT_PATH", _artifact(tmp_path),
    )
    sig = SportsLiveWpSignal(espn=_Espn(game))
    return sig.generate(_market())


def test_live_game_priced_from_comeback_cell(tmp_path, monkeypatch):
    # In period 3 (period_completed=2), home BOS leads by 8 -> [6,10) bucket.
    game = _Game("BOS", "LAL", "in", period=3, hs=70, as_=62)
    signal = _signal(tmp_path, game, monkeypatch)
    assert signal is not None
    assert signal.source == "sports_live_wp"
    assert abs(signal.probability_yes - 0.85) < 1e-9  # BOS is home + subject
    assert signal.features["historical_sample"] == 200
    assert signal.features["lead_bucket"] == "[6,10)"


def test_away_subject_gets_complement(tmp_path, monkeypatch):
    # Subject LAL is away; home BOS leads -> subject prob is 1 - 0.85.
    market = MarketView(
        ticker="KXNBAGAME-26JAN10BOSLAL-LAL", title="Lakers vs Celtics Winner?",
        vertical=Vertical.SPORTS, status="open",
        close_time=(NOW + timedelta(hours=3)).isoformat(),
        yes_bid=48, yes_ask=52, no_bid=48, no_ask=52, volume=100, liquidity=500, raw={},
    )
    monkeypatch.setattr(
        "autonomy.sports.pbp_params.DEFAULT_ARTIFACT_PATH", _artifact(tmp_path),
    )
    sig = SportsLiveWpSignal(espn=_Espn(_Game("BOS", "LAL", "in", 3, 70, 62)))
    signal = sig.generate(market)
    assert signal is not None
    assert abs(signal.probability_yes - 0.15) < 1e-9


def test_pregame_and_final_abstain(tmp_path, monkeypatch):
    for status in ("pre", "post"):
        game = _Game("BOS", "LAL", status, period=3, hs=70, as_=62)
        assert _signal(tmp_path, game, monkeypatch) is None


def test_first_period_and_thin_cell_abstain(tmp_path, monkeypatch):
    # period 1 -> period_completed 0 -> abstain.
    assert _signal(tmp_path, _Game("BOS", "LAL", "in", 1, 5, 3), monkeypatch) is None
    # A lead bucket with no historical cell -> abstain.
    assert _signal(tmp_path, _Game("BOS", "LAL", "in", 3, 90, 62), monkeypatch) is None
