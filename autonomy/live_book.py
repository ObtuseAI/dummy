"""Signed Kalshi WebSocket live orderbook + pre-submit quote refresh.

Two capabilities:
1. `KalshiLiveBook` — an async client that authenticates with the same
   RSA-PSS scheme as REST, subscribes to `orderbook_delta`, and maintains a
   live per-ticker book from snapshot + delta frames. Frame application is
   pure/synchronous so it is fully testable without a socket.
2. `fresh_best_quote` — a synchronous REST fallback the executor calls right
   before submit to re-derive maker prices from the freshest book, so a
   resting quote is never priced off a stale scan.

Read/subscribe only; never sends order commands over the socket.
"""
from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from typing import Any, Callable

WS_PATH = "/trade-api/ws/v2"


def _ws_url() -> str:
    base = os.environ.get("KALSHI_API_BASE", "https://api.elections.kalshi.com")
    host = base.split("//", 1)[-1].rstrip("/")
    return f"wss://{host}{WS_PATH}"


def sign_ws_headers() -> dict[str, str]:
    """Signed headers for the WS handshake (message = {ts}GET{WS_PATH})."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    from kalshi.signer import load_private_key

    key_id = os.environ.get("KALSHI_API_KEY_ID", "")
    if not key_id:
        raise RuntimeError("KALSHI_API_KEY_ID not set")
    ts = str(int(datetime.now(timezone.utc).timestamp() * 1000))
    message = f"{ts}GET{WS_PATH}"
    signature = load_private_key().sign(
        message.encode("utf-8"),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )
    return {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode(),
        "KALSHI-ACCESS-TIMESTAMP": ts,
    }


class BookState:
    """One market's book. yes[] / no[] map price(cents) -> resting count.

    Kalshi encodes both sides as bids: a `yes` level is a bid to buy YES at
    that price; a `no` level is a bid to buy NO. The YES ask is therefore
    100 - best NO bid.
    """

    def __init__(self, ticker: str) -> None:
        self.ticker = ticker
        self.yes: dict[int, float] = {}
        self.no: dict[int, float] = {}
        self.seq: int | None = None
        self.updated_at: str | None = None

    @staticmethod
    def _aggregate_levels(raw: Any) -> dict[int, float]:
        """Aggregate duplicate price levels instead of silently overwriting."""
        levels: dict[int, float] = {}
        for item in raw or []:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            try:
                price = int(item[0])
                count = float(item[1])
            except (TypeError, ValueError):
                continue
            if not 1 <= price <= 99 or count <= 0:
                continue
            levels[price] = levels.get(price, 0.0) + count
        return levels

    def apply_snapshot(self, msg: dict[str, Any]) -> None:
        self.yes = self._aggregate_levels(msg.get("yes", []))
        self.no = self._aggregate_levels(msg.get("no", []))
        self.seq = msg.get("seq")
        self._stamp()

    def apply_delta(self, msg: dict[str, Any]) -> None:
        side = msg.get("side")
        price = int(msg.get("price"))
        delta = float(msg.get("delta", 0))
        book = self.yes if side == "yes" else self.no if side == "no" else None
        if book is None:
            return
        book[price] = book.get(price, 0) + delta
        if book[price] <= 0:
            book.pop(price, None)
        self.seq = msg.get("seq", self.seq)
        self._stamp()

    def _stamp(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def best_yes_bid(self) -> int | None:
        return max(self.yes) if self.yes else None

    def best_yes_ask(self) -> int | None:
        # Best YES ask is derived from the best NO bid.
        return (100 - max(self.no)) if self.no else None

    def best_no_bid(self) -> int | None:
        return max(self.no) if self.no else None

    def best_no_ask(self) -> int | None:
        return (100 - max(self.yes)) if self.yes else None

    def quote(self) -> dict[str, Any]:
        yes_bid = self.best_yes_bid()
        no_bid = self.best_no_bid()
        # Kalshi publishes YES and NO bids. Buying YES consumes NO bids at
        # complement prices; buying NO consumes YES bids. Preserve the full
        # executable ask ladders for depth/VWAP-aware presubmit sizing.
        yes_ask_levels = sorted((100 - price, count) for price, count in self.no.items())
        no_ask_levels = sorted((100 - price, count) for price, count in self.yes.items())
        return {
            "yes_bid": yes_bid,
            "yes_ask": self.best_yes_ask(),
            "no_bid": no_bid,
            "no_ask": self.best_no_ask(),
            "yes_bid_size": self.yes.get(yes_bid) if yes_bid is not None else None,
            "no_bid_size": self.no.get(no_bid) if no_bid is not None else None,
            "yes_ask_size": self.no.get(no_bid) if no_bid is not None else None,
            "no_ask_size": self.yes.get(yes_bid) if yes_bid is not None else None,
            "yes_ask_levels": [list(level) for level in yes_ask_levels],
            "no_ask_levels": [list(level) for level in no_ask_levels],
            # Local receipt time, not a fabricated venue event timestamp.
            "book_received_at": self.updated_at,
            "book_sequence": self.seq,
        }


def apply_frame(books: dict[str, BookState], frame: dict[str, Any]) -> None:
    """Route one WS frame into the per-ticker book map (pure/testable)."""
    ftype = frame.get("type")
    msg = frame.get("msg", {})
    ticker = msg.get("market_ticker")
    if not ticker:
        return
    book = books.setdefault(ticker, BookState(ticker))
    if ftype == "orderbook_snapshot":
        book.apply_snapshot(msg)
    elif ftype == "orderbook_delta":
        book.apply_delta(msg)


def normalize_orderbook_levels(
    orderbook: dict[str, Any], side: str,
) -> list[tuple[int, float]]:
    """Normalize legacy integer-cent and current fixed-point dollar levels."""
    raw = orderbook.get(side)
    dollars = False
    if raw is None:
        raw = orderbook.get(f"{side}_dollars")
        dollars = True
    levels: list[tuple[int, float]] = []
    for level in raw or []:
        if not isinstance(level, (list, tuple)) or len(level) < 2:
            continue
        try:
            price = int(round(float(level[0]) * 100)) if dollars else int(level[0])
            count = float(level[1])
        except (TypeError, ValueError):
            continue
        if 1 <= price <= 99 and count > 0:
            levels.append((price, count))
    return levels


class KalshiLiveBook:
    """Async WS client maintaining live books for subscribed tickers."""

    def __init__(self, connect_fn: Callable[..., Any] | None = None) -> None:
        self.books: dict[str, BookState] = {}
        self._connect_fn = connect_fn
        self._running = False

    async def run(self, tickers: list[str], max_frames: int | None = None) -> None:
        import websockets

        connect = self._connect_fn or websockets.connect
        self._running = True
        frames = 0
        async with connect(_ws_url(), additional_headers=sign_ws_headers()) as ws:
            await ws.send(json.dumps({
                "id": 1, "cmd": "subscribe",
                "params": {"channels": ["orderbook_delta"], "market_tickers": tickers},
            }))
            async for raw in ws:
                if not self._running:
                    break
                try:
                    apply_frame(self.books, json.loads(raw))
                except Exception:
                    continue
                frames += 1
                if max_frames is not None and frames >= max_frames:
                    break

    def stop(self) -> None:
        self._running = False

    def quote(self, ticker: str) -> dict[str, Any] | None:
        book = self.books.get(ticker)
        return book.quote() if book else None


def fresh_best_quote(
    ticker: str, fetch_orderbook: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Synchronous REST read -> timestamped quote plus executable ask depth."""
    if fetch_orderbook is None:
        from kalshi.presubmit import default_fetch_orderbook

        fetch_orderbook = default_fetch_orderbook
    try:
        ob = fetch_orderbook(ticker)
    except Exception:
        return None
    book = BookState(ticker)
    yes = normalize_orderbook_levels(ob, "yes")
    no = normalize_orderbook_levels(ob, "no")
    # REST orderbook uses [price, count] pairs like the WS snapshot.
    book.apply_snapshot({"yes": yes, "no": no})
    return book.quote()
