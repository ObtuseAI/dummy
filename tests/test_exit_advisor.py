from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from autonomy.exit_advisor import advise_exit, write_exit_advisory_artifact
from autonomy.ontology import Forecast, MarketView, Vertical


def _market(yes_bid=60, no_bid=39):
    return MarketView(
        ticker="KXTEST-EXIT", title="Exit test", vertical=Vertical.OTHER,
        status="active",
        close_time=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        yes_bid=yes_bid, yes_ask=61, no_bid=no_bid, no_ask=40,
        volume=100, liquidity=100,
        raw={"yes_bid_size": 10, "no_bid_size": 10},
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )


def _forecast(p_yes, uncertainty=0.05):
    return Forecast(
        market_ticker="KXTEST-EXIT", probability_yes=p_yes,
        uncertainty=uncertainty, sources_used={"s": 1.0},
        market_implied_yes=0.60, edge_yes=p_yes - 0.60, rationale="test",
    )


def _position(filled=2):
    return {
        "decision_id": "d1", "market_ticker": "KXTEST-EXIT", "side": "yes",
        "price_cents": 40, "fill_price_cents": 40,
        "count": 2, "filled_count": filled, "order_active": False,
        "liquidity_role": "maker", "execution_fee_cents": 0,
        "fill_cost_cents": 40 * filled,
    }


def test_exit_requires_executable_value_above_uncertainty_adjusted_hold():
    advisory = advise_exit(_position(), _market(), _forecast(0.20))
    assert advisory is not None
    assert advisory.action == "EXIT"
    assert advisory.exit_advantage_cents >= 3.0
    signal = advisory.to_signal()
    assert signal.source == "exit_advisor_shadow"
    assert signal.features["observational_only"] is True
    assert signal.features["action"] == "EXIT"
    assert signal.features["policy_evidence_only"] is True
    assert signal.features["probability_authority"] is False
    assert signal.features["challenger_only"] is True
    assert signal.features["promotion_eligible"] is False
    assert signal.features["exit_quote_fresh"] is True
    assert signal.features["exit_depth_verified"] is True
    assert signal.features["entry_cost_source"] == "witnessed_fill_cost"


def test_exit_advisor_holds_when_forecast_still_supports_position():
    advisory = advise_exit(_position(), _market(), _forecast(0.80))
    assert advisory is not None
    assert advisory.action == "HOLD"


def test_exit_advisor_ignores_unfilled_reservations():
    assert advise_exit(_position(filled=0), _market(), _forecast(0.20)) is None


def test_exit_advisor_holds_while_entry_remainder_is_active():
    position = _position(filled=1)
    position["order_active"] = True
    advisory = advise_exit(position, _market(), _forecast(0.20))
    assert advisory is not None
    assert advisory.action == "HOLD"
    assert advisory.reason == "entry order remains active"


def test_exit_advisor_holds_on_unverifiable_quote_freshness():
    market = _market()
    object.__setattr__(market, "fetched_at", None)
    advisory = advise_exit(_position(), market, _forecast(0.20))
    assert advisory is not None
    assert advisory.action == "HOLD"
    assert advisory.exit_quote_fresh is False
    assert advisory.reason == "exit quote freshness is unverified"


def test_exit_advisor_rejects_future_or_timezone_naive_quotes():
    now = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
    for observed_at in (
        (now + timedelta(seconds=1)).isoformat(),
        "2026-07-22T11:59:30",
    ):
        market = _market()
        object.__setattr__(market, "fetched_at", observed_at)
        advisory = advise_exit(_position(), market, _forecast(0.20), now=now)
        assert advisory is not None
        assert advisory.action == "HOLD"
        assert advisory.exit_quote_fresh is False
        assert advisory.exit_quote_age_seconds is None
        assert advisory.reason == "exit quote freshness is unverified"


def test_exit_artifact_is_explicitly_non_live(tmp_path):
    path = tmp_path / "exit.json"
    rows = write_exit_advisory_artifact(
        [_position()], [(_market(), _forecast(0.20))], path,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert rows[0].action == "EXIT"
    assert payload["mode"] == "shadow_advisory_only"
    assert payload["live_execution_enabled"] is False
    assert payload["quote_semantics"] == "displayed_bid_not_a_fill"
    assert payload["depth_required_for_execution_claim"] is True
    assert payload["depth_verified_exit_count"] == 1
