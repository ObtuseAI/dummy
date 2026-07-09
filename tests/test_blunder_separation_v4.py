def test_blunder_separation_recheck_v4():
    from scripts.generate_v6_reports import generate_blunder_separation_recheck_v4
    report = generate_blunder_separation_recheck_v4()
    assert report["verdict"] == "PASS"
    assert report["blunder_fingerprint_unchanged"] is True
    assert report["non_test_references_to_blunder"] == []


def test_dummy_independence_report_v2():
    from scripts.generate_v6_reports import generate_dummy_independence_report_v2
    report = generate_dummy_independence_report_v2()
    assert report["verdict"] == "PASS"
    assert all(report["owns_configs_logs_artifacts_proof_dashboard"].values())
    assert report["production_imports_from_blunder"] == []
