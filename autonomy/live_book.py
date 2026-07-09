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
        self.yes: dict[int, int] = {}
        self.no: dict[int, int] = {}
        self.seq: int | None = None
        self.updated_at: str | None = None

    def apply_snapshot(self, msg: dict[str, Any]) -> None:
        self.yes = {int(p): int(c) for p, c in msg.get("yes", []) if int(c) > 0}
        self.no = {int(p): int(c) for p, c in msg.get("no", []) if int(c) > 0}
        self.seq = msg.get("seq")
        self._stamp()

    def apply_delta(self, msg: dict[str, Any]) -> None:
        side = msg.get("side")
        price = int(msg.get("price"))
        delta = int(msg.get("delta", 0))
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

    def quote(self) -> dict[str, int | None]:
        return {
            "yes_bid": self.best_yes_bid(),
            "yes_ask": self.best_yes_ask(),
            "no_bid": self.best_no_bid(),
            "no_ask": self.best_no_ask(),
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

    def quote(self, ticker: str) -> dict[str, int | None] | None:
        book = self.books.get(ticker)
        return book.quote() if book else None


def fresh_best_quote(ticker: str, fetch_orderbook: Callable[[str], dict[str, Any]] | None = None) -> dict[str, int | None] | None:
    """Synchronous REST book read → best quote, for pre-submit re-pricing."""
    if fetch_orderbook is None:
        from kalshi.presubmit import default_fetch_orderbook

        fetch_orderbook = default_fetch_orderbook
    try:
        ob = fetch_orderbook(ticker)
    except Exception:
        return None
    book = BookState(ticker)
    yes = ob.get("yes") or []
    no = ob.get("no") or []
    # REST orderbook uses [price, count] pairs like the WS snapshot.
    book.apply_snapshot({"yes": yes, "no": no})
    return book.quote()
