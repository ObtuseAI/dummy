#!/usr/bin/env python
"""Fail closed on missing or prohibited licenses in selected direct dependencies."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
import tomllib
from pathlib import Path
from typing import Any


FORBIDDEN_LICENSE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AGPL", re.compile(r"\bAGPL(?:V?\d|\b)|GNU AFFERO", re.IGNORECASE)),
    (
        "GPL",
        re.compile(
            r"(?<!L)(?<!A)\bGPL(?:V?\d|\b)|GNU GENERAL PUBLIC LICENSE",
            re.IGNORECASE,
        ),
    ),
    ("SSPL", re.compile(r"\bSSPL\b|SERVER SIDE PUBLIC LICENSE", re.IGNORECASE)),
    ("BUSL", re.compile(r"\bBUSL\b|BUSINESS SOURCE LICENSE", re.IGNORECASE)),
    ("COMMONS_CLAUSE", re.compile(r"COMMONS CLAUSE", re.IGNORECASE)),
)


def _canonical_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _requirement_name(requirement: str) -> str:
    name = re.split(r"[\s\[<>=!~;]", requirement.strip(), maxsplit=1)[0]
    if not name:
        raise ValueError(f"cannot parse dependency requirement: {requirement!r}")
    return _canonical_name(name)


def declared_dependencies(
    pyproject: Path,
    *,
    extras: tuple[str, ...] = (),
) -> list[str]:
    with pyproject.open("rb") as stream:
        project = tomllib.load(stream).get("project") or {}
    requirements = list(project.get("dependencies") or [])
    optional = project.get("optional-dependencies") or {}
    unknown = sorted(set(extras) - set(optional))
    if unknown:
        raise ValueError(f"unknown optional dependency groups: {unknown}")
    for extra in extras:
        requirements.extend(optional[extra])
    return sorted({_requirement_name(item) for item in requirements})


def distribution_license(distribution: importlib.metadata.Distribution) -> str:
    metadata = distribution.metadata
    values: list[str] = []
    for key in ("License-Expression", "License"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
    values.extend(
        item.removeprefix("License :: ").strip()
        for item in metadata.get_all("Classifier", [])
        if item.startswith("License :: ")
    )
    return " | ".join(dict.fromkeys(values))


def prohibited_license(license_text: str) -> str | None:
    for label, pattern in FORBIDDEN_LICENSE_PATTERNS:
        if pattern.search(license_text):
            return label
    return None


def evaluate_licenses(
    pyproject: Path,
    *,
    extras: tuple[str, ...] = (),
) -> dict[str, Any]:
    selected = declared_dependencies(pyproject, extras=extras)
    installed = {
        _canonical_name(distribution.metadata["Name"]): distribution
        for distribution in importlib.metadata.distributions()
        if distribution.metadata.get("Name")
    }
    rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    for name in selected:
        distribution = installed.get(name)
        if distribution is None:
            blockers.append(f"{name}:not_installed")
            rows.append(
                {
                    "name": name,
                    "version": None,
                    "license": None,
                    "status": "MISSING",
                }
            )
            continue
        license_text = distribution_license(distribution)
        prohibited = prohibited_license(license_text)
        if not license_text:
            blockers.append(f"{name}:license_metadata_missing")
            status = "BLOCKED"
        elif prohibited:
            blockers.append(f"{name}:prohibited_license:{prohibited}")
            status = "BLOCKED"
        else:
            status = "PASS"
        rows.append(
            {
                "name": name,
                "version": distribution.version,
                "license": license_text[:500] or None,
                "status": status,
            }
        )
    return {
        "schema_version": 1,
        "status": "PASS" if not blockers else "BLOCKED",
        "pyproject": str(pyproject),
        "extras": list(extras),
        "dependencies": rows,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    parser.add_argument(
        "--extra",
        action="append",
        default=[],
        help="optional dependency group installed for this environment",
    )
    args = parser.parse_args(argv)
    try:
        report = evaluate_licenses(
            args.pyproject,
            extras=tuple(dict.fromkeys(args.extra)),
        )
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        report = {
            "schema_version": 1,
            "status": "BLOCKED",
            "blockers": [f"configuration_error:{type(exc).__name__}:{exc}"],
        }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
