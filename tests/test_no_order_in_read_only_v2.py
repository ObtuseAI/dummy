from kalshi.live_data import KalshiRealReadOnly


def test_order_creating_endpoints_listed_and_blocked():
    reader = KalshiRealReadOnly.__new__(KalshiRealReadOnly)
    # Simulate a malicious endpoint call that should be flagged.
    reader._endpoints = {"POST /orders"}
    assert "POST /orders" in reader.order_creating_endpoints_called()


def test_read_only_endpoints_not_flagged():
    reader = KalshiRealReadOnly.__new__(KalshiRealReadOnly)
    reader._endpoints = {
        "GET /account",
        "GET /portfolio/positions",
    }
    assert not reader.order_creating_endpoints_called()


def test_report_verdict_pass_when_no_order_endpoints():
    from scripts.generate_v5_reports import generate_no_order_in_read_only_report_v2
    report = generate_no_order_in_read_only_report_v2()
    assert report["verdict"] == "PASS"
