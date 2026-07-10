from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from autonomy.crypto_paper_twin import (
    COHORTS,
    CryptoPaperTwin,
    PaperTwinLedger,
    ResearchGenome,
    TrustSnapshot,
    bucket_start,
    cohort_for_market,
    cohort_for_ticker,
    compounding_proposal,
    market_listing_duration_hours,
    maker_fill_witness,
    timeframe_state,
)
from autonomy.ontology import MarketView, Vertical
from autonomy.signals.commodities_spot import CommoditiesSpotVolSignal


NOW = datetime(2026, 7, 10, 7, 15, tzinfo=timezone.utc)


def _market(asset: str, timeframe: str = "1h") -> MarketView:
    strike = {"BTC": 99.0, "ETH": 49.0, "SOL": 24.0}[asset]
    if timeframe == "15m":
        ticker = f"KX{asset}15M-26JUL100730-00"
        close_time = NOW + timedelta(minutes=15)
        open_time = NOW
        strike_type = "greater_or_equal"
    else:
        series = {"BTC": "KXBTCD", "ETH": "KXETHD", "SOL": "KXSOLD"}[asset]
        if timeframe == "1h":
            ticker = f"{series}-26JUL1008-T{strike:g}"
            close_time = NOW + timedelta(minutes=30)
            open_time = close_time - timedelta(hours=1)
        elif timeframe == "1d":
            ticker = f"{series}-26JUL1117-T{strike:g}"
            close_time = NOW + timedelta(days=1)
            open_time = close_time - timedelta(hours=24)
        elif timeframe == "1w":
            ticker = f"{series}-26JUL1717-T{strike:g}"
            close_time = NOW + timedelta(days=5)
            open_time = close_time - timedelta(days=7)
        else:
            raise ValueError(timeframe)
        strike_type = "greater"
    return MarketView(
        ticker=ticker,
        title=f"{asset} {timeframe} threshold",
        vertical=Vertical.CRYPTO,
        status="active",
        close_time=close_time.isoformat(),
        yes_bid=40,
        yes_ask=42,
        no_bid=58,
        no_ask=60,
        volume=10_000,
        liquidity=1_000,
        raw={
            "strike_type": strike_type,
            "floor_strike": strike,
            "cap_strike": None,
            "open_time": open_time.isoformat(),
        },
    )


def _state(asset: str) -> dict:
    spot = {"BTC": 100.0, "ETH": 50.0, "SOL": 25.0}[asset]
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


def _commodity_market(asset: str, timeframe: str) -> MarketView:
    series = {
        ("WTI", "1d"): "KXWTI",
        ("NATGAS", "1d"): "KXNATGASD",
        ("GOLD", "1d"): "KXGOLDD",
        ("WTI", "1w"): "KXWTIW",
        ("NATGAS", "1w"): "KXNATGASW",
        ("GOLD", "1w"): "KXGOLDW",
    }[(asset, timeframe)]
    strike = {"WTI": 79.0, "NATGAS": 3.0, "GOLD": 4_500.0}[asset]
    close = NOW + timedelta(days=2 if timeframe == "1d" else 5)
    return MarketView(
        ticker=f"{series}-26JUL15-T{strike:g}",
        title=f"{asset} {timeframe} threshold",
        vertical=Vertical.COMMODITIES,
        status="active",
        close_time=close.isoformat(),
        yes_bid=40,
        yes_ask=42,
        no_bid=58,
        no_ask=60,
        volume=10_000,
        liquidity=1_000,
        raw={"strike_type": "greater", "floor_strike": strike},
    )


class FakeHub:
    def __init__(self):
        self.states = {asset: _state(asset) for asset in ("BTC", "ETH", "SOL")}

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
        crypto = [
            _market(asset, timeframe)
            for timeframe in ("15m", "1h", "1d", "1w")
            for asset in ("BTC", "ETH", "SOL")
        ]
        commodities = [
            _commodity_market(asset, timeframe)
            for timeframe in ("1d", "1w")
            for asset in ("WTI", "NATGAS", "GOLD")
        ]
        return crypto + commodities


def _twin(tmp_path, *, now=NOW, results=None, trades=None):
    ledger = PaperTwinLedger(tmp_path / "paper.db")
    return CryptoPaperTwin(
        ledger=ledger,
        scanner=FakeScanner(),
        hub=FakeHub(),
        commodity_signal=CommoditiesSpotVolSignal(
            fetch_spot_and_vol=lambda symbol: {
                "CL=F": (80.0, 0.35),
                "NG=F": (3.2, 0.45),
                "GC=F": (4_600.0, 0.25),
            }[symbol],
        ),
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
        assert report["observations_written"] == 54
        assert report["trades_opened"] >= 6
        assert set(report["lanes"]) == {"15m", "1h", "1d", "1w"}
        assert set(report["cohorts"]) == {"CRYPTO", "COMMODITIES"}
        assert set(report["cohorts"]["COMMODITIES"]) == {"1d", "1w"}
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
        routed = {
            (row["timeframe"], row["asset"], row["ticker"])
            for row in twin.ledger.connection.execute(
                "SELECT timeframe,asset,ticker FROM observations "
                "WHERE vertical='CRYPTO' AND ticker IS NOT NULL"
            )
        }
        assert {asset for _timeframe, asset, _ticker in routed} == {"BTC", "ETH", "SOL"}
        assert all("15M-" in ticker for timeframe, _asset, ticker in routed if timeframe == "15m")
        assert all("15M-" not in ticker for timeframe, _asset, ticker in routed if timeframe == "1h")
        weekly_routed = twin.ledger.connection.execute(
            "SELECT COUNT(*) FROM observations WHERE vertical='CRYPTO' "
            "AND timeframe='1w' AND ticker IS NOT NULL"
        ).fetchone()[0]
        assert weekly_routed == 9
        commodity_observations = twin.ledger.connection.execute(
            "SELECT COUNT(*) FROM observations WHERE vertical='COMMODITIES' "
            "AND timeframe IN ('1d','1w') AND ticker IS NOT NULL"
        ).fetchone()[0]
        assert commodity_observations == 18
        assert report["phase_4_canary_decision"]["gates_by_vertical"][
            "COMMODITIES"
        ]["1d"]["incumbent"]["live_canary_ready"] is False
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
        assert second["observations_written"] == 54
    finally:
        twin.close()


def test_legacy_hourly_contracts_are_preserved_outside_native_15m_cohort(tmp_path):
    twin = _twin(tmp_path)
    try:
        twin.run_cycle()
        twin.ledger.connection.execute(
            "UPDATE observations SET ticker='KXBTCD-26JUL1008-T99' "
            "WHERE timeframe='15m' AND ticker IS NOT NULL"
        )
        twin.ledger.connection.execute(
            "UPDATE trades SET ticker='KXBTCD-26JUL1008-T99' WHERE timeframe='15m'"
        )
        twin.ledger.connection.commit()
    finally:
        twin.close()

    ledger = PaperTwinLedger(tmp_path / "paper.db")
    try:
        quarantine = ledger.legacy_quarantine_summary()
        assert quarantine["observations"] > 0
        assert quarantine["trades"] > 0
        assert ledger.lane_summary("exploratory", "15m")["trades"] == 0
    finally:
        ledger.close()


def test_settlement_uses_simulated_taker_quote_and_keeps_paper_quarantined(tmp_path):
    first = _twin(tmp_path)
    try:
        report = first.run_cycle()
        assert report["trades_opened"] > 0
    finally:
        first.close()
    results = {
        _market(asset, timeframe).ticker: {"result": "yes"}
        for timeframe in ("15m", "1h", "1d", "1w")
        for asset in ("BTC", "ETH", "SOL")
    }
    results.update({
        _commodity_market(asset, timeframe).ticker: {"result": "yes"}
        for timeframe in ("1d", "1w")
        for asset in ("WTI", "NATGAS", "GOLD")
    })
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


def test_native_15m_keeps_final_four_minutes_while_hourly_retains_cutoff(tmp_path):
    twin = _twin(tmp_path)
    try:
        native = replace(
            _market("BTC", "15m"),
            close_time=(NOW + timedelta(minutes=4)).isoformat(),
        )
        hourly = replace(
            _market("BTC", "1h"),
            close_time=(NOW + timedelta(minutes=4)).isoformat(),
        )
        assert twin._markets_for_asset([native], "BTC", "15m", NOW) == [native]
        assert twin._markets_for_asset([hourly], "BTC", "1h", NOW) == []
    finally:
        twin.close()


def test_exact_crypto_and_commodity_horizon_allowlist():
    crypto = {
        (cohort.asset, cohort.timeframe)
        for cohort in COHORTS if cohort.vertical is Vertical.CRYPTO
    }
    commodities = {
        (cohort.asset, cohort.timeframe)
        for cohort in COHORTS if cohort.vertical is Vertical.COMMODITIES
    }
    assert crypto == {
        (asset, timeframe)
        for asset in ("BTC", "ETH", "SOL")
        for timeframe in ("15m", "1h", "1d", "1w")
    }
    assert commodities == {
        (asset, timeframe)
        for asset in ("WTI", "NATGAS", "GOLD")
        for timeframe in ("1d", "1w")
    }
    assert cohort_for_ticker("KXDOGE15M-26JUL100430-30") is None
    assert cohort_for_ticker("KXBTCMAXW-26JUL10-T80000") is None
    assert cohort_for_ticker("KXBTCD-26JUL1017-T63999.99") is None
    assert cohort_for_ticker("KXWTIW-26JUL1014-T75.99").asset == "WTI"
    assert cohort_for_market(_market("BTC", "1h")).timeframe == "1h"
    assert cohort_for_market(_market("BTC", "1d")).timeframe == "1d"
    assert cohort_for_market(_market("BTC", "1w")).timeframe == "1w"
    monday = datetime(2026, 7, 6, tzinfo=timezone.utc)
    assert bucket_start(NOW, "1w") == monday.isoformat()


def test_kalshi_weekly_btc_listing_is_routed_from_event_duration():
    market = MarketView(
        ticker="KXBTCD-26JUL1017-T63999.99",
        title="Bitcoin price on Jul 10, 2026?",
        vertical=Vertical.CRYPTO,
        status="active",
        close_time="2026-07-10T21:00:00+00:00",
        yes_bid=55,
        yes_ask=57,
        no_bid=43,
        no_ask=45,
        volume=3_250_909,
        liquidity=1_000,
        raw={
            "open_time": "2026-07-03T20:00:00Z",
            "strike_type": "greater",
            "floor_strike": 63_999.99,
            "cap_strike": None,
        },
    )

    assert market_listing_duration_hours(market) == 169.0
    assert cohort_for_market(market).timeframe == "1w"


def test_compounding_and_canary_outputs_never_grant_live_authority():
    proposal = compounding_proposal([])
    assert proposal["capital_authority"] is False
    assert proposal["live_application"] is False
