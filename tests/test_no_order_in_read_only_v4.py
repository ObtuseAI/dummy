"""Prove that V4 READ_ONLY ingestion never calls order-creating endpoints."""

from kalshi.live_data import KalshiRealReadOnly


def test_no_order_in_read_only_report_v4():
    from archive.report_scripts.generate_v8_kalshi_reports import generate_no_order_in_read_only_report_v4

    report = generate_no_order_in_read_only_report_v4()
    assert report["verdict"] == "PASS"
    assert "create_order" in report["order_creating_methods_blocked"]
    assert "cancel_order" in report["order_creating_methods_blocked"]
    assert "POST" in report["write_http_methods_blocked"]
    assert "PUT" in report["write_http_methods_blocked"]
    assert "DELETE" in report["write_http_methods_blocked"]
    assert report["kalshi_real_read_only_has_no_create_order"] is True


def test_read_only_wrapper_has_no_order_creating_methods():
    methods = {m for m in dir(KalshiRealReadOnly) if not m.startswith("_")}
    order_creating = {"create_order", "cancel_order", "post_order", "place_order"}
    assert methods & order_creating == set()


def test_read_only_endpoints_exclude_orders():
    reader = KalshiRealReadOnly.__new__(KalshiRealReadOnly)
    reader._endpoints = {
        "GET /portfolio/balance",
        "GET /events",
        "GET /markets",
        "GET /markets/{ticker}/orderbook",
        "GET /portfolio/positions",
        "GET /portfolio/orders",
        "GET /portfolio/fills",
    }
    assert not reader.order_creating_endpoints_called()
