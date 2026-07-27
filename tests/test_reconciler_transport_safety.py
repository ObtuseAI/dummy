from unittest.mock import MagicMock, patch

import autonomy.reconciler as reconciler
import httpx


def test_public_base_ignores_ambient_endpoint_redirect(monkeypatch):
    monkeypatch.setenv("KALSHI_API_BASE", "https://attacker.invalid")
    monkeypatch.setenv("KALSHI_API_VERSION", "trade-api/v999")

    assert (
        reconciler._public_base()
        == "https://external-api.kalshi.com/trade-api/v2"
    )


def test_public_fetch_disables_environment_proxy_trust():
    response = httpx.Response(
        200,
        json={"market": {"ticker": "TEST"}},
        request=httpx.Request("GET", "https://kalshi.invalid/markets/TEST"),
    )
    client = MagicMock()
    client.__enter__.return_value = client
    client.get.return_value = response

    with patch("httpx.Client", return_value=client) as client_type:
        result = reconciler.default_fetch_market_result("TEST")

    assert result == {"ticker": "TEST"}
    assert client_type.call_args.kwargs["trust_env"] is False
    assert client_type.call_args.kwargs["base_url"] == (
        "https://external-api.kalshi.com/trade-api/v2"
    )
    client.get.assert_called_once_with("/markets/TEST", params=None)
