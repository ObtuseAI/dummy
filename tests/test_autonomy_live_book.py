"""Tests for the WS live-book state machine + pre-submit quote guard."""

from __future__ import annotations

import asyncio
import json

from autonomy.live_book import BookState, KalshiLiveBook, apply_frame, fresh_best_quote


def test_snapshot_sets_best_levels():
    book = BookState("T")
    book.apply_snapshot({"yes": [[30, 100], [31, 50]], "no": [[62, 80], [61, 40]]})
    assert book.best_yes_bid() == 31
    assert book.best_no_bid() == 62
    assert book.best_yes_ask() == 100 - 62  # 38
    assert book.best_no_ask() == 100 - 31  # 69


def test_delta_add_and_remove_level():
    book = BookState("T")
    book.apply_snapshot({"yes": [[30, 100]], "no": [[60, 50]]})
    book.apply_delta({"side": "yes", "price": 32, "delta": 20})
    assert book.best_yes_bid() == 32
    book.apply_delta({"side": "yes", "price": 32, "delta": -20})  # level cleared
    assert book.best_yes_bid() == 30


def test_delta_unknown_side_ignored():
    book = BookState("T")
    book.apply_snapshot({"yes": [[30, 100]], "no": []})
    book.apply_delta({"side": "bogus", "price": 40, "delta": 10})
    assert book.best_yes_bid() == 30


def test_apply_frame_routes_by_type_and_ticker():
    books: dict[str, BookState] = {}
    apply_frame(books, {"type": "orderbook_snapshot", "msg": {"market_ticker": "A", "yes": [[30, 10]], "no": [[60, 10]]}})
    apply_frame(books, {"type": "orderbook_delta", "msg": {"market_ticker": "A", "side": "yes", "price": 35, "delta": 5}})
    apply_frame(books, {"type": "noise", "msg": {"market_ticker": "A"}})
    assert books["A"].best_yes_bid() == 35


def test_apply_frame_ignores_missing_ticker():
    books: dict[str, BookState] = {}
    apply_frame(books, {"type": "orderbook_snapshot", "msg": {"yes": [[1, 1]]}})
    assert books == {}


def test_live_book_consumes_mock_socket_frames():
    frames = [
        json.dumps({"type": "orderbook_snapshot", "msg": {"market_ticker": "A", "yes": [[40, 100]], "no": [[55, 100]]}}),
        json.dumps({"type": "orderbook_delta", "msg": {"market_ticker": "A", "side": "no", "price": 58, "delta": 20}}),
    ]

    class FakeWs:
        def __init__(self):
            self.sent = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def send(self, m):
            self.sent.append(m)

        def __aiter__(self):
            self._it = iter(frames)
            return self

        async def __anext__(self):
            try:
                return next(self._it)
            except StopIteration:
                raise StopAsyncIteration

    def connect(url, additional_headers=None):
        return FakeWs()

    book = KalshiLiveBook(connect_fn=connect)
    # sign_ws_headers needs creds; bypass by monkeypatching via env-free path:
    import autonomy.live_book as lb

    orig = lb.sign_ws_headers
    lb.sign_ws_headers = lambda: {}
    try:
        asyncio.run(book.run(["A"], max_frames=2))
    finally:
        lb.sign_ws_headers = orig
    quote = book.quote("A")
    assert quote["yes_bid"] == 40
    assert quote["yes_ask"] == 100 - 58  # best no bid moved to 58


def test_fresh_best_quote_from_rest():
    quote = fresh_best_quote("T", fetch_orderbook=lambda t: {"yes": [[30, 100]], "no": [[62, 50]]})
    assert quote["yes_bid"] == 30
    assert quote["yes_ask"] == 38


def test_fresh_best_quote_swallows_error():
    def boom(t):
        raise RuntimeError("down")

    assert fresh_best_quote("T", fetch_orderbook=boom) is None


# ---------------------------------------------------------------- executor guard


def test_executor_skips_crossed_maker_quote(tmp_path):
    import json as _json
    from datetime import datetime, timedelta, timezone

    from autonomy.allocator import Allocator
    from autonomy.executor import AUTONOMY_ACK, Executor
    from autonomy.ontology import Forecast, MarketView, OutcomeKind, SessionMode, Vertical
    from autonomy.risk_brain import RiskBrain

    session = tmp_path / "s.json"
    session.write_text(_json.dumps({
        "mode": "LIVE", "ack": AUTONOMY_ACK,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }), encoding="utf-8")

    brain = RiskBrain(state_path=tmp_path / "risk.json")
    state = brain.load_state(100_000)
    market = MarketView(ticker="T", title="", vertical=Vertical.CRYPTO, status="active",
                        close_time=(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
                        yes_bid=30, yes_ask=40, no_bid=60, no_ask=70, volume=100, liquidity=100)
    forecast = Forecast(market_ticker="T", probability_yes=0.7, uncertainty=0.08,
                        sources_used={}, market_implied_yes=0.35, edge_yes=0.35, rationale="")
    decision = Allocator(brain).decide(market, forecast, state)
    assert decision.side == "yes"

    # Book moved: yes_ask now at/below our resting price -> we'd cross.
    crossed = lambda t: {"yes_bid": decision.price_cents, "yes_ask": decision.price_cents}
    executor = Executor(SessionMode.LIVE, session_path=session, kill_path=tmp_path / "KILL", quote_fn=crossed)
    outcome = asyncio.run(executor.execute(decision))
    assert outcome.kind is OutcomeKind.BLOCKED_LOCAL
    assert "crossed" in outcome.detail["reason"]
