from autonomy.ontology import Vertical
from autonomy.target_policy import (
    has_prediction_target_authority,
    is_data_only_target,
    is_data_only_vertical,
    is_equity_index_target,
    is_prediction_quarantined_target,
    target_policy_payload,
)


def test_weather_and_commodities_are_data_only_targets():
    assert is_data_only_vertical(Vertical.WEATHER)
    assert is_data_only_vertical("COMMODITIES")
    assert is_data_only_target("KXRAINNYC-26JUL21")
    assert is_data_only_target("KXWTI-26JUL21-T80")
    assert is_data_only_target("ANY", category="Weather")
    assert is_data_only_target("ANY", category="Commodities")


def test_context_mentions_do_not_block_sports_or_crypto_targets():
    assert not is_data_only_target("KXMLBGAME-26JUL21NYYBOS-NYY", category="Sports")
    assert not is_data_only_target("KXBTC15M-26JUL211230-30", category="Crypto")


def test_prediction_authority_requires_structured_allowlisted_context():
    assert has_prediction_target_authority("OPAQUE", category="Sports")
    assert has_prediction_target_authority("OPAQUE", category="Crypto")
    assert not has_prediction_target_authority("OPAQUE")
    assert not has_prediction_target_authority("OPAQUE", category="Companies")
    assert not has_prediction_target_authority(
        "KXTSLAA-26JUL22-B350", category="Sports"
    )


def test_equity_and_index_targets_are_fail_closed_by_prefix_or_category():
    for ticker in (
        "KXINXY-26JUL22-B6400",
        "KXSPX-26JUL22-B6400",
        "KXNASDAQ100Y-26JUL22-B24000",
        "KXTSLAA-26JUL22-B350",
        "KXNVDAA-26JUL22-B200",
        "KXAAPLA-26JUL22-B250",
        "KXAMZNA-26JUL22-B250",
        "KXBAA-28JANDELIV-700",
        "KXEBAYA-28JANGMV-92000000000.0",
        "KXCVNAA-28JANUNITS-910000",
        "KXFA-28JANUSSALES-2300000.0",
        "KXUALA-28JANPAX-190000000",
        "SPX-2026-07-22",
        "TSLA:2026-07-22",
    ):
        assert is_equity_index_target(ticker), ticker
        assert is_prediction_quarantined_target(ticker), ticker

    assert is_equity_index_target("OPAQUE", category="Equities")
    assert is_equity_index_target("OPAQUE", category="Companies")
    assert is_equity_index_target(
        "OPAQUE", category="Financials", series_tags=["KPIs"]
    )
    assert is_equity_index_target(
        "OPAQUE", category="Financials", series_tags=["Single company"]
    )


def test_broad_financials_category_does_not_quarantine_fx_or_rates():
    assert not is_equity_index_target(
        "KXEURUSD-26JUL2310-T1.15399",
        category="Financials",
        series_tags=["Foreign Exchange"],
    )
    assert not is_equity_index_target(
        "KXUST10M-26JUL-T4.5",
        category="Financials",
        series_tags=["Interest Rates"],
    )


def test_equity_prefix_matching_is_bounded_and_preserves_sports_crypto():
    assert not is_equity_index_target("KXSPXLONGWORD")
    assert not is_equity_index_target("KXMLBGAME-26JUL21NYYBOS-NYY", category="Sports")
    assert not is_equity_index_target("KXBTC15M-26JUL211230-30", category="Crypto")
    assert not is_prediction_quarantined_target(
        "KXMLBGAME-26JUL21NYYBOS-NYY", category="Sports"
    )
    assert not is_prediction_quarantined_target(
        "KXBTC15M-26JUL211230-30", category="Crypto"
    )


def test_unsupported_target_policy_is_permanently_fail_closed():
    policy = target_policy_payload("KXTSLA-26JUL22-B350", category="Equities")
    assert policy["classification"] == "unsupported_target"
    assert policy["role"] == "excluded"
    assert policy["prediction_target"] is False
    assert policy["trade_proposal_authority"] is False
    assert policy["execution_target"] is False
    assert policy["reason"] == "outside_supported_prediction_targets"
    assert all("valuation" not in key for key in policy)
