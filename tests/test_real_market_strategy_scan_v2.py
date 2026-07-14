import asyncio


def test_strategy_scan_produces_proposals_or_no_trade_reasons():
    from archive.report_scripts.generate_v5_reports import generate_strategy_scan_report_v2
    report = asyncio.run(generate_strategy_scan_report_v2())
    results = report.get("results", [])
    assert len(results) > 0
    for r in results:
        assert "family" in r
        assert r.get("has_proposal") or r.get("no_trade_reason")


def test_strategy_candidate_quality_report():
    from archive.report_scripts.generate_v5_reports import generate_strategy_candidate_quality_report
    report = generate_strategy_candidate_quality_report()
    assert report["verdict"] == "PASS"
    required = report["required_fields"]
    assert "strategy family" in required
    assert "edge estimate" in required
