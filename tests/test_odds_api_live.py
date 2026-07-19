"""Wave-9: Odds API credit governor + governed client + licensed consensus."""
from __future__ import annotations


from autonomy.odds_api_budget import ODDS_CALL_COST, OddsApiBudget
from autonomy.odds_api_client import OddsApiClient
from autonomy.ontology import MarketView, Vertical
from autonomy.signals.licensed_consensus import LicensedConsensusSignal


class _Clock:
    def __init__(self, t=1_784_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def _budget(tmp_path, daily=500, clock=None, line_reserve=0):
    # line_reserve defaults to 0 here so these Wave-9 cap/cache tests exercise
    # the raw daily cap; the Wave-31 reservation has its own test module.
    return OddsApiBudget(
        daily_credits=daily,
        line_reserve=line_reserve,
        budget_path=tmp_path / "budget.json",
        cache_dir=tmp_path / "cache",
        now_fn=clock or _Clock(),
    )


# ---- governor: caching ---------------------------------------------------------

def test_ttl_cache_serves_without_spending(tmp_path):
    clock = _Clock()
    budget = _budget(tmp_path, clock=clock)
    calls = []

    def fetch():
        calls.append(1)
        return [{"game": 1}], 19_997

    p, src = budget.budgeted_fetch("k", fetch)
    assert src == "live" and p == [{"game": 1}] and len(calls) == 1
    # Within TTL: served from cache, no second call, no spend.
    p, src = budget.budgeted_fetch("k", fetch)
    assert src == "cache" and len(calls) == 1
    assert budget.status()["spent_today"] == ODDS_CALL_COST
    # After TTL expires: refetch.
    clock.t += 2000
    p, src = budget.budgeted_fetch("k", fetch)
    assert src == "live" and len(calls) == 2


# ---- governor: budget ----------------------------------------------------------

def test_daily_budget_caps_spend_and_serves_stale(tmp_path):
    clock = _Clock()
    budget = _budget(tmp_path, daily=ODDS_CALL_COST, clock=clock)  # room for exactly one call

    def fetch():
        return [{"v": 1}], None
    _, src = budget.budgeted_fetch("k", fetch)
    assert src == "live"
    # Cache expired but budget is gone -> serve stale, never spend past the cap.
    clock.t += 5000
    _, src = budget.budgeted_fetch("k", fetch)
    assert src == "stale"
    assert budget.status()["spent_today"] == ODDS_CALL_COST
    # A brand-new key with no cache and no budget -> budget_exhausted, None.
    payload, src = budget.budgeted_fetch("other", fetch)
    assert payload is None and src == "budget_exhausted"


def test_remaining_header_hard_stops(tmp_path):
    budget = _budget(tmp_path, daily=10_000)

    def fetch():
        return [{"v": 1}], 2                # plan says only 2 credits remain
    _, src = budget.budgeted_fetch("k", fetch)
    assert src == "live"
    assert budget.can_spend(ODDS_CALL_COST) is False   # 2 < 3, even under daily cap


def test_day_and_month_rollover(tmp_path):
    clock = _Clock()
    budget = _budget(tmp_path, clock=clock)
    budget.budgeted_fetch("k", lambda: ([1], None))
    assert budget.status()["spent_today"] == ODDS_CALL_COST
    clock.t += 30 * 24 * 3600                # a month later
    assert budget.status()["spent_today"] == 0
    assert budget.status()["spent_month"] == 0


def test_fetch_error_falls_back_to_stale_then_error(tmp_path):
    clock = _Clock()
    budget = _budget(tmp_path, clock=clock)
    budget.budgeted_fetch("k", lambda: ([{"ok": 1}], None))

    def boom():
        raise RuntimeError("network down")

    clock.t += 5000
    p, src = budget.budgeted_fetch("k", boom)
    assert src == "stale" and p == [{"ok": 1}]         # last good payload survives
    p, src = budget.budgeted_fetch("fresh", boom)
    assert p is None and src == "error"


# ---- governed client -----------------------------------------------------------

def _client(tmp_path, monkeypatch, http_get, key="testkey", enabled=True):
    monkeypatch.setenv("DUMMY_ODDS_API_KEY", key)
    if enabled:
        monkeypatch.setenv("DUMMY_ODDS_API_ENABLED", "1")
    else:
        monkeypatch.delenv("DUMMY_ODDS_API_ENABLED", raising=False)
    return OddsApiClient(budget=_budget(tmp_path), http_get=http_get)


def test_client_inert_unless_armed(tmp_path, monkeypatch):
    calls = []

    def http(url, params):
        calls.append(url)
        return [], None
    client = _client(tmp_path, monkeypatch, http, enabled=False)
    assert client.available is False
    events, src = client.consensus_odds("baseball_mlb")
    assert events == [] and src == "inert" and calls == []   # never touches network


def test_client_skips_out_of_season_sport(tmp_path, monkeypatch):
    def http(url, params):
        if url.endswith("/sports/"):
            return [{"key": "baseball_mlb", "active": True}], None
        raise AssertionError("must not fetch odds for an inactive sport")
    client = _client(tmp_path, monkeypatch, http)
    events, src = client.consensus_odds("basketball_nba")   # not in active set
    assert events == [] and src == "out_of_season"


def test_client_fetches_active_sport_and_tracks_header(tmp_path, monkeypatch):
    def http(url, params):
        if url.endswith("/sports/"):
            return [{"key": "baseball_mlb", "active": True}], None
        return [{"home_team": "Boston Red Sox", "away_team": "Tampa Bay Rays",
                 "bookmakers": []}], 19_997
    client = _client(tmp_path, monkeypatch, http)
    events, src = client.consensus_odds("baseball_mlb")
    assert src == "live" and len(events) == 1
    assert client.budget.status()["remaining_reported"] == 19_997


# ---- licensed consensus signal -------------------------------------------------

class _Game:
    def __init__(self, status="pre", home="NYY", away="BOS",
                 home_name="New York Yankees", away_name="Boston Red Sox"):
        self.status, self.home, self.away = status, home, away
        self.home_name, self.away_name = home_name, away_name


class _Espn:
    def __init__(self, game):
        self._game = game

    def clear_cache(self):
        pass

    def find_matchup(self, league, a, b, dates=None):
        return self._game

    def find_matchup_names(self, league, a, b, dates=None):
        return self._game


class _StubClient:
    available = True

    def __init__(self, events):
        self._events = events

    def consensus_odds(self, sport_key):
        return self._events, "cache"


def _mlb_events():
    def book(h, a):
        return {"key": "dk", "markets": [{"key": "h2h", "outcomes": [
            {"name": "New York Yankees", "price": h},
            {"name": "Boston Red Sox", "price": a}]}]}
    return [{"home_team": "New York Yankees", "away_team": "Boston Red Sox",
             "bookmakers": [book(-150, 130), book(-160, 140)]}]


def _market():
    return MarketView(ticker="KXMLBGAME-26JUL17NYYBOS-NYY", title="NYY?",
                      vertical=Vertical.SPORTS, status="open",
                      close_time="2026-07-17T23:00:00+00:00", yes_bid=44, yes_ask=46,
                      no_bid=54, no_ask=56, volume=10, liquidity=10, raw={})


def test_licensed_consensus_devigs_multibook_and_is_challenger():
    signal = LicensedConsensusSignal(
        espn=_Espn(_Game()), client=_StubClient(_mlb_events()))
    out = signal.generate(_market())
    assert out is not None
    assert out.source == "licensed_consensus"
    assert out.features["challenger_only"] is True
    assert out.features["book_count"] == 2
    assert 0.58 < out.probability_yes < 0.63          # -150/-160 devig ~ 0.60 home


def test_licensed_consensus_inert_when_slot_unarmed():
    class _Off(_StubClient):
        available = False
    signal = LicensedConsensusSignal(espn=_Espn(_Game()), client=_Off([]))
    assert signal.applicable(_market()) is False
    assert signal.generate(_market()) is None


def test_licensed_consensus_fail_closed_started_game():
    signal = LicensedConsensusSignal(
        espn=_Espn(_Game(status="in")), client=_StubClient(_mlb_events()))
    assert signal.generate(_market()) is None          # started -> stale line


def test_licensed_consensus_none_when_game_absent():
    signal = LicensedConsensusSignal(espn=_Espn(None), client=_StubClient(_mlb_events()))
    assert signal.generate(_market()) is None


# ---- Wave-11: full-game totals / spreads off the same slate payload ------------


def _line_events(*, total_line=8.5, second_book_total_line=8.5):
    """One event, two books, each quoting totals and spreads."""
    def book(key, tot_line, over, under):
        return {
            "key": key,
            "markets": [
                {"key": "totals", "outcomes": [
                    {"name": "Over", "price": over, "point": tot_line},
                    {"name": "Under", "price": under, "point": tot_line}]},
                {"key": "spreads", "outcomes": [
                    {"name": "Boston Red Sox", "price": 120, "point": -1.5},
                    {"name": "New York Yankees", "price": -140, "point": 1.5}]},
            ],
        }
    return [{"home_team": "New York Yankees", "away_team": "Boston Red Sox",
             "bookmakers": [book("dk", total_line, -110, -110),
                            book("fd", second_book_total_line, -120, 100)]}]


def _total_market(strike=8.5):
    return MarketView(
        ticker="KXMLBTOTAL-26JUL17NYYBOS-T85",
        title="New York Yankees vs Boston Red Sox Total Runs?",
        vertical=Vertical.SPORTS, status="open",
        close_time="2026-07-17T23:00:00+00:00", yes_bid=48, yes_ask=52,
        no_bid=48, no_ask=52, volume=10, liquidity=10,
        raw={"floor_strike": strike})


def _spread_market(subject="BOS", strike=1.5):
    return MarketView(
        ticker=f"KXMLBSPREAD-26JUL17NYYBOS-{subject}15",
        title="New York Yankees vs Boston Red Sox Spread?",
        vertical=Vertical.SPORTS, status="open",
        close_time="2026-07-17T23:00:00+00:00", yes_bid=40, yes_ask=44,
        no_bid=56, no_ask=60, volume=10, liquidity=10,
        raw={"floor_strike": strike})


def test_licensed_total_devigs_books_at_exact_line():
    signal = LicensedConsensusSignal(
        espn=_Espn(_Game()), client=_StubClient(_line_events()))
    market = _total_market()
    assert signal.applicable(market) is True
    out = signal.generate(market)
    assert out is not None
    assert out.source == "licensed_consensus_total"
    assert out.features["challenger_only"] is True
    assert out.features["book_count"] == 2
    assert out.features["line"] == 8.5
    # dk -110/-110 -> 0.500; fd -120/+100 -> 0.5455/1.0455 = 0.5217; avg 0.511
    assert 0.50 < out.probability_yes < 0.52


def test_licensed_total_skips_books_quoting_a_different_line():
    events = _line_events(second_book_total_line=9.5)
    signal = LicensedConsensusSignal(espn=_Espn(_Game()), client=_StubClient(events))
    out = signal.generate(_total_market())
    assert out is not None
    assert out.features["book_count"] == 1          # fd's 9.5 quote is unusable
    assert abs(out.probability_yes - 0.5) < 1e-6    # dk -110/-110 only


def test_licensed_total_refuses_integer_line():
    # A book quote at an integer line can push; the de-vig would price
    # P(over | no push), which is not the Kalshi binary. Fail closed.
    signal = LicensedConsensusSignal(
        espn=_Espn(_Game()), client=_StubClient(_line_events(total_line=9.0)))
    assert signal.generate(_total_market(strike=9.0)) is None


def test_licensed_total_none_when_no_book_quotes_the_line():
    events = _line_events(total_line=7.5, second_book_total_line=9.5)
    signal = LicensedConsensusSignal(espn=_Espn(_Game()), client=_StubClient(events))
    assert signal.generate(_total_market(strike=8.5)) is None


def test_licensed_spread_prices_subject_side():
    signal = LicensedConsensusSignal(
        espn=_Espn(_Game()), client=_StubClient(_line_events()))
    market = _spread_market(subject="BOS", strike=1.5)
    out = signal.generate(market)
    assert out is not None
    assert out.source == "licensed_consensus_spread"
    assert out.features["subject_home"] is False
    # BOS -1.5 at +120 vs NYY +1.5 at -140: 0.4545/1.0379 ~ 0.438 per book.
    assert 0.42 < out.probability_yes < 0.46


def test_licensed_spread_negative_line_is_the_underdog_side():
    # NYY margin > -1.5 (win, or lose by 1): the book quotes NYY at +1.5.
    signal = LicensedConsensusSignal(
        espn=_Espn(_Game()), client=_StubClient(_line_events()))
    out = signal.generate(_spread_market(subject="NYY", strike=-1.5))
    assert out is not None
    assert out.features["subject_home"] is True
    # NYY +1.5 at -140 vs BOS -1.5 at +120: 0.5833/1.0379 ~ 0.562 per book.
    assert 0.54 < out.probability_yes < 0.58


def test_licensed_line_fail_closed_started_game_and_unarmed():
    started = LicensedConsensusSignal(
        espn=_Espn(_Game(status="in")), client=_StubClient(_line_events()))
    assert started.generate(_total_market()) is None

    class _Off(_StubClient):
        available = False
    off = LicensedConsensusSignal(espn=_Espn(_Game()), client=_Off([]))
    assert off.applicable(_total_market()) is False
    assert off.generate(_total_market()) is None


def test_licensed_line_ignores_segment_markets():
    # F5 totals belong to the segment wave; the slate quotes full-game only.
    signal = LicensedConsensusSignal(
        espn=_Espn(_Game()), client=_StubClient(_line_events()))
    f5 = MarketView(
        ticker="KXMLBF5TOTAL-26JUL17NYYBOS-T45",
        title="New York Yankees vs Boston Red Sox First Five Total?",
        vertical=Vertical.SPORTS, status="open",
        close_time="2026-07-17T23:00:00+00:00", yes_bid=48, yes_ask=52,
        no_bid=48, no_ask=52, volume=10, liquidity=10,
        raw={"floor_strike": 4.5})
    assert signal.applicable(f5) is False
    assert signal.generate(f5) is None


def test_wnba_mapped_and_line_sources_have_a_taxonomy_home():
    from autonomy.signals.licensed_consensus import LEAGUE_TO_ODDS_SPORT
    from autonomy.taxonomy import specialist_for

    assert LEAGUE_TO_ODDS_SPORT["wnba"] == "basketball_wnba"
    assert specialist_for("licensed_consensus") == "sportsbook"
    assert specialist_for("licensed_consensus_total") == "sportsbook"
    assert specialist_for("licensed_consensus_spread") == "sportsbook"
