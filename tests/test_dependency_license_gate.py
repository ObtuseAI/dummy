from __future__ import annotations

from scripts.check_dependency_licenses import (
    declared_dependencies,
    prohibited_license,
)


def test_prohibited_license_detector_blocks_strong_copyleft_and_source_available() -> None:
    assert prohibited_license("GNU Affero General Public License v3") == "AGPL"
    assert prohibited_license("GNU General Public License v3") == "GPL"
    assert prohibited_license("Server Side Public License") == "SSPL"
    assert prohibited_license("Business Source License 1.1") == "BUSL"
    assert prohibited_license("MIT with Commons Clause") == "COMMONS_CLAUSE"


def test_prohibited_license_detector_does_not_misclassify_permissive_or_weak_copyleft() -> None:
    assert prohibited_license("MIT") is None
    assert prohibited_license("Apache-2.0 OR BSD-3-Clause") is None
    assert prohibited_license("MPL-2.0") is None
    assert prohibited_license("LGPL-3.0") is None


def test_declared_dependencies_selects_only_requested_optional_groups(tmp_path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "fixture"
version = "1"
dependencies = ["Alpha>=1"]

[project.optional-dependencies]
dev = ["Beta[cli]>=2"]
desktop = ["Gamma>=3"]
""".strip(),
        encoding="utf-8",
    )

    assert declared_dependencies(pyproject, extras=("dev",)) == ["alpha", "beta"]
