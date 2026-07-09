from __future__ import annotations

from tests.v16_test_helpers import valid_runtime_config


def test_timeout_guards_still_intact_v16() -> None:
    config = valid_runtime_config()

    assert config.max_request_timeout_s <= 10
    assert config.total_timeout_s <= 45
