"""Regression coverage for the pytest production-ledger interlock."""

from __future__ import annotations

import inspect
from pathlib import Path

from autonomy.ledger import AutonomyLedger


DEFAULT_LEDGER_PATH = Path("runtime/autonomy/ledger.db")


def test_default_ledger_is_redirected_to_per_test_tmp_path(tmp_path):
    ledger = AutonomyLedger()
    try:
        expected = tmp_path / DEFAULT_LEDGER_PATH
        assert ledger.db_path == expected
        assert expected.is_file()
        assert ledger.db_path.resolve() != (
            _project_root() / DEFAULT_LEDGER_PATH
        ).resolve()
    finally:
        ledger.close()


def test_explicit_project_default_is_also_redirected(tmp_path):
    ledger = AutonomyLedger(_project_root() / DEFAULT_LEDGER_PATH)
    try:
        assert ledger.db_path == tmp_path / DEFAULT_LEDGER_PATH
    finally:
        ledger.close()


def test_explicit_tmp_ledger_path_passes_through_unchanged(tmp_path):
    explicit = tmp_path / "explicit" / "ledger.db"
    ledger = AutonomyLedger(explicit)
    try:
        assert ledger.db_path == explicit
        assert explicit.is_file()
    finally:
        ledger.close()


def test_constructor_path_contract_remains_inspectable_without_io():
    parameter = inspect.signature(AutonomyLedger).parameters["db_path"]

    assert parameter.default == DEFAULT_LEDGER_PATH
    assert parameter.annotation in (Path | str, "Path | str")


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent
