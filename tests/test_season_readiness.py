"""Wave-18: every league priced as if the season starts tomorrow.

Two layers:
  * the discovery<->pricing TRIPWIRE: every ``discover=True`` series in the
    registry must be claimed by at least one registered pricing signal's
    ``applicable()`` on a synthetic market of that exact shape. Flipping a
    series on without a pricer (the Wave-10 registry's founding rule) now
    fails the suite instead of silently wasting scan slots;
  * behavior checks for the newly generalized segment/team-total kernel.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.basketball_segments import BasketballSegmentSignal
from autonomy.sports.espn import EspnClient, Game
from autonomy.sports.segment_shares import SEGMENT_SHARES, segment_share, sport_of
from autonomy.sports.team_scores import TeamScoreModel
from autonomy.sports_markets import (
    SERIES_SPEC,
    TEAM_TOTAL,
    WINNER,
    YRFI,
    discovery_series,
)

NOW = datetime(2026, 7, 18, 16, 0, tzinfo=timezone.utc)


def _market(ticker: str, title: str, **raw) -> MarketView:
    payload = {"event_ticker": ticker.rsplit("-", 1)[0], **raw}
    return MarketView(
        ticker=ticker, title=title, vertical=Vertical.SPORTS, status="open",
        close_time=(NOW + timedelta(hours=6)).isoformat(),
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56,
        volume=500, liquidity=1_000, raw=payload,
    )


def _synthetic_market(series: str, spec) -> MarketView:
    """A market of the series' exact shape (ticker grammar + strike)."""
    date = "26NOV20"
    teams = "AAABBB"
    if spec.is_prop:
        return _market(f"{series}-{date}{teams}-PLAYER1",
                       "Some Player: 2+ things?", floor_strike=1.5)
    if spec.market_type == WINNER:
        return _market(f"{series}-{date}{teams}-AAA", "Aaa vs Bbb Winner?")
    if spec.market_type == YRFI:
        return _market(f"{series}-{date}{teams}", "Run in the first inning?")
    if spec.market_type in (TEAM_TOTAL,):
        return _market(f"{series}-{date}{teams}-AAA25",
                       "Will Aaa score over 2.5?", floor_strike=2.5)
    if spec.market_type == "spread":
        return _market(f"{series}-{date}{teams}-AAA35",
                       "Will Aaa win by over 3.5?", floor_strike=3.5)
    return _market(f"{series}-{date}{teams}-T85",
                   "Aaa vs Bbb Total?", floor_strike=8.5)


def _pricing_signals():
    """The classify/parse-driven signals whose applicable() is model-free."""
    from autonomy.signals.licensed_consensus import LicensedConsensusSignal
    from autonomy.signals.licensed_props import LicensedPlayerPropSignal
    from autonomy.signals.mlb_segments import MlbSegmentSignal
    from autonomy.signals.sportsbook import SportsbookConsensusSignal

    class _ArmedStub:
        available = True

        def consensus_odds(self, sport_key):
            return [], "cache"

        def list_events(self, sport_key):
            return [], "cache"

    signals = [
        SportsbookConsensusSignal(),
        LicensedConsensusSignal(client=_ArmedStub()),
        LicensedPlayerPropSignal(),
        MlbSegmentSignal(),
    ]
    for league in ("wnba", "nba", "ncaamb", "nfl", "ncaaf"):
        signals.append(BasketballSegmentSignal(league=league))
    return signals


def test_every_discovered_series_has_a_pricer():
    signals = _pricing_signals()
    unpriced = []
    for series in discovery_series():
        spec = SERIES_SPEC[series]
        market = _synthetic_market(series, spec)
        if spec.is_prop:
            # Props price through the licensed per-event de-vig; the signal
            # is classify-driven and slot-gated, so assert classification
            # (the armed path is covered by test_licensed_props).
            from autonomy.sports_markets import classify

            info = classify(market)
            if info is None or not info.is_prop:
                unpriced.append(series)
            continue
        if spec.market_type == YRFI:
            # YRFI prices inside BaseballIntelligenceSignal (heavyweight
            # constructor); assert its parser owns the series instead.
            from autonomy.signals.sports_intelligence import parse_sports_contract

            contract = parse_sports_contract(_market(
                f"{series}-26NOV20HOUTEX", "Run in the first inning?"))
            if contract is None:
                unpriced.append(series)
            continue
        if not any(s.applicable(market) for s in signals):
            unpriced.append(series)
    assert unpriced == [], f"discovered but unpriceable: {unpriced}"


def test_share_tables_are_coherent():
    # Full-game segment families sum to 1 (halves; quarters; periods).
    for sport, shares in SEGMENT_SHARES.items():
        halves = [v for k, v in shares.items() if k.startswith("h")]
        quarters = [v for k, v in shares.items() if k.startswith("q")]
        periods = [v for k, v in shares.items() if k.startswith("p")]
        if halves:
            assert sum(halves) == pytest.approx(1.0, abs=1e-9), sport
        if quarters:
            assert sum(quarters) == pytest.approx(1.0, abs=1e-9), sport
        if periods:
            assert sum(periods) == pytest.approx(1.0, abs=1e-9), sport
    assert sport_of("nba") == sport_of("wnba") == "basketball"
    assert sport_of("nfl") == "football"
    assert segment_share("nhl", "p3") == pytest.approx(0.36)
    assert segment_share("mlb", "h1") is None      # MLB has its own F5 model


def _signal(league, home, away, game_id="g1"):
    game = Game(game_id, league, home, away, "pre", None, "2026-11-20T20:00Z",
                home_name=f"{home} City", away_name=f"{away} Town")
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    client._cache[(league, "20261120")] = [game]
    return BasketballSegmentSignal(
        league=league, espn=client, model=TeamScoreModel(league))


def test_nfl_halves_and_quarters_price():
    signal = _signal("nfl", "KC", "BUF")
    h2 = signal.generate(_market(
        "KXNFL2HTOTAL-26NOV20KCBUF-T24", "Kc City vs Buf Town: Second Half Total?",
        floor_strike=23.5))
    assert h2 is not None and h2.source == "nfl_2h_total"
    # 2H carries 52.5% of a ~45-point prior total -> ~23.6; the line sits at
    # the mean so the probability hugs the coin flip.
    assert 0.35 < h2.probability_yes < 0.65

    q4 = signal.generate(_market(
        "KXNFL4QSPREAD-26NOV20KCBUF-KC3", "Will Kc win the 4Q by over 2.5?",
        floor_strike=2.5))
    assert q4 is not None and q4.source == "nfl_4q_spread"
    assert q4.probability_yes < 0.5      # cold model: only a small home edge

    h1w = signal.generate(_market(
        "KXNFL1HWINNER-26NOV20KCBUF-TIE", "Kc City vs Buf Town: First Half Winner?"))
    assert h1w is not None and h1w.source == "nfl_1h_winner"
    assert 0.0 < h1w.probability_yes < 0.25     # a real but minority tie mass


def test_team_totals_price_for_every_depth_league():
    for league, home, away, series, line in (
        ("nfl", "KC", "BUF", "KXNFLTEAMTOTAL", 24.5),
        ("nba", "LAL", "BOS", "KXNBATEAMTOTAL", 113.5),
        ("ncaaf", "TEX", "OU", "KXNCAAFTEAMTOTAL", 27.5),
    ):
        signal = _signal(league, home, away)
        out = signal.generate(_market(
            f"{series}-26NOV20{home}{away}-{home}25",
            f"Will {home} score over {line}?", floor_strike=line))
        assert out is not None, league
        assert out.source == f"{league}_team_total"
        assert out.features["challenger_only"] is True
        # Line at/near the prior team score -> probability near the flip.
        assert 0.3 < out.probability_yes < 0.7, league


def test_basketball_second_half_winner_has_tie_leg():
    signal = _signal("wnba", "LVA", "NYL")
    tie = signal.generate(_market(
        "KXWNBA2HWINNER-26NOV20LVANYL-TIE",
        "Lva City vs Nyl Town: Second Half Winner?"))
    assert tie is not None and tie.source == "wnba_2h_winner"
    assert 0.005 < tie.probability_yes < 0.15


def test_wave13_wnba_first_half_sources_unchanged():
    signal = _signal("wnba", "LVA", "NYL")
    out = signal.generate(_market(
        "KXWNBA1HTOTAL-26NOV20LVANYL-T80",
        "Lva City vs Nyl Town: First Half Total?", floor_strike=79.5))
    assert out is not None and out.source == "wnba_1h_total"