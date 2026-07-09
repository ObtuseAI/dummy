import pytest


def test_blunder_separation_recheck_v5():
    from scripts.generate_v7_reports import generate_blunder_separation_recheck_v5
    report = generate_blunder_separation_recheck_v5()
    assert report["verdict"] == "PASS"
    assert report["blunder_fingerprint_unchanged"] is True
    assert report["non_test_references_to_blunder"] == []
