"""Wave-3 player-prop plumbing: parse + de-vig, fixtures-first, governance-gated."""
from __future__ import annotations

import json
from pathlib import Path

from autonomy.player_props import (
    FixturePropProvider,
    LicensedPropProvider,
    parse_player_props,
    prop_over_probability,
)

_ROOT = Path(__file__).parents[1]
_SAMPLE = _ROOT / "autonomy" / "fixtures" / "player_props" / "mlb_player_props_sample.json"
_ONESIDED = Path(__file__).parent / "fixtures" / "player_props_onesided.json"


def _sample_payload():
    return json.loads(_SAMPLE.read_text())


# ---- parse + de-vig ----------------------------------------------------------

def test_parses_and_devigs_two_way_props_across_books():
    events = parse_player_props(_sample_payload())
    assert len(events) == 1
    quotes = {(q.market_key, q.player, q.point): q for q in events[0].quotes}
    altuve = quotes[("player_hits", "Jose Altuve", 0.5)]
    assert altuve.n_books == 2                      # DraftKings + FanDuel paired
    assert 0.45 < altuve.prob_over < 0.60           # de-vigged near pick-em
    # total_bases market parsed independently of hits.
    assert ("player_total_bases", "Yordan Alvarez", 1.5) in quotes
    # every de-vigged probability is a valid, non-degenerate probability
    assert all(0.0 < q.prob_over < 1.0 for q in events[0].quotes)


def test_one_sided_and_mismatched_points_fail_closed():
    events = parse_player_props(json.loads(_ONESIDED.read_text()))
    # A lone Over, and Over@1.5 vs Under@2.5, never form a pair -> no quotes.
    assert [len(e.quotes) for e in events] == [0]


def test_malformed_payloads_yield_no_quotes():
    assert parse_player_props(None) == []
    assert parse_player_props({}) == []
    assert parse_player_props({"events": [None, 42, "x"]}) == [] or all(
        e.quotes == () for e in parse_player_props({"events": [None, 42, "x"]})
    )


# ---- fixture provider (offline) ---------------------------------------------

def test_fixture_provider_reads_committed_sample():
    provider = FixturePropProvider(path=_SAMPLE)
    assert provider.available
    assert provider.event_props()[0].quotes
    matched = provider.props_for("Houston Astros", "Texas Rangers")
    assert any(q.player == "Jose Altuve" for q in matched)


def test_fixture_provider_bad_path_is_inert():
    provider = FixturePropProvider(path=_ROOT / "does_not_exist.json")
    assert provider.available is False
    assert provider.event_props() == []


# ---- licensed provider: governance slot -------------------------------------

def _boom_fetch(*_a, **_k):
    raise AssertionError("licensed fetch must not run while the slot is closed")


def test_licensed_provider_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DUMMY_ODDS_API_KEY", raising=False)
    monkeypatch.delenv("DUMMY_ODDS_API_ENABLED", raising=False)
    provider = LicensedPropProvider(fetch_fn=_boom_fetch)
    assert provider.available is False
    assert provider.event_props() == []           # never fetches
    assert provider.props_for("Houston Astros", "Texas Rangers") == []


def test_licensed_provider_requires_both_key_and_enable(monkeypatch):
    # api_key=None falls back to the environment; isolate from an armed
    # workstation's real key (present on the live box since Wave-9).
    monkeypatch.delenv("DUMMY_ODDS_API_KEY", raising=False)
    monkeypatch.delenv("DUMMY_ODDS_API_ENABLED", raising=False)
    # Key present but not enabled -> still inert.
    assert LicensedPropProvider(api_key="k", enabled=False, fetch_fn=_boom_fetch).available is False
    # Enabled but no key -> still inert.
    assert LicensedPropProvider(api_key=None, enabled=True, fetch_fn=_boom_fetch).available is False


def test_licensed_provider_parses_only_when_armed():
    provider = LicensedPropProvider(
        api_key="k", enabled=True,
        fetch_fn=lambda sport, key, markets: _sample_payload(),
    )
    assert provider.available is True
    quotes = provider.event_props()[0].quotes
    assert any(q.player == "Jose Altuve" for q in quotes)


def test_licensed_provider_fetch_error_fails_closed():
    def _raise(*_a, **_k):
        raise RuntimeError("network down")

    provider = LicensedPropProvider(api_key="k", enabled=True, fetch_fn=_raise)
    assert provider.event_props() == []           # armed but fetch failed -> []


# ---- challenger hook: dormant until the slot opens --------------------------

def test_prop_over_probability_from_fixture_and_dormant_licensed(monkeypatch):
    provider = FixturePropProvider(path=_SAMPLE)
    p = prop_over_probability(
        provider, home_team="Houston Astros", away_team="Texas Rangers",
        market_key="player_hits", player="Jose Altuve", point=0.5,
    )
    assert p is not None and 0.45 < p < 0.60
    # Unmatched player -> None (fail-closed).
    assert prop_over_probability(
        provider, home_team="Houston Astros", away_team="Texas Rangers",
        market_key="player_hits", player="Nobody Here", point=0.5,
    ) is None
    # Licensed provider unarmed -> challenger dormant (always None).
    monkeypatch.delenv("DUMMY_ODDS_API_KEY", raising=False)
    monkeypatch.delenv("DUMMY_ODDS_API_ENABLED", raising=False)
    dormant = LicensedPropProvider(fetch_fn=_boom_fetch)
    assert prop_over_probability(
        dormant, home_team="Houston Astros", away_team="Texas Rangers",
        market_key="player_hits", player="Jose Altuve", point=0.5,
    ) is None
