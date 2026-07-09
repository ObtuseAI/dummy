from __future__ import annotations

from predator_mesh.v34.run import DomainMarketClassScoreboardV19, build_default_v34_state
from tests.v34_test_helpers import assert_v34_report_named


def test_domain_market_class_scoreboard_default_status() -> None:
    board = DomainMarketClassScoreboardV19().build(build_default_v34_state(enable_network=False))

    assert board.market_class_scoreboard_v19_status == "PASS_PARTIAL_EXPECTED"
    assert board.execution_bridge_present is False
    assert len(board.domain_market_class_rows) == 4


def test_domain_market_class_scoreboard_report_contract() -> None:
    report = assert_v34_report_named("domain_market_class_scoreboard_v19_report.json", "domain_market_class_scoreboard_v19_status")

    assert report["domain_market_class_scoreboard_v19_status"] == "PASS_PARTIAL_EXPECTED"
