def test_blunder_separation_recheck_v6():
    from archive.report_scripts.generate_v8_identity_reports import generate_blunder_separation_recheck_v6

    report = generate_blunder_separation_recheck_v6()
    assert report["verdict"] == "PASS"
    assert report["inherited_blunder_present"] is True
    assert report["manifest_matches"] is True
    assert report["manifest_mismatches"] == []
    assert report["inherited_blunder_file_count"] > 0
