"""Wave-78: the independent model view.

Every non-winner market on the board echoed the market price because the
promotion ladder filters unpromoted ``challenger_only`` signals out of the
traded number. The model view is a SECOND fusion over the challenger-inclusive
set (market_prior excluded) that surfaces what our own models believe about
both sides of every market, without touching the traded number or any gate.
"""
from __future__ import annotations

import datetime
import tempfile
from pathlib import Path

from autonomy.forecaster import EnsembleForecaster
from autonomy.market_labels import model_view_fields
from autonomy.ontology import Forecast, MarketView, Signal, Vertical


class _StubLedger:
    def get_weight(self, source, default=1.0):
        return default


class _StubPromotion:
    """No challenger is ever promoted -- the worst case for market echo."""

    def is_promoted_signal(self, *args, **kwargs):
        return False

    def weight_multiplier_for_signal(self, *args, **kwargs):
        return 1.0


def _forecaster() -> EnsembleForecaster:
    # Exercise the public constructor and make this unit fixture's evidence
    # assumption explicit. Bypassing ``__init__`` omitted the no-edge trust
    # disposition and no longer represents a constructible production object.
    return EnsembleForecaster(
        _StubLedger(),
        promotion=_StubPromotion(),
        negative_scopes=frozenset(),
    )


def _market(ticker: str = "KXMLBTOTAL-26JUL242010COLMIL-8") -> MarketView:
    return MarketView(
        ticker=ticker, title="COL vs MIL Total", vertical=Vertical.SPORTS,
        status="active", close_time=None, yes_bid=55, yes_ask=60, no_bid=40,
        no_ask=45, volume=10, liquidity=10, tick_size=1, raw={"floor_strike": 8.5},
        fetched_at=datetime.datetime.now(datetime.timezone.utc),
    )


def _sig(source, prob, unc, *, challenger):
    return Signal(
        source=source, market_ticker="KXMLBTOTAL-26JUL242010COLMIL-8",
        probability_yes=prob, uncertainty=unc, rationale="",
        features={"challenger_only": True} if challenger else {},
    )


def test_traded_number_still_echoes_market_but_model_view_diverges():
    """A hidden challenger cannot move the traded number, but the model view
    shows its independent read."""
    f = _forecaster()
    m = _market()
    prior = _sig("market_prior", 0.58, 0.03, challenger=False)
    challenger = _sig("mlb_total_runs", 0.42, 0.12, challenger=True)
    fc = f.fuse(m, [prior, challenger])
    # Traded number = market echo (the challenger is filtered out).
    assert abs(fc.probability_yes - 0.58) < 1e-9
    # Model view = the challenger's independent read (market_prior excluded).
    assert fc.model_probability_yes is not None
    assert abs(fc.model_probability_yes - 0.42) < 1e-9
    assert fc.model_sources and "market_prior" not in fc.model_sources


def test_no_model_view_when_only_market_prior():
    f = _forecaster()
    fc = f.fuse(_market(), [_sig("market_prior", 0.58, 0.03, challenger=False)])
    assert fc.model_probability_yes is None
    assert fc.model_sources is None


def test_promoted_challenger_appears_in_both_traded_and_model_view():
    """A promoted challenger moves the traded number AND shows a model view."""
    class Promoted(_StubPromotion):
        def is_promoted_signal(self, source, *a, **k):
            return source == "mlb_total_runs"

    f = _forecaster()
    f.promotion = Promoted()
    m = _market()
    fc = f.fuse(m, [
        _sig("market_prior", 0.58, 0.03, challenger=False),
        _sig("mlb_total_runs", 0.42, 0.12, challenger=True),
    ])
    # Promoted -> it now influences the traded number (no longer pure echo).
    assert fc.probability_yes < 0.58
    # And the model view still shows the pure model consensus.
    assert fc.model_probability_yes is not None


def test_model_view_fields_side_is_yes_when_model_richer_than_market():
    out = model_view_fields("KXMLBTOTAL-26JUL242010COLMIL-8", 0.62, 0.50, {"s": 1.0})
    assert out["has_independent_model"] is True
    assert out["model_side"] == "yes"
    assert out["model_edge"] == 0.12
    assert out["model_recommendation"] is not None


def test_model_view_fields_side_is_no_when_model_cheaper_than_market():
    out = model_view_fields("KXMLBTOTAL-26JUL242010COLMIL-8", 0.38, 0.50, {"s": 1.0})
    assert out["model_side"] == "no"
    assert out["model_edge"] == -0.12


def test_model_view_fields_blank_when_no_model():
    out = model_view_fields("KXMLBTOTAL-26JUL242010COLMIL-8", None, 0.50, None)
    assert out["has_independent_model"] is False
    assert out["model_probability"] is None
    assert out["model_recommendation"] is None


def test_yrfi_model_recommendation_reads_as_yes_no():
    """The both-sides call on a first-inning-run market is unambiguous NRFI/YRFI."""
    yes = model_view_fields("KXMLBRFI-26JUL242010COLMIL", 0.60, 0.45, {"s": 1.0})
    no = model_view_fields("KXMLBRFI-26JUL242010COLMIL", 0.30, 0.45, {"s": 1.0})
    assert "1st" in (yes["model_recommendation"] or "")
    assert "NRFI" in (no["model_recommendation"] or "")


def test_board_artifact_carries_model_view():
    from autonomy.bet_board import write_board_artifact

    m = _market()
    fc = Forecast(
        market_ticker=m.ticker, probability_yes=0.58, uncertainty=0.05,
        sources_used={"market_prior": 1.0}, market_implied_yes=0.575,
        edge_yes=0.005, rationale="fused", model_probability_yes=0.42,
        model_uncertainty=0.12, model_sources={"mlb_total_runs": 1.0},
    )
    tmp = Path(tempfile.mkdtemp()) / "board.json"
    payload = write_board_artifact([(m, fc)], path=tmp)
    row = payload["groups"]["mlb"]["total"][0]
    assert row["model_probability"] == 0.42
    assert row["model_edge"] == -0.155
    assert row["model_side"] == "no"
    assert row["has_independent_model"] is True
    assert row["model_recommendation"] is not None
