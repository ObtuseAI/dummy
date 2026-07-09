from __future__ import annotations

from predator_mesh.v15.source_adapter_closure_v5 import SourceAdapterClosureV5
from tests.v15_test_helpers import MALFORMED_BACKSLASH_ENV, forensics_with_env


def test_kalshi_entry_reflects_terrain_mode() -> None:
    forensics = forensics_with_env(MALFORMED_BACKSLASH_ENV)
    closure = SourceAdapterClosureV5(forensics_report=forensics.to_report())
    entry = closure.kalshi_entry()
    assert entry["mode"] == "SAMPLE_STATIC_FALLBACK"
    assert entry["terrain_mode"].startswith("PARTIAL_")


def test_closure_entries_include_kalshi_first() -> None:
    forensics = forensics_with_env(MALFORMED_BACKSLASH_ENV)
    closure = SourceAdapterClosureV5(forensics_report=forensics.to_report())
    entries = closure.closure_entries()
    assert entries[0]["source_name"] == "kalshi_real_orderbook_liquidity"


def test_report_no_unauthorized_sources() -> None:
    forensics = forensics_with_env(MALFORMED_BACKSLASH_ENV)
    closure = SourceAdapterClosureV5(forensics_report=forensics.to_report())
    report = closure.to_report()
    assert report["unauthorized_sources"] == []
    assert report["legality_recheck"]["verdict"] == "PASS"
