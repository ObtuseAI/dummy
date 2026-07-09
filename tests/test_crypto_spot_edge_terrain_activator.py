from tests.v22_test_helpers import assert_current_test_report


def test_v22_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["no_private_exchange_api"] is True
    assert report["no_trading_endpoint"] is True
    assert report["no_leverage"] is True
