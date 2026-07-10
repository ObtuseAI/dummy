from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from autonomy.crypto_paper_twin import (
    CryptoPaperTwin,
    PaperTwinLedger,
    ResearchGenome,
    TrustSnapshot,
    compounding_proposal,
    maker_fill_witness,
    timeframe_state,
)
from autonomy.ontology import MarketView, Vertical


NOW = datetime(2026, 7, 10, 7, 15, tzinfo=timezone.utc)


def _market(asset: str) -> MarketView:
    ticker = "KXBTCD-26JUL1008-T99" if asset == "BTC" else "KXETHD-26JUL1008-T49"
    strike = 99.0 if asset == "BTC" else 49.0
    return MarketView(
        ticker=ticker,
        title=f"{asset} threshold",
        vertical=Vertical.CRYPTO,
        status="active",
        close_time=(NOW + timedelta(minutes=30)).isoformat(),
        yes_bid=40,
        yes_ask=42,
        no_bid=58,
        no_ask=60,
        volume=10_000,
        liquidity=1_000,
        raw={"strike_type": "greater", "floor_strike": strike, "cap_strike": None},
    )


def _state(asset: str) -> dict:
    spot = 100.0 if asset == "BTC" else 50.0
    minute = [spot * (1.0 + index / 100_000.0) for index in range(350)]
    hourly = [spot * (0.97 + index / 10_000.0) for index in range(350)]
    return {
        "asset": asset,
        "spot": minute[-1],
        "coinbase_spot": minute[-1],
        "kraken_spot": minute[-1] * 1.0001,
        "venue_divergence_bps": 1.0,
        "hourly_closes": hourly,
        "minute_closes": minute,
        "minute_volumes": [100.0 + index for index in range(350)],
        "book_imbalance": 0.2,
        "microprice_basis_bps": 1.5,
        "dvol": 50.0,
        "dvol_at_ms": int(NOW.timestamp() * 1000),
        "coinbase_hourly_at_s": int(NOW.timestamp()),
        "coinbase_minute_at_s": int(NOW.timestamp()),
        "coinbase_hourly_age_s": 0.0,
        "coinbase_minute_age_s": 0.0,
    }


class FakeHub:
    def __init__(self):
        self.states = {asset: _state(asset) for asset in ("BTC", "ETH")}

    def clear(self):
        return None

    def state(self, asset):
        return self.states[asset]

    def flat_spot_and_vol(self, asset):
        return float(self.states[asset]["spot"]), 0.50

    def ewma_spot_and_vol(self, asset):
        return float(self.states[asset]["spot"]), 0.50


class FakeScanner:
    def scan(self):
        return [_market("BTC"), _market("ETH")]


def _twin(tmp_path, *, now=NOW, results=None, trades=None):
    ledger = PaperTwinLedger(tmp_path / "paper.db")
    return CryptoPaperTwin(
        ledger=ledger,
        scanner=FakeScanner(),
        hub=FakeHub(),
        trust=TrustSnapshot({
            "market_prior@CRYPTO": 0.1,
            "crypto_spot_vol@CRYPTO": 8.0,
            "crypto_ewma_t@CRYPTO": 8.0,
        }),
        fetch_result=lambda ticker: (results or {}).get(ticker, {}),
        fetch_orderbook=lambda ticker: {"yes": [[41, 5]], "no": [[59, 5]]},
        fetch_trades=lambda ticker, start, end: list(trades or []),
        now_fn=lambda: now,
        proposed_genome_path=tmp_path / "missing.json",
    )


def test_parallel_paper_cycle_records_explanations_and_never_has_authority(tmp_path):
    twin = _twin(tmp_path)
    try:
        report = twin.run_cycle()
        assert report["status"] == "CYCLE_OK"
        assert report["observations_written"] == 12
        assert report["trades_opened"] >= 4
        assert set(report["lanes"]) == {"15m", "1h"}
        assert report["authority"]["independent_of_shadow_or_live_session"] is True
        assert report["authority"]["continues_during_authorized_live_operation"] is True
        assert report["authority"]["execution_authority"] is False
        assert report["authority"]["capital_authority"] is False
        assert report["evidence_quarantine"]["counts_toward_canary"] is False
        assert report["phase_2_forward_selection"]["candidate_gates"]["15m"]["recursive"][
            "auto_apply"
        ] is False
        assert any(
            "diagnostic-only" in blocker
            for blocker in report["phase_2_forward_selection"]["candidate_gates"]["15m"][
                "exploratory"
            ]["blockers"]
        )
        assert report["phase_3_execution"]["policy_challengers"]["execution_authority"] is False
        explanations = report["recent_explanations"]
        assert explanations
        assert all("Paper-only" in row["explanation"] or "No paper order" in row["explanation"]
                   for row in explanations)
    finally:
        twin.close()


def test_same_lane_never_pyramids_same_asset_expiry(tmp_path):
    twin = _twin(tmp_path)
    try:
        first = twin.run_cycle()
        first_count = first["trades_opened"]
        second = twin.run_cycle()
        assert first_count > 0
        assert second["trades_opened"] == 0
        assert second["observations_written"] == 12
    finally:
        twin.close()


def test_settlement_uses_simulated_taker_quote_and_keeps_paper_quarantined(tmp_path):
    first = _twin(tmp_path)
    try:
        report = first.run_cycle()
        assert report["trades_opened"] > 0
    finally:
        first.close()
    results = {
        _market("BTC").ticker: {"result": "yes"},
        _market("ETH").ticker: {"result": "yes"},
    }
    second = _twin(tmp_path, now=NOW + timedelta(hours=1), results=results)
    try:
        report = second.run_cycle()
        assert report["settlements_recorded"] > 0
        settled = sum(
            lane[strategy]["settled_trades"]
            for lane in report["lanes"].values()
            for strategy in ("incumbent", "recursive", "exploratory")
        )
        assert settled > 0
        assert report["phase_4_canary_decision"]["live_canary_ready"] is False
    finally:
        second.close()


def test_maker_fill_requires_public_trade_through_or_queue_consumption():
    order = {
        "side": "yes",
        "maker_price_cents": 41,
        "maker_queue_ahead": 5.0,
        "maker_queue_snapshot": 1,
        "created_at": NOW.isoformat(),
        "maker_expires_at": (NOW + timedelta(minutes=1)).isoformat(),
    }
    no_fill = maker_fill_witness(order, [{
        "taker_book_side": "ask",
        "yes_price_dollars": "0.41",
        "count_fp": "5",
        "created_time": (NOW + timedelta(seconds=30)).isoformat(),
    }])
    assert no_fill is None
    fill = maker_fill_witness(order, [{
        "taker_book_side": "ask",
        "yes_price_dollars": "0.40",
        "count_fp": "1",
        "trade_id": "public-1",
        "created_time": (NOW + timedelta(seconds=30)).isoformat(),
    }])
    assert fill["reason"] == "public_trade_through"


def test_later_cycle_reconciles_maker_lane_from_public_prints(tmp_path):
    first = _twin(tmp_path)
    try:
        opened = first.run_cycle()
        assert opened["trades_opened"] > 0
    finally:
        first.close()
    public_print = {
        "taker_book_side": "ask",
        "yes_price_dollars": "0.40",
        "no_price_dollars": "0.58",
        "count_fp": "20",
        "trade_id": "public-through",
        "created_time": (NOW + timedelta(seconds=30)).isoformat(),
    }
    second = _twin(tmp_path, now=NOW + timedelta(minutes=2), trades=[public_print])
    try:
        report = second.run_cycle()
        assert report["maker_updates"] > 0
        maker_fills = sum(
            lane[strategy]["maker_fills"]
            for lane in report["lanes"].values()
            for strategy in ("incumbent", "recursive", "exploratory")
        )
        assert maker_fills > 0
    finally:
        second.close()


def test_timeframe_inputs_are_distinct_and_recursive_epoch_is_frozen(tmp_path):
    state = _state("BTC")
    fast = timeframe_state(state, "15m")
    hourly = timeframe_state(state, "1h")
    assert fast["minute_closes"]
    assert hourly["minute_closes"] == []

    ledger = PaperTwinLedger(tmp_path / "paper.db")
    try:
        first = ledger.ensure_epoch(
            ResearchGenome(0.75, 8, 0.25, 75), now=NOW,
        )
        second = ledger.ensure_epoch(
            ResearchGenome(0.50, 12, 0.18, 65), now=NOW + timedelta(hours=1),
        )
        assert second["epoch_id"] == first["epoch_id"]
        assert json.loads(second["genome_json"])["shrinkage"] == 0.75
    finally:
        ledger.close()


def test_compounding_and_canary_outputs_never_grant_live_authority():
    proposal = compounding_proposal([])
    assert proposal["capital_authority"] is False
    assert proposal["live_application"] is False
