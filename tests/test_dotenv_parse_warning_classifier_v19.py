from __future__ import annotations


def test_dotenv_parse_warning_classifier_v19_identifies_line_shape_without_value() -> None:
    from predator_mesh.v19.env_hygiene import DotenvParseWarningClassifier

    report = DotenvParseWarningClassifier().to_report()
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report["raw_line_content_exposed"] is False
    assert report["classifications"]
