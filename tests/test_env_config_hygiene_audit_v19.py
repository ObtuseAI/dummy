from __future__ import annotations

from v19_test_helpers import assert_pass_or_partial


def test_env_config_hygiene_audit_v19_redacts_line_content() -> None:
    from predator_mesh.v19.env_hygiene import EnvConfigHygieneAudit

    report = EnvConfigHygieneAudit().to_report()
    assert_pass_or_partial(report)
    assert report["auto_edited_env"] is False
    assert report["raw_line_content_exposed"] is False
    assert report["affected_line_numbers"]
