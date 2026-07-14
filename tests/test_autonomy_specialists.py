"""Council-of-specialists protocol, routing, and zero-change wrappers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.specialists import SpecialistRegistry, build_specialist_registry
from autonomy.specialists.crypto import CryptoSpecialist
from autonomy.specialists.mlb import MlbSpecialist
from autonomy.specialists.team_leagues import TeamLeagueSpecialist
from autonomy.sports.espn import EspnClient, Game

NOW = datetime(2026, 7, 12, tzinfo=timezone.utc)


def _market(ticker: str, title: str, vertical: Vertical = Vertical.SPORTS, **raw) -> MarketView:
    payload = {"event_ticker": ticker.rsplit("-", 1)[0], **raw}
    return MarketView(
        ticker=ticker, title=title, vertical=vertical, status="open",
        close_time=(NOW + timedelta(hours=6)).isoformat(),
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56,
        volume=500, liquidity=1_000, raw=payload,
    )


def _signal(source: str, ticker: str, probability: float, **features) -> Signal:
    return Signal(
        source=source, market_ticker=ticker, probability_yes=probability,
        uncertainty=0.10, rationale="test", features=features,
    )


class _StubIntelligence:
    """Minimal generate()-only stand-in for a registered signal source."""

    def __init__(self, name: str, signal: Signal | None = None):
        self.name = name
        self.signal = signal
        self.calls: list[str] = []

    def generate(self, market: MarketView) -> Signal | None:
        self.calls.append(market.ticker)
        return self.signal


class _StubSportsbook:
    name = "sportsbook_consensus"

    def __init__(self, probability: float | None = 0.58):
        self.probability = probability

    def applicable(self, market: MarketView) -> bool:
        return market.vertical is Vertical.SPORTS

    def generate(self, market: MarketView) -> Signal | None:
        if self.probability is None:
            return None
        return _signal(self.name, market.ticker, self.probability)


class _StubLiveBook:
    def __init__(self, home_probability: float | None, ejections=()):
        self.home_probability = home_probability
        self.ejections = tuple(ejections)
        self.cleared = 0

    def home_win_probability(self, event_id: str | None) -> float | None:
        return self.home_probability

    def ejection_events(self, event_id: str | None):
        return self.ejections if event_id else ()

    def clear(self) -> None:
        self.cleared += 1


def _espn_with_game(status: str) -> EspnClient:
    client = EspnClient(fetch_scoreboard=lambda _league, _dates: {"events": []})
    game = Game(
        "g1", "mlb", "HOU", "TEX", status, None, "2026-07-12T20:05Z",
        home_score=3 if status != "pre" else None,
        away_score=1 if status != "pre" else None,
    )
    client._cache[("mlb", "20260712")] = [game]
    return client


def _mlb_winner_market() -> MarketView:
    return _market("KXMLBGAME-26JUL122005HOUTEX-HOU", "Astros vs Rangers Winner?")


def _espn_with_team_game(league: str, status: str) -> EspnClient:
    client = EspnClient(fetch_scoreboard=lambda _league, _dates: {"events": []})
    home, away = {
        "nba": ("LAL", "BOS"),
        "nhl": ("NYR", "BOS"),
        "nfl": ("KC", "BUF"),
        "ncaaf": ("TEX", "OU"),
        "ncaamb": ("DUKE", "UNC"),
    }[league]
    game = Game(
        "g-team", league, home, away, status, None, "2026-07-12T20:05Z",
        home_score=60 if status == "in" else None,
        away_score=50 if status == "in" else None,
        current_period=3 if status == "in" else None,
        current_clock="6:00" if status == "in" else None,
    )
    client._cache[(league, "20260712")] = [game]
    return client


# -- routing -----------------------------------------------------------------

def test_factory_routes_each_vertical_to_exactly_one_specialist():
    class _FakeSourceRegistry:
        def sources(self):
            return [
                _StubIntelligence("mlb_intelligence"),
                _StubIntelligence("team_sports_intelligence"),
                _StubSportsbook(),
                _StubIntelligence("crypto_spot_vol"),
            ]

    council = build_specialist_registry(_FakeSourceRegistry())
    names = [specialist.name for specialist in council.specialists()]
    assert names == ["mlb", "nba", "nfl", "ncaaf", "nhl", "ncaamb", "crypto"]

    cases = {
        "KXMLBGAME-26JUL122005HOUTEX-HOU": "mlb",
        "KXNBAGAME-26JUL12LALBOS-LAL": "nba",
        "KXNFLGAME-26SEP13KCBUF-KC": "nfl",
        "KXNHLGAME-26OCT09NYRBOS-NYR": "nhl",
        "KXNCAAFGAME-26SEP05TEXOU-TEX": "ncaaf",
        "KXNCAAMBGAME-26NOV20DUKEUNC-DUKE": "ncaamb",
    }
    for ticker, expected in cases.items():
        routed = council.route(_market(ticker, "winner?"))
        assert routed is not None and routed.name == expected, ticker

    crypto = council.route(_market(
        "KXBTCD-26JUL1217-T71249.99", "BTC above?", vertical=Vertical.CRYPTO))
    assert crypto is not None and crypto.name == "crypto"

    # No specialist claims WNBA or retired/unknown series: route -> None and
    # callers fall back to their pre-council behavior.
    assert council.route(_market("KXWNBAGAME-26JUL12LVNY-LV", "WNBA winner?")) is None
    assert council.route(_market("KXUFCFIGHT-26JUL12ABCDEF-ABC", "UFC?")) is None


# -- MLB specialist ----------------------------------------------------------

def test_mlb_live_forecast_requires_in_progress_game_and_live_feature():
    live_signal = _signal("mlb_intelligence", "KXMLBGAME-26JUL122005HOUTEX-HOU",
                          0.71, live=True)
    intelligence = _StubIntelligence("mlb_intelligence", live_signal)
    specialist = MlbSpecialist(
        intelligence=intelligence, sportsbook=_StubSportsbook(),
        espn=_espn_with_game("in"), live_book=_StubLiveBook(None),
    )
    market = _mlb_winner_market()
    live = specialist.live_forecast(market)
    assert live is not None and live.probability_yes == 0.71

    # Pre-game: no live view even though the signal itself would fire.
    pre = MlbSpecialist(
        intelligence=intelligence, sportsbook=_StubSportsbook(),
        espn=_espn_with_game("pre"), live_book=_StubLiveBook(None),
    )
    assert pre.live_forecast(market) is None

    # A signal without the live feature is not a live view.
    stale = _signal("mlb_intelligence", market.ticker, 0.71)
    specialist.intelligence = _StubIntelligence("mlb_intelligence", stale)
    assert specialist.live_forecast(market) is None


def test_mlb_book_prefers_live_summary_and_maps_subject_side():
    specialist = MlbSpecialist(
        intelligence=None, sportsbook=_StubSportsbook(0.58),
        espn=_espn_with_game("in"), live_book=_StubLiveBook(0.64),
    )
    market = _mlb_winner_market()  # subject HOU == home
    assert specialist.book(market) == 0.64

    away = _market("KXMLBGAME-26JUL122005HOUTEX-TEX", "Astros vs Rangers Winner?")
    assert abs(specialist.book(away) - 0.36) < 1e-9

    # Live book missing -> pre-game consensus fallback inside the specialist.
    cold_live = MlbSpecialist(
        intelligence=None, sportsbook=_StubSportsbook(0.58),
        espn=_espn_with_game("in"), live_book=_StubLiveBook(None),
    )
    assert cold_live.book(market) == 0.58


def test_mlb_cycle_start_clears_only_the_live_book():
    live_book = _StubLiveBook(0.5)
    specialist = MlbSpecialist(
        intelligence=None, sportsbook=None,
        espn=_espn_with_game("pre"), live_book=live_book,
    )
    specialist.on_cycle_start()
    assert live_book.cleared == 1


# -- team-league + crypto specialists ----------------------------------------

def test_team_league_specialist_exposes_existing_nba_live_view_and_summary_book():
    market = _market("KXNBAGAME-26JUL12LALBOS-LAL", "Lakers vs Celtics Winner?")
    live_signal = _signal("nba_live_winner", market.ticker, 0.74, live=True)
    specialist = TeamLeagueSpecialist(
        league="nba", intelligence=_StubIntelligence("team_sports_intelligence", live_signal),
        sportsbook=_StubSportsbook(0.61),
        espn=_espn_with_team_game("nba", "in"), live_book=_StubLiveBook(0.66),
    )
    assert specialist.applicable(market)
    assert specialist.live_forecast(market) == live_signal
    assert specialist.book(market) == 0.66

    away = _market("KXNBAGAME-26JUL12LALBOS-BOS", "Lakers vs Celtics Winner?")
    assert abs(specialist.book(away) - 0.34) < 1e-9


def test_team_league_specialist_exposes_existing_nhl_live_view_and_summary_book():
    market = _market("KXNHLGAME-26JUL12NYRBOS-NYR", "Rangers vs Bruins Winner?")
    live_signal = _signal("nhl_live_winner", market.ticker, 0.63, live=True)
    specialist = TeamLeagueSpecialist(
        "nhl", _StubIntelligence("team_sports_intelligence", live_signal),
        _StubSportsbook(0.55), espn=_espn_with_team_game("nhl", "in"),
        live_book=_StubLiveBook(0.62),
    )
    assert specialist.live_forecast(market) == live_signal
    assert specialist.book(market) == 0.62


def test_team_league_specialist_exposes_new_live_team_model_views():
    cases = (
        ("nfl", "KXNFLGAME-26JUL12KCBUF-KC", "nfl_live_winner"),
        ("ncaaf", "KXNCAAFGAME-26JUL12TEXOU-TEX", "ncaaf_live_winner"),
        ("ncaamb", "KXNCAAMBGAME-26JUL12DUKEUNC-DUKE", "ncaamb_live_winner"),
    )
    for league, ticker, source in cases:
        market = _market(ticker, "Alpha vs Beta Winner?")
        live_signal = _signal(source, ticker, 0.64, live=True)
        specialist = TeamLeagueSpecialist(
            league, _StubIntelligence("team_sports_intelligence", live_signal),
            _StubSportsbook(0.55), espn=_espn_with_team_game(league, "in"),
            live_book=_StubLiveBook(0.60),
        )
        assert specialist.live_forecast(market) == live_signal


def test_team_league_live_view_remains_fail_closed_for_missing_models_and_pregame():
    market = _market("KXNBAGAME-26JUL12LALBOS-LAL", "Lakers vs Celtics Winner?")
    signal_without_live_feature = _signal("nba_structural_winner", market.ticker, 0.60)
    stale = TeamLeagueSpecialist(
        "nba", _StubIntelligence("team_sports_intelligence", signal_without_live_feature),
        _StubSportsbook(0.61), espn=_espn_with_team_game("nba", "in"),
        live_book=_StubLiveBook(None),
    )
    assert stale.live_forecast(market) is None
    assert stale.book(market) == 0.61

    pre = TeamLeagueSpecialist(
        "nba", _StubIntelligence("team_sports_intelligence", signal_without_live_feature),
        _StubSportsbook(0.61), espn=_espn_with_team_game("nba", "pre"),
        live_book=_StubLiveBook(0.66),
    )
    assert pre.live_forecast(market) is None
    assert pre.book(market) == 0.61

    nfl_market = _market("KXNFLGAME-26JUL12KCBUF-KC", "Chiefs vs Bills Winner?")
    nfl = TeamLeagueSpecialist(
        "nfl", _StubIntelligence("team_sports_intelligence", None), None,
        espn=_espn_with_team_game("nfl", "in"), live_book=_StubLiveBook(0.60),
    )
    assert nfl.live_forecast(nfl_market) is None


def test_team_league_ejections_are_evidence_only_and_cache_clears_each_cycle():
    market = _market("KXNBAGAME-26JUL12LALBOS-LAL", "Lakers vs Celtics Winner?")
    event = {"event_type": "ejection", "text": "Player ejected"}
    live_book = _StubLiveBook(0.66, [event])
    specialist = TeamLeagueSpecialist(
        "nba", _StubIntelligence("team_sports_intelligence"), _StubSportsbook(),
        espn=_espn_with_team_game("nba", "in"), live_book=live_book,
    )
    assert specialist.ejection_events(market) == (event,)
    specialist.on_cycle_start()
    assert live_book.cleared == 1


def test_team_league_book_never_maps_moneyline_to_spread_or_total():
    spread = _market(
        "KXNBASPREAD-26JUL12LALBOS-LAL5", "Lakers win by over 4.5 points?",
        floor_strike=4.5,
    )
    specialist = TeamLeagueSpecialist(
        "nba", _StubIntelligence("team_sports_intelligence"), None,
        espn=_espn_with_team_game("nba", "in"), live_book=_StubLiveBook(0.66),
    )
    assert specialist.book(spread) is None


def test_crypto_specialist_routes_and_abstains_from_book_when_unwired():
    champion_signal = _signal("crypto_spot_vol", "KXBTCD-26JUL1217-T71249.99", 0.55)
    specialist = CryptoSpecialist(champion=_StubIntelligence("crypto_spot_vol", champion_signal))
    market = _market("KXBTCD-26JUL1217-T71249.99", "BTC above 71249.99?",
                     vertical=Vertical.CRYPTO)
    assert specialist.applicable(market)
    assert specialist.forecast(market).probability_yes == 0.55
    assert specialist.book(market) is None
    assert specialist.live_forecast(market) is None
    assert not specialist.applicable(_mlb_winner_market())


def test_crypto_specialist_book_uses_wired_implied_book_and_fails_closed():
    class _StubImpliedBook:
        def __init__(self, value):
            self.value = value

        def book_probability(self, market):
            if isinstance(self.value, Exception):
                raise self.value
            return self.value

    market = _market("KXBTCD-26JUL1217-T71249.99", "BTC above?",
                     vertical=Vertical.CRYPTO)
    wired = CryptoSpecialist(champion=None, implied_book=_StubImpliedBook(0.63))
    assert wired.book(market) == 0.63
    assert wired.health().details["book"] == "dvol_implied"
    # A raising book abstains instead of propagating.
    broken = CryptoSpecialist(champion=None,
                              implied_book=_StubImpliedBook(RuntimeError("hub down")))
    assert broken.book(market) is None
    # Non-crypto markets never reach the book.
    assert wired.book(_mlb_winner_market()) is None


def test_factory_wires_dvol_implied_book_from_hub_backed_signal():
    state = {"dvol": 50.0, "spot": 71_000.0}

    class _StubDvolSignal:
        name = "crypto_dvol_implied"

        def __init__(self):
            self.fetch_state = lambda _asset: state

    class _FakeSourceRegistry:
        def sources(self):
            return [_StubDvolSignal()]

    council = build_specialist_registry(_FakeSourceRegistry())
    crypto = next(s for s in council.specialists() if s.name == "crypto")
    assert crypto.implied_book is not None
    market = _market("KXBTCD-26JUL1317-T70000", "BTC above 70000?",
                     vertical=Vertical.CRYPTO)
    probability = crypto.book(market)
    assert probability is not None and probability > 0.5  # spot above strike
    # No hub-backed signal registered -> no book, crypto stays model_only.
    class _EmptyRegistry:
        def sources(self):
            return []

    cold = build_specialist_registry(_EmptyRegistry())
    cold_crypto = next(s for s in cold.specialists() if s.name == "crypto")
    assert cold_crypto.implied_book is None
    assert cold_crypto.book(market) is None


def test_mlb_methods_fail_closed_when_espn_fetch_raises():
    class _RaisingEspn:
        def find_matchup(self, *_args, **_kwargs):
            raise RuntimeError("espn down")

    live_signal = _signal("mlb_intelligence", "KXMLBGAME-26JUL122005HOUTEX-HOU",
                          0.71, live=True)
    specialist = MlbSpecialist(
        intelligence=_StubIntelligence("mlb_intelligence", live_signal),
        sportsbook=_StubSportsbook(0.58),
        espn=_RaisingEspn(), live_book=_StubLiveBook(0.64),
    )
    market = _mlb_winner_market()
    # Every protocol method abstains instead of propagating the feed error.
    # book() abstains entirely (matching the pre-council monitor, whose whole
    # book closure aborted to None when the live-game lookup raised).
    assert specialist.live_forecast(market) is None
    assert specialist.book(market) is None
    assert specialist.forecast(market) is not None  # routing needs no ESPN fetch


# -- registry isolation -------------------------------------------------------

def test_registry_isolates_broken_specialists():
    class _Broken:
        name = "broken"

        def applicable(self, market):
            raise RuntimeError("boom")

        def on_cycle_start(self):
            raise RuntimeError("boom")

        def health(self):
            raise RuntimeError("boom")

    healthy = CryptoSpecialist(champion=None)
    registry = SpecialistRegistry()
    registry.register(_Broken())
    registry.register(healthy)

    market = _market("KXBTCD-26JUL1217-T71249.99", "BTC?", vertical=Vertical.CRYPTO)
    assert registry.route(market) is healthy
    registry.on_cycle_start()  # broken warmup must not raise

    report = registry.health_report()
    assert [entry["name"] for entry in report] == ["broken", "crypto"]
    assert report[0]["status"] == "degraded"
    assert report[1]["status"] == "cold"  # no champion wired -> cold, not error
