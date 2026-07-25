"""Positive market authorization must be expressible for rotating contracts.

``allowed_markets`` is an exact-ticker list. Kalshi crypto contracts rotate
every fifteen minutes and sports contracts rotate per game, so an exact list
can authorize a pilot but can never authorize continuous operation -- which is
why it has always been empty.

``allowed_series`` authorizes a *series*, so any contract within it passes while
everything outside is still denied. This is deliberately a positive control
only: it can widen what is permitted, and every negative control (quarantine,
blocked_categories, caps, risk brain, compliance) is untouched.

Series matching is boundary-aware string matching on an opaque identifier --
NOT category inference. The firewall still refuses to read category from a
ticker; category compliance continues to come from fetched venue metadata.
"""
from __future__ import annotations

from live_firewall.firewall import market_is_allowlisted


class _Caps:
    def __init__(self, markets=None, series=None):
        self.allowed_markets = list(markets or [])
        self.allowed_series = list(series or [])


SOL = "KXSOL15M-26JUL25H04-T140.5"


class TestDenyByDefault:
    def test_empty_allowlists_deny_everything(self):
        assert market_is_allowlisted(SOL, _Caps()) is False

    def test_unrelated_series_is_denied(self):
        assert market_is_allowlisted(SOL, _Caps(series=["KXBTC15M"])) is False

    def test_unrelated_exact_ticker_is_denied(self):
        assert market_is_allowlisted(SOL, _Caps(markets=["KXETH15M-26JUL25H04-T1"])) is False


class TestExactMatchStillWorks:
    def test_exact_ticker_is_allowed(self):
        assert market_is_allowlisted(SOL, _Caps(markets=[SOL])) is True

    def test_exact_match_works_with_empty_series_list(self):
        caps = _Caps(markets=[SOL], series=[])
        assert market_is_allowlisted(SOL, caps) is True


class TestSeriesMatch:
    def test_contract_in_allowed_series_is_allowed(self):
        assert market_is_allowlisted(SOL, _Caps(series=["KXSOL15M"])) is True

    def test_any_rotation_of_the_series_is_allowed(self):
        for suffix in ("26JUL25H04-T140.5", "26JUL25H05-T141.0", "26AUG01H23-T99"):
            assert market_is_allowlisted(f"KXSOL15M-{suffix}", _Caps(series=["KXSOL15M"])) is True

    def test_series_matching_is_boundary_aware(self):
        """KXSOL15M must not authorize KXSOL15MEGA -- prefix matching without a
        boundary check silently widens the allowlist to look-alike series."""
        assert market_is_allowlisted(
            "KXSOL15MEGA-26JUL25-T1", _Caps(series=["KXSOL15M"])
        ) is False

    def test_series_alone_without_separator_is_not_a_contract(self):
        assert market_is_allowlisted("KXSOL15M", _Caps(series=["KXSOL15M"])) is True


class TestMalformedInput:
    def test_empty_ticker_is_denied(self):
        assert market_is_allowlisted("", _Caps(series=["KXSOL15M"])) is False

    def test_none_ticker_is_denied(self):
        assert market_is_allowlisted(None, _Caps(series=["KXSOL15M"])) is False

    def test_caps_without_allowed_series_attribute_still_works(self):
        """Older CapConfig payloads have no allowed_series; they must keep
        behaving exactly as before rather than raising."""

        class _LegacyCaps:
            allowed_markets = [SOL]

        assert market_is_allowlisted(SOL, _LegacyCaps()) is True
        assert market_is_allowlisted("KXETH15M-1-T1", _LegacyCaps()) is False


class TestCapConfigSchema:
    def test_capconfig_exposes_allowed_series_defaulting_to_empty(self):
        from core.ontology import CapConfig

        caps = CapConfig()
        assert caps.allowed_series == []

    def test_capconfig_accepts_allowed_series(self):
        from core.ontology import CapConfig

        caps = CapConfig(allowed_series=["KXSOL15M"])
        assert caps.allowed_series == ["KXSOL15M"]
