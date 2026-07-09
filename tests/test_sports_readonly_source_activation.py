from __future__ import annotations

from v19_test_helpers import assert_domain_activation_report


def test_sports_readonly_source_activation_blocks_questionable_odds_scraping() -> None:
    assert_domain_activation_report("sports")
