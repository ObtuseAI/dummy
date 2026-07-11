from pathlib import Path


def test_dummy_path_integrity():
    from archive.report_scripts.generate_v6_reports import generate_dummy_path_integrity_report_v1
    report = generate_dummy_path_integrity_report_v1()
    assert report["active_root"] == "C:\\src\\engine\\dummy"
    assert report["old_root_absent"] is True
    assert report["required_paths_present"] is True
    assert report["no_dumby_labels_in_runtime_paths"] is True
    assert report["verdict"] == "PASS"
