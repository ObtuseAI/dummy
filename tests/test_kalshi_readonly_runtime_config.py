from __future__ import annotations

from tests.v16_test_helpers import SECRET_KEY, SECRET_PEM, valid_runtime_config


def test_runtime_config_resolves_single_redacted_source_without_import_cache() -> None:
    config = valid_runtime_config()

    assert config.ready is True
    assert config.selected_source == "process_env"
    assert config.base_url == "https://trading-api.kalshi.example"
    assert config.api_version == "v2"
    assert config.max_request_timeout_s <= 10
    assert config.total_timeout_s <= 45
    report_text = str(config.to_report())
    assert SECRET_KEY not in report_text
    assert SECRET_PEM not in report_text


def test_runtime_config_missing_credentials_blocks_retry() -> None:
    from tests.v16_test_helpers import missing_runtime_config

    config = missing_runtime_config()

    assert config.ready is False
    assert config.invalid_reason == "CREDENTIALS_MISSING"
    assert config.allows_terrain_retry is False
