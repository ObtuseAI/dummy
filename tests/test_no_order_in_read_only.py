"""Prove that READ_ONLY ingestion never calls order-creating endpoints."""

from kalshi.live_data import KalshiRealReadOnly


def test_read_only_wrapper_has_no_order_creating_methods():
    """KalshiRealReadOnly only exposes GET-style read methods."""
    methods = {m for m in dir(KalshiRealReadOnly) if not m.startswith("_")}
    order_creating = {"create_order", "cancel_order", "post_order", "place_order"}
    assert methods & order_creating == set()


def test_read_only_endpoints_exclude_orders():
    reader = KalshiRealReadOnly.__new__(KalshiRealReadOnly)
    reader._endpoints = {
        "GET /account",
        "GET /account/balance",
        "GET /events",
        "GET /markets",
        "GET /markets/{ticker}/orderbook",
        "GET /portfolio/positions",
        "GET /portfolio/orders",
        "GET /portfolio/fills",
    }
    assert not reader.order_creating_endpoints_called()
